import hashlib
import json
import os
import pytest
from vsora_correlator.input_identity import InputIdentity
from vsora_correlator.closure_pipeline import process_closure_session
from vsora_correlator.session import load_session
from workflows.vdif_closure_validation import make_fixture


@pytest.fixture
def inputs(tmp_path):
    make_fixture(tmp_path/'input',frame_count=16)
    return tmp_path/'input/manifest.json',tmp_path/'input/clock.json'


def test_fresh_identity_reads_all_bytes_once_and_returns_copies(inputs,monkeypatch):
    import vsora_correlator.input_identity as module
    manifest,clock=inputs;calls=[];digest=module.digest_file
    def count(path):calls.append(path);return digest(path)
    monkeypatch.setattr(module,'digest_file',count)
    identity=InputIdentity(manifest,clock)
    vdifs=[p for p in calls if p.suffix=='.vdif']
    assert len(vdifs)==len(set(vdifs))==4
    assert identity.diagnostics['vdif_hash_bytes']==sum(p.stat().st_size for p in vdifs)
    expected=hashlib.sha256((manifest.parent/'station-1.vdif').read_bytes()).hexdigest()
    public=identity.public_identity;assert public['input_vdif'][0]['sha256']==expected
    public['input_vdif'][0]['sha256']='untrusted';policy=identity.diagnostics;policy['vdif_hash_bytes']=0
    assert identity.public_identity['input_vdif'][0]['sha256']==expected
    assert identity.diagnostics['vdif_hash_bytes']>0
    identity.assert_current(manifest,clock);assert len([p for p in calls if p.suffix=='.vdif'])==4
    InputIdentity(manifest,clock);assert len([p for p in calls if p.suffix=='.vdif'])==8 # No persistent digest cache.


@pytest.mark.parametrize('filename',['manifest.json','clock.json','observation.json','station-1.vdif'])
def test_same_size_change_and_restored_mtime_are_detected(inputs,filename):
    manifest,clock=inputs;identity=InputIdentity(manifest,clock);path=manifest.parent/filename
    before=path.stat();data=bytearray(path.read_bytes());data[-1]^=1;path.write_bytes(data)
    os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
    assert path.stat().st_size==before.st_size and path.stat().st_mtime_ns==before.st_mtime_ns
    with pytest.raises(ValueError,match='input files changed'):identity.assert_current(manifest,clock)


def test_same_bytes_replacement_changes_inode(inputs):
    manifest,clock=inputs;identity=InputIdentity(manifest,clock)
    path=manifest.parent/'station-1.vdif';old=path.stat();replacement=path.with_suffix('.new')
    replacement.write_bytes(path.read_bytes());os.utime(replacement,ns=(old.st_atime_ns,old.st_mtime_ns));replacement.replace(path)
    assert path.stat().st_size==old.st_size and path.stat().st_mtime_ns==old.st_mtime_ns
    with pytest.raises(ValueError,match='input files changed'):identity.assert_current(manifest,clock)


def test_symlink_target_change_is_detected(inputs):
    manifest,clock=inputs;path=manifest.parent/'station-1.vdif'
    a=path.with_suffix('.a');b=path.with_suffix('.b');path.rename(a);b.write_bytes(a.read_bytes());path.symlink_to(a.name)
    identity=InputIdentity(manifest,clock);path.unlink();path.symlink_to(b.name)
    with pytest.raises(ValueError,match='input files changed'):identity.assert_current(manifest,clock)


def test_identity_is_bound_to_paths_and_loaded_configuration(inputs):
    manifest,clock=inputs;identity=InputIdentity(manifest,clock);copy=clock.with_name('other.json');copy.write_bytes(clock.read_bytes())
    with pytest.raises(ValueError,match='different input paths'):identity.assert_current(manifest,copy)
    config=load_session(manifest);config['sample_rate_hz']*=2
    with pytest.raises(ValueError,match='loaded configuration'):identity.assert_current(manifest,clock,config)
    with pytest.raises(ValueError,match='before identity capture'):InputIdentity(manifest,clock,expected_config=config)


def test_change_during_hashing_and_missing_input_reject_identity(inputs,monkeypatch):
    import vsora_correlator.input_identity as module
    manifest,clock=inputs;digest=module.digest_file
    def mutate(path):
        result=digest(path)
        if path==manifest.resolve():clock.write_bytes(clock.read_bytes()+b' ')
        return result
    monkeypatch.setattr(module,'digest_file',mutate)
    with pytest.raises(ValueError,match='input files changed'):InputIdentity(manifest,clock)
    monkeypatch.setattr(module,'digest_file',digest);identity=InputIdentity(manifest,clock);clock.unlink()
    with pytest.raises(ValueError,match='unavailable'):identity.assert_current(manifest,clock)


def test_no_caller_supplied_digest_dictionary(tmp_path):
    with pytest.raises(TypeError,match='InputIdentity'):
        process_closure_session(tmp_path/'m.json',tmp_path/'c.json',tmp_path/'out',_source_identity={'sha256':'claimed'})


def test_explicit_limit_vdif_change_hidden_from_all_stat_fields(inputs,monkeypatch):
    import vsora_correlator.input_identity as module
    manifest,clock=inputs;identity=InputIdentity(manifest,clock)
    monkeypatch.setattr(module,'snapshot_paths',lambda paths:identity._snapshot.copy())
    path=manifest.parent/'station-1.vdif';data=bytearray(path.read_bytes());data[-1]^=1;path.write_bytes(data)
    identity.assert_current(manifest,clock) # Intentionally not a full VDIF rehash.
    assert hashlib.sha256(path.read_bytes()).hexdigest()!=identity.public_identity['input_vdif'][0]['sha256']
    assert 'preserve all stat fields' in identity.diagnostics['limits']


def test_standalone_pipeline_stops_when_input_changes_after_stage(tmp_path):
    make_fixture(tmp_path/'input',seed=23);manifest=tmp_path/'input/manifest.json';clock=tmp_path/'input/clock.json'
    def mutate(step,done):
        if step=='model_free_rate':
            stat=clock.stat();os.utime(clock,ns=(stat.st_atime_ns,stat.st_mtime_ns+1_000_000))
    with pytest.raises(ValueError,match='input files changed'):
        process_closure_session(manifest,clock,tmp_path/'changed',correlation_only=True,progress=mutate)
    assert not (tmp_path/'changed').exists() and not (tmp_path/'changed.partial/correlation').exists()
    failure=json.loads((tmp_path/'changed.partial/failure.json').read_text())
    assert failure['state']=='incomplete' and failure['completed_steps']==['aligned_pilot','model_free_rate']
