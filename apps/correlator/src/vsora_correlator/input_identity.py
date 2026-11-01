"""In-memory identity of closed inputs, computed afresh for each run."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from .session import load_session
from vsora_formats.sigmf import SigMFRecording


def input_paths(manifest,clock):
    manifest=Path(manifest).resolve();clock=Path(clock).resolve()
    raw=json.loads(manifest.read_text());root=manifest.parent
    return (manifest,clock,(root/raw['observation_config']).resolve(),
            *((root/s['vdif']).resolve() for s in raw['stations']))


def snapshot_paths(paths):
    return {path:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            for path in paths for s in [path.stat()]}


def digest_file(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def config_values(config):
    return {k:v for k,v in config.items() if k!='_root'}


class InputIdentity:
    """No disk cache or caller-supplied digest. Every constructor hashes inputs.

    Stat guards detect normal changes, not adversarial filesystem manipulation.
    Python callers are trusted code; this is not a security capability.
    """
    def __init__(self,manifest,clock,expected_config=None):
        self._manifest=Path(manifest).resolve();self._clock=Path(clock).resolve()
        self._paths=input_paths(self._manifest,self._clock)
        self._snapshot=snapshot_paths(self._paths)
        self._hash_reads={path:0 for path in self._snapshot}
        self._config=load_session(self._manifest)
        if expected_config is not None and config_values(expected_config)!=config_values(self._config):
            raise ValueError('input files changed before identity capture')
        self.assert_current(manifest,clock,expected_config)
        digests={path:self._digest(path) for path in dict.fromkeys(self._paths)}
        self._digests=digests
        self.assert_current(manifest,clock,expected_config)
        self._identity={'input_manifest_sha256':digests[self._paths[0]],
            'input_clock_sha256':digests[self._paths[1]],'input_observation_sha256':digests[self._paths[2]],
            'input_vdif':[{'station_id':station['id'],'sha256':digests[path],'bytes':self._snapshot[path][2]}
                          for station,path in zip(self._config['stations'],self._paths[3:])]}
        self._diagnostics={'schema_version':1,'hash_policy':'fresh_full_vdif_hash_once_per_run_with_rehashed_metadata',
            'initial_hashed_file_count':len(digests),'initial_hash_bytes':sum(self._snapshot[p][2] for p in digests),
            'full_sha_passes_per_unique_vdif_file':1,
            'change_check':'Resolved input paths, device/inode, size, mtime_ns and ctime_ns before/after stages',
            'structure_scope':'SHA identifies bytes; it does not validate all VDIF headers',
            'limits':'Closed input files, in-memory run only; VDIF changes that preserve all stat fields may be missed, including timestamp granularity. No adversarial filesystem proof.'}

    def _digest(self,path):
        result=digest_file(path);self._hash_reads[path]+=1;return result

    def assert_current(self,manifest,clock,config=None):
        if (Path(manifest).resolve()!=self._manifest or Path(clock).resolve()!=self._clock):
            raise ValueError('input identity belongs to different input paths')
        try:
            paths=input_paths(manifest,clock)
            if paths!=self._paths or snapshot_paths(paths)!=self._snapshot:
                raise ValueError('input files changed during processing')
            if hasattr(self,'_digests'):
                # Small configuration files can change within one filesystem
                # timestamp tick. Compare bytes via SHA at every boundary.
                for path in dict.fromkeys(self._paths[:3]):
                    if self._digest(path)!=self._digests[path]:
                        raise ValueError('input files changed in metadata content')
        except (OSError,KeyError,TypeError,json.JSONDecodeError) as exc:
            raise ValueError('input files changed or became unavailable during processing') from exc
        if config is not None and (Path(config['_root']).resolve()!=self._manifest.parent or
                                  config_values(config)!=config_values(self._config)):
            raise ValueError('input files changed from loaded configuration')

    @property
    def public_identity(self):return deepcopy(self._identity)

    @property
    def diagnostics(self):
        vdifs=set(self._paths[3:]);metadata=set(self._paths[:3])
        return {**deepcopy(self._diagnostics),
            'vdif_hash_bytes':sum(self._snapshot[p][2]*self._hash_reads[p] for p in vdifs),
            'vdif_hash_file_reads':sum(self._hash_reads[p] for p in vdifs),
            'metadata_hash_bytes':sum(self._snapshot[p][2]*self._hash_reads[p] for p in metadata),
            'metadata_hash_file_reads':sum(self._hash_reads[p] for p in metadata)}


class SigMFInputIdentity:
    """Fresh identity of a closed SigMF pair; no persistent or supplied hash cache.

    Call assert_current at processing boundaries. The small metadata is rehashed;
    the dataset is fully hashed once per instance and guarded by stat afterward.
    These guards are not proof against changes preserving every stat field.
    """
    def __init__(self, metadata_path):
        self._metadata = Path(metadata_path).absolute()
        self._paths = self._resolve_paths(self._metadata)
        self._snapshot = snapshot_paths(self._paths)
        if self._snapshot[self._paths[0]][:2] == self._snapshot[self._paths[1]][:2]:
            raise ValueError('SigMF metadata and data must be distinct files')
        self._hash_reads = {path: 0 for path in self._paths}
        self.recording = SigMFRecording(self._metadata)
        self.assert_current()
        self._digests = {path: self._digest(path) for path in self._paths}
        self.assert_current()
        self._identity = {
            role: {'sha256': self._digests[path], 'bytes': self._snapshot[path][2]}
            for role, path in zip(('metadata', 'data'), self._paths)
        }

    @staticmethod
    def _resolve_paths(metadata):
        if not metadata.name.endswith('.sigmf-meta'):
            raise ValueError('SigMF metadata filename must end in .sigmf-meta')
        data = metadata.with_name(metadata.name[:-len('.sigmf-meta')] + '.sigmf-data')
        return metadata.resolve(), data.resolve()

    def _digest(self, path):
        value = digest_file(path)
        self._hash_reads[path] += 1
        return value

    def assert_current(self, metadata_path=None):
        try:
            paths = self._resolve_paths(self._metadata)
            if metadata_path is not None and self._resolve_paths(Path(metadata_path).absolute()) != self._paths:
                raise ValueError('SigMF identity belongs to different input paths')
            if paths != self._paths or snapshot_paths(paths) != self._snapshot:
                raise ValueError('SigMF input files changed during processing')
            if hasattr(self, '_digests') and self._digest(paths[0]) != self._digests[paths[0]]:
                raise ValueError('SigMF metadata content changed during processing')
        except OSError as error:
            raise ValueError('SigMF input files changed or became unavailable') from error

    @property
    def public_identity(self):
        return deepcopy(self._identity)

    @property
    def diagnostics(self):
        metadata, data = self._paths
        return {
            'schema_version': 1,
            'hash_policy': 'fresh_full_pair_sha256_once_per_instance_metadata_rehashed_at_boundaries',
            'data_hash_file_reads': self._hash_reads[data],
            'data_hash_bytes': self._snapshot[data][2] * self._hash_reads[data],
            'metadata_hash_file_reads': self._hash_reads[metadata],
            'metadata_hash_bytes': self._snapshot[metadata][2] * self._hash_reads[metadata],
            'change_check': 'resolved pair paths, device/inode, size, mtime_ns, ctime_ns; metadata content SHA',
            'limits': 'Closed files and trusted Python callers; dataset changes preserving every stat field can be missed. SHA identifies bytes, not clock accuracy or signal quality.',
        }
