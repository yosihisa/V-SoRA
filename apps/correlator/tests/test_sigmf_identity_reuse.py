"""Closed-file, same-run derived identity: real digest calls and refusals."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

import numpy as np
import pytest

from vsora_correlator.aligned import correlate_aligned
from vsora_correlator.input_identity import InputIdentity
from vsora_correlator.session import load_session
from workflows.vdif_closure_validation import make_fixture


@pytest.fixture
def inputs(tmp_path):
    original=tmp_path/'vdif';make_fixture(original,frame_count=1)
    root=tmp_path/'source';child=tmp_path/'child';root.mkdir();child.mkdir()
    c=json.loads((original/'manifest.json').read_text())
    obs=json.loads((original/'observation.json').read_text())
    for name in ['observation.json','clock.json']:shutil.copy2(original/name,root/name)
    stations=[]
    for index,station in enumerate(c['stations']):
        stem=f'station-{index+1}'
        meta={'global':{'core:version':'1.2.0','core:datatype':'ci16_le','core:sample_rate':c['sample_rate_hz']},
              'captures':[{'core:sample_start':0,'core:frequency':obs['observation']['frequency_hz'],
                           'core:datetime':obs['observation']['start_utc']}],'annotations':[]}
        (root/(stem+'.sigmf-meta')).write_text(json.dumps(meta))
        (np.arange(4096,dtype=np.int16)+index*1000).astype('<i2').tofile(root/(stem+'.sigmf-data'))
        stations.append({'id':station['id'],'sigmf':stem+'.sigmf-meta'})
    c.update(input_format='sigmf_ci16_le',stations=stations)
    (root/'manifest.json').write_text(json.dumps(c))
    d=json.loads(json.dumps(c));d['blocks_per_integration']=4
    for station in d['stations']:station['sigmf']=str(root/station['sigmf'])
    shutil.copy2(root/'observation.json',child/'observation.json')
    (child/'manifest.json').write_text(json.dumps(d))
    return root,child,original


def edit(path,change):
    c=json.loads(path.read_text());change(c);path.write_text(json.dumps(c))


def test_real_full_hash_reads_once_and_child_uses_own_control_SHA(inputs,monkeypatch):
    from vsora_correlator import input_identity as module
    root,child,_=inputs;calls=[];digest=module.digest_file
    def count(path):calls.append(path);return digest(path)
    monkeypatch.setattr(module,'digest_file',count)
    source=InputIdentity(root/'manifest.json',root/'clock.json')
    view=source.bind_sigmf_session(child/'manifest.json',root/'clock.json',load_session(child/'manifest.json',allow_sigmf=True))
    assert len([p for p in calls if p.suffix=='.sigmf-data'])==4
    assert view.public_identity['input_sigmf']==source.public_identity['input_sigmf']
    assert view.public_identity['input_manifest_sha256']==hashlib.sha256((child/'manifest.json').read_bytes()).hexdigest()
    assert view.public_identity['input_manifest_sha256']!=source.public_identity['input_manifest_sha256']
    assert view.diagnostics['sigmf_data_hash_file_reads']==0
    count_small=len(calls);view.assert_current(child/'manifest.json',root/'clock.json')
    assert len(calls)>count_small and len([p for p in calls if p.suffix=='.sigmf-data'])==4
    public=view.public_identity;public['input_sigmf'][0]['data']['sha256']='untrusted'
    assert view.public_identity['input_sigmf'][0]['data']['sha256']!='untrusted'
    InputIdentity(root/'manifest.json',root/'clock.json')
    assert len([p for p in calls if p.suffix=='.sigmf-data'])==8


@pytest.mark.parametrize('change',[
    lambda c:c.update(fft_length=64),lambda c:c.update(sample_rate_hz=4096000),
    lambda c:c.update(voltage_unit='sqrt(Jy)'),lambda c:c.update(phase_center_correction=False),
    lambda c:c.update(integrations_per_shard=1),lambda c:c['stations'].reverse(),
    lambda c:c['spectral_quality'].update(channel_weights=False),
])
def test_child_configuration_changes_are_not_a_reuse_authority(inputs,change):
    root,child,_=inputs;source=InputIdentity(root/'manifest.json',root/'clock.json')
    edit(child/'manifest.json',change)
    with pytest.raises(ValueError):source.bind_sigmf_session(child/'manifest.json',root/'clock.json')


def test_same_byte_copied_pairs_clock_and_changed_geometry_rejected(inputs):
    root,child,_=inputs;source=InputIdentity(root/'manifest.json',root/'clock.json')
    clock=child/'clock.json';shutil.copy2(root/'clock.json',clock)
    with pytest.raises(ValueError,match='clock path'):source.bind_sigmf_session(child/'manifest.json',clock)
    edit(child/'observation.json',lambda c:c['site'].update(height_m=1.))
    with pytest.raises(ValueError,match='configuration'):source.bind_sigmf_session(child/'manifest.json',root/'clock.json')
    shutil.copy2(root/'observation.json',child/'observation.json')
    for suffix in ['.sigmf-meta','.sigmf-data']:shutil.copy2(root/('station-1'+suffix),child/('copied'+suffix))
    edit(child/'manifest.json',lambda c:c['stations'][0].update(sigmf=str(child/'copied.sigmf-meta')))
    with pytest.raises(ValueError,match='pairs differ'):source.bind_sigmf_session(child/'manifest.json',root/'clock.json')


@pytest.mark.parametrize('scope,name',[
    ('source','station-1.sigmf-meta'),('source','clock.json'),
    ('child','manifest.json'),('child','observation.json')])
def test_parent_and_child_small_file_changes_rejected(inputs,scope,name):
    root,child,_=inputs;source=InputIdentity(root/'manifest.json',root/'clock.json')
    view=source.bind_sigmf_session(child/'manifest.json',root/'clock.json')
    path=(root if scope=='source' else child)/name;path.write_text(path.read_text()+' ')
    with pytest.raises(ValueError,match='changed'):view.assert_current(child/'manifest.json',root/'clock.json')


def test_parent_metadata_rehash_detects_content_when_stat_is_held(inputs,monkeypatch):
    from vsora_correlator import input_identity as module
    root,child,_=inputs;source=InputIdentity(root/'manifest.json',root/'clock.json')
    view=source.bind_sigmf_session(child/'manifest.json',root/'clock.json')
    monkeypatch.setattr(module,'snapshot_paths',lambda paths:source._snapshot.copy())
    path=root/'station-1.sigmf-meta';path.write_text(path.read_text()+' ')
    with pytest.raises(ValueError,match='metadata content'):view.assert_current(child/'manifest.json',root/'clock.json')


def test_raw_ordinary_change_and_symlink_retarget_rejected(inputs):
    root,child,_=inputs;raw=root/'station-1.sigmf-data';a=raw.with_suffix('.a');b=raw.with_suffix('.b')
    raw.rename(a);b.write_bytes(a.read_bytes());raw.symlink_to(a.name)
    source=InputIdentity(root/'manifest.json',root/'clock.json');view=source.bind_sigmf_session(child/'manifest.json',root/'clock.json')
    raw.unlink();raw.symlink_to(b.name)
    with pytest.raises(ValueError,match='changed'):view.assert_current(child/'manifest.json',root/'clock.json')
    raw.unlink();raw.symlink_to(a.name)
    source=InputIdentity(root/'manifest.json',root/'clock.json');view=source.bind_sigmf_session(child/'manifest.json',root/'clock.json')
    before=a.stat();time.sleep(.02);data=bytearray(a.read_bytes());data[-1]^=1;a.write_bytes(data)
    os.utime(a,ns=(before.st_atime_ns,before.st_mtime_ns))
    assert a.stat().st_ctime_ns!=before.st_ctime_ns
    with pytest.raises(ValueError,match='changed'):view.assert_current(child/'manifest.json',root/'clock.json')


def test_same_stat_raw_change_remains_an_explicit_limit(inputs,monkeypatch):
    from vsora_correlator import input_identity as module
    root,child,_=inputs;source=InputIdentity(root/'manifest.json',root/'clock.json')
    view=source.bind_sigmf_session(child/'manifest.json',root/'clock.json')
    monkeypatch.setattr(module,'snapshot_paths',lambda paths:source._snapshot.copy() if paths==source._paths else view._snapshot.copy())
    path=root/'station-1.sigmf-data';data=bytearray(path.read_bytes());data[-1]^=1;path.write_bytes(data)
    view.assert_current(child/'manifest.json',root/'clock.json')
    assert hashlib.sha256(path.read_bytes()).hexdigest()!=view.public_identity['input_sigmf'][0]['data']['sha256']
    assert 'all stat fields' in view.diagnostics['limits']


def test_reuse_types_and_VDIF_are_rejected(inputs,tmp_path):
    root,child,original=inputs
    with pytest.raises(TypeError,match='live InputIdentity'):
        correlate_aligned('absent','absent',tmp_path/'out',1,_source_identity={'sha256':'claimed'})
    source=InputIdentity(original/'manifest.json',original/'clock.json')
    with pytest.raises(ValueError,match='SigMF source'):source.bind_sigmf_session(child/'manifest.json',root/'clock.json')
    with pytest.raises(ValueError,match='SigMF-only'):
        correlate_aligned(original/'manifest.json',original/'clock.json',tmp_path/'out',1,_source_identity=source)


def test_reused_direct_checks_parent_during_integration(inputs,tmp_path,monkeypatch):
    from vsora_correlator import aligned
    root,child,_=inputs;source=InputIdentity(root/'manifest.json',root/'clock.json');finish=aligned.FXAccumulator.finish
    def mutate(self,*args):
        result=finish(self,*args);path=root/'station-1.sigmf-meta';path.write_text(path.read_text()+' ');return result
    monkeypatch.setattr(aligned.FXAccumulator,'finish',mutate)
    with pytest.raises(ValueError,match='changed'):
        correlate_aligned(child/'manifest.json',root/'clock.json',tmp_path/'out',1,start_offset_s=.0002,_source_identity=source)
    assert not (tmp_path/'out').exists() and (tmp_path/'out.partial/failure.json').exists()
