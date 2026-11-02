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
    control=(manifest,clock,(root/raw['observation_config']).resolve())
    if 'input_format' in raw:
        if raw['input_format']!='sigmf_ci16_le':raise ValueError('unsupported session input_format')
        return control+tuple(path for station in raw['stations']
            for path in SigMFInputIdentity._resolve_paths(root/station['sigmf']))
    return control+tuple((root/s['vdif']).resolve() for s in raw['stations'])


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
        self._config=load_session(self._manifest,allow_sigmf=True)
        self._sigmf=self._config.get('input_format')=='sigmf_ci16_le'
        self._metadata_paths=self._paths[:3]+(self._paths[3::2] if self._sigmf else ())
        self._raw_paths=self._paths[4::2] if self._sigmf else self._paths[3:]
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
        if self._sigmf:
            if len({digests[path] for path in self._raw_paths})!=len(self._raw_paths):
                raise ValueError('SigMF station data SHA must be distinct; copied stations are unsupported')
            self._identity.pop('input_vdif')
            self._identity['input_sigmf']=[{'station_id':station['id'],
                'metadata':{'sha256':digests[meta],'bytes':self._snapshot[meta][2]},
                'data':{'sha256':digests[data],'bytes':self._snapshot[data][2]}}
                for station,meta,data in zip(self._config['stations'],self._paths[3::2],self._raw_paths)]
        self._diagnostics={'schema_version':1,'hash_policy':'fresh_full_vdif_hash_once_per_run_with_rehashed_metadata',
            'initial_hashed_file_count':len(digests),'initial_hash_bytes':sum(self._snapshot[p][2] for p in digests),
            'full_sha_passes_per_unique_vdif_file':1,
            'change_check':'Resolved input paths, device/inode, size, mtime_ns and ctime_ns before/after stages',
            'structure_scope':'SHA identifies bytes; it does not validate all VDIF headers',
            'limits':'Closed input files, in-memory run only; VDIF changes that preserve all stat fields may be missed, including timestamp granularity. No adversarial filesystem proof.'}

        if self._sigmf:
            self._diagnostics.pop('full_sha_passes_per_unique_vdif_file')
            self._diagnostics.update(hash_policy='fresh_full_sigmf_data_hash_once_per_run_with_rehashed_metadata',
                full_sha_passes_per_unique_sigmf_data_file=1,
                structure_scope='Limited ci16_le profile; SHA identifies pair bytes, not clock accuracy or signal quality',
                limits='Closed files, trusted Python callers; data changes preserving all stat fields may be missed, including timestamp granularity. No adversarial filesystem proof.')

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
                for path in dict.fromkeys(self._metadata_paths):
                    if self._digest(path)!=self._digests[path]:
                        raise ValueError('input files changed in metadata content')
        except (OSError,KeyError,TypeError,json.JSONDecodeError) as exc:
            raise ValueError('input files changed or became unavailable during processing') from exc
        if config is not None and (Path(config['_root']).resolve()!=self._manifest.parent or
                                  config_values(config)!=config_values(self._config)):
            raise ValueError('input files changed from loaded configuration')

    @property
    def public_identity(self):return deepcopy(self._identity)

    def bind_sigmf_session(self,manifest,clock,expected_config=None):
        """Bind a guarded derived session to this live, freshly hashed source."""
        return DerivedSigMFInputIdentity(self,manifest,clock,expected_config)

    @property
    def diagnostics(self):
        vdifs=set(self._raw_paths);metadata=set(self._metadata_paths)
        prefix='sigmf_data' if self._sigmf else 'vdif'
        return {**deepcopy(self._diagnostics),
            prefix+'_hash_bytes':sum(self._snapshot[p][2]*self._hash_reads[p] for p in vdifs),
            prefix+'_hash_file_reads':sum(self._hash_reads[p] for p in vdifs),
            'metadata_hash_bytes':sum(self._snapshot[p][2]*self._hash_reads[p] for p in metadata),
            'metadata_hash_file_reads':sum(self._hash_reads[p] for p in metadata)}


class DerivedSigMFInputIdentity:
    """Sequential in-memory reuse, not a supplied digest or filesystem lock.

    Only block count and control-file placement may differ from the source.
    The source and derived small files are rechecked at every boundary. Raw
    changes preserving every stat field remain outside this closed-file guard.
    """
    def __init__(self,source,manifest,clock,expected_config=None):
        if not isinstance(source,InputIdentity):raise TypeError('live InputIdentity source required')
        if not source._sigmf:raise ValueError('derived identity requires a SigMF source')
        source.assert_current(source._manifest,source._clock,source._config)
        self._source=source;self._manifest=Path(manifest).resolve();self._clock=Path(clock).resolve()
        if self._clock!=source._clock:raise ValueError('derived clock path differs from source')
        self._paths=input_paths(self._manifest,self._clock)
        if self._paths[3:]!=source._paths[3:]:raise ValueError('derived SigMF pairs differ from source')
        self._snapshot=snapshot_paths(self._paths)
        self._metadata_paths=tuple(dict.fromkeys(self._paths[:3]+self._paths[3::2]))
        self._hash_reads={path:0 for path in self._metadata_paths}
        # Hash before parsing, then rehash after parsing to bind the loaded
        # configuration even if a small rewrite preserves all timestamps.
        self._digests={path:self._digest(path) for path in self._metadata_paths}
        self._config=load_session(self._manifest,allow_sigmf=True)
        ignored={'_root','observation_config','blocks_per_integration','stations'}
        def semantic(config):
            return json.dumps({k:v for k,v in config.items() if k not in ignored},sort_keys=True,allow_nan=False)
        if (semantic(self._config)!=semantic(source._config)
                or [s['id'] for s in self._config['stations']]!=[s['id'] for s in source._config['stations']]):
            raise ValueError('derived session configuration differs from source')
        self.assert_current(manifest,clock,expected_config)
        self._identity={'input_manifest_sha256':self._digests[self._paths[0]],
            'input_clock_sha256':self._digests[self._paths[1]],
            'input_observation_sha256':self._digests[self._paths[2]],
            'input_sigmf':source.public_identity['input_sigmf']}

    def _digest(self,path):
        value=digest_file(path);self._hash_reads[path]+=1;return value

    def assert_current(self,manifest,clock,config=None):
        self._source.assert_current(self._source._manifest,self._source._clock,self._source._config)
        if Path(manifest).resolve()!=self._manifest or Path(clock).resolve()!=self._clock:
            raise ValueError('derived identity belongs to different input paths')
        try:
            paths=input_paths(manifest,clock)
            if paths!=self._paths or snapshot_paths(paths)!=self._snapshot:
                raise ValueError('derived input files changed during processing')
            for path in self._metadata_paths:
                if self._digest(path)!=self._digests[path]:
                    raise ValueError('derived metadata content changed during processing')
        except (OSError,KeyError,TypeError,json.JSONDecodeError) as error:
            raise ValueError('derived input files changed or became unavailable') from error
        if config is not None and (Path(config['_root']).resolve()!=self._manifest.parent
                                  or config_values(config)!=config_values(self._config)):
            raise ValueError('derived input files changed from loaded configuration')

    @property
    def public_identity(self):return deepcopy(self._identity)

    @property
    def diagnostics(self):
        return {'schema_version':1,'hash_policy':'guarded_in_memory_sigmf_derived_view_no_data_rehash',
            'source_input_manifest_sha256':self._source.public_identity['input_manifest_sha256'],
            'source_input_observation_sha256':self._source.public_identity['input_observation_sha256'],
            'initial_hashed_file_count':len(self._metadata_paths),
            'initial_hash_bytes':sum(self._snapshot[p][2] for p in self._metadata_paths),
            'full_sha_passes_per_unique_sigmf_data_file':0,
            'sigmf_data_hash_file_reads':0,'sigmf_data_hash_bytes':0,
            'metadata_hash_bytes':sum(self._snapshot[p][2]*self._hash_reads[p] for p in self._metadata_paths),
            'metadata_hash_file_reads':sum(self._hash_reads.values()),
            'change_check':'Parent source and derived paths/stat; parent and derived small-file content SHA at each boundary',
            'limits':'Closed files, sequential in-memory run, trusted Python callers; raw changes preserving all stat fields may be missed. No persistent cache or adversarial filesystem proof.'}


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
