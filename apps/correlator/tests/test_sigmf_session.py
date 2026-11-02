"""Explicit SigMF session contracts, using distinct synthetic station bytes."""
import json
import os
import time
from pathlib import Path
from astropy.time import Time
import astropy.units as u

import numpy as np
import pytest

from vsora_correlator.aligned import correlate_aligned
from vsora_correlator.input_identity import InputIdentity
from vsora_correlator.session import load_session, correlate_session
from vsora_formats.spectral import load_spectral
from workflows.vdif_closure_validation import make_fixture


@pytest.fixture
def inputs(tmp_path):
    root = tmp_path/'input'; make_fixture(root, frame_count=1)
    manifest = json.loads((root/'manifest.json').read_text())
    obs = json.loads((root/'observation.json').read_text())
    # 20 MHz deliberately fails the VDIF frame-rate divisibility contract.
    fs = 20000000
    obs['observation']['start_utc'] = '2024-07-30T09:19:20.197123456Z'
    (root/'observation.json').write_text(json.dumps(obs))
    for index, station in enumerate(manifest['stations']):
        meta = {'global': {'core:version':'1.2.0','core:datatype':'ci16_le','core:sample_rate':fs},
                'captures':[{'core:sample_start':0,'core:frequency':obs['observation']['frequency_hz'],
                             'core:datetime':obs['observation']['start_utc']}], 'annotations':[]}
        stem = f's{index}'
        (root/(stem+'.sigmf-meta')).write_text(json.dumps(meta))
        # Different stored integer signals, not copies of one telescope.
        values = (np.arange(16384, dtype=np.int16)*(index+1)).astype('<i2')
        values.tofile(root/(stem+'.sigmf-data'))
        station.clear(); station.update(id=obs['stations'][index]['id'],sigmf=stem+'.sigmf-meta')
    manifest.update(input_format='sigmf_ci16_le',sample_rate_hz=fs,fft_length=32,blocks_per_integration=4)
    (root/'manifest.json').write_text(json.dumps(manifest))
    clock = {'schema_version':1,'max_abs_baseband_hz':fs*.2,'stations':[
        {'id':s['id'],'input_start_offset_s':0.,'actual_sample_rate_hz':fs*(1+index*.0001)}
        for index,s in enumerate(manifest['stations'])]}
    (root/'clock.json').write_text(json.dumps(clock))
    return root


def edit(root, filename, change):
    path=root/filename; value=json.loads(path.read_text()); change(value); path.write_text(json.dumps(value))


def test_fractional_epoch_20MHz_explicit_rates_and_pair_identity(inputs, tmp_path):
    c=load_session(inputs/'manifest.json',allow_sigmf=True)
    assert c['sample_rate_hz']==20000000
    identity=InputIdentity(inputs/'manifest.json',inputs/'clock.json',c)
    assert len(identity.public_identity['input_sigmf'])==4
    assert identity.diagnostics['sigmf_data_hash_file_reads']==4
    identity.assert_current(inputs/'manifest.json',inputs/'clock.json',c)
    assert identity.diagnostics['sigmf_data_hash_file_reads']==4
    result=correlate_aligned(inputs/'manifest.json',inputs/'clock.json',tmp_path/'result',1,start_offset_s=.0001)
    cube=load_spectral(tmp_path/'result/shard-00000.npz')
    assert result['input_identity']==identity.public_identity
    assert cube['metadata']['visibility_unit']=='ADC^2'
    assert abs((Time(cube['metadata']['time_origin_utc'])-Time('2024-07-30T09:19:20.197123456Z')).to_value(u.s))<1e-9
    assert cube['valid_fft_count'].max()==4
    assert 'vdif_read_mode' not in result and result['input_format']=='sigmf_ci16_le'


@pytest.mark.parametrize('change', [
    lambda c:c.update(input_format='unknown'),
    lambda c:c.update(voltage_unit='sqrt(Jy)'),
    lambda c:c['stations'][0].update(decoded_voltage_scale=1),
    lambda c:c['stations'][0].update(sigmf=1),
    lambda c:c['stations'][0].update(id='wrong'),
    lambda c:c.update(sample_rate_hz=2048000),
])
def test_manifest_contract_rejects(inputs,change):
    edit(inputs,'manifest.json',change)
    with pytest.raises((ValueError,FileNotFoundError)):
        load_session(inputs/'manifest.json',allow_sigmf=True)


@pytest.mark.parametrize('filename,key,value,match',[
    ('s0.sigmf-meta','core:frequency',1,'RF center'),
    ('s0.sigmf-meta','core:datetime','2024-07-30T09:19:20.197123466Z','capture epoch'),
    ('clock.json','actual_sample_rate_hz',True,'clock'),
    ('clock.json','actual_sample_rate_hz',20030000,'clock'),
    ('clock.json','input_start_offset_s',.001,'capture epoch'),
])
def test_metadata_and_clock_disagreement_rejects_before_output(inputs,tmp_path,filename,key,value,match):
    if filename.endswith('.sigmf-meta'):
        edit(inputs,filename,lambda c:c['captures'][0].update({key:value}))
    else:edit(inputs,filename,lambda c:c['stations'][0].update({key:value}))
    with pytest.raises(ValueError,match=match):
        correlate_aligned(inputs/'manifest.json',inputs/'clock.json',tmp_path/'result',1)
    assert not (tmp_path/'result').exists() and not (tmp_path/'result.partial').exists()


def test_duplicate_physical_file_and_copied_SHA_rejected(inputs):
    first=inputs/'s0.sigmf-data'; second=inputs/'s1.sigmf-data'
    second.unlink();second.symlink_to(first.name)
    with pytest.raises(ValueError,match='distinct data files'):load_session(inputs/'manifest.json',allow_sigmf=True)
    second.unlink();second.write_bytes(first.read_bytes())
    with pytest.raises(ValueError,match='SHA must be distinct'):InputIdentity(inputs/'manifest.json',inputs/'clock.json')


def test_metadata_and_data_cannot_be_same_physical_file(inputs):
    meta=inputs/'s0.sigmf-meta';data=inputs/'s0.sigmf-data'
    meta.write_text(meta.read_text()+' '*(-meta.stat().st_size%4))
    data.unlink();os.link(meta,data)
    with pytest.raises(ValueError,match='metadata and data must be distinct'):
        InputIdentity(inputs/'manifest.json',inputs/'clock.json')


@pytest.mark.parametrize('name',['s0.sigmf-meta','s0.sigmf-data','clock.json'])
def test_boundary_rejects_mutation(inputs,name):
    identity=InputIdentity(inputs/'manifest.json',inputs/'clock.json');path=inputs/name
    old=path.stat();time.sleep(.02)
    data=bytearray(path.read_bytes());data[-1]^=1;path.write_bytes(data)
    os.utime(path,ns=(old.st_atime_ns,old.st_mtime_ns))
    assert path.stat().st_ctime_ns!=old.st_ctime_ns
    with pytest.raises(ValueError,match='changed'):identity.assert_current(inputs/'manifest.json',inputs/'clock.json')


def test_metadata_rehashed_even_when_stat_guard_is_unchanged(inputs,monkeypatch):
    from vsora_correlator import input_identity
    identity=InputIdentity(inputs/'manifest.json',inputs/'clock.json')
    monkeypatch.setattr(input_identity,'snapshot_paths',lambda paths:identity._snapshot)
    path=inputs/'s0.sigmf-meta';path.write_text(path.read_text()+' ')
    with pytest.raises(ValueError,match='metadata content'):identity.assert_current(inputs/'manifest.json',inputs/'clock.json')


def test_direct_correlation_checks_each_integration_and_keeps_partial(inputs,tmp_path,monkeypatch):
    from vsora_correlator import aligned
    original=aligned.FXAccumulator.finish
    def mutate(self,*args):
        result=original(self,*args)
        path=inputs/'s0.sigmf-meta';path.write_text(path.read_text()+' ')
        return result
    monkeypatch.setattr(aligned.FXAccumulator,'finish',mutate)
    with pytest.raises(ValueError,match='changed'):
        correlate_aligned(inputs/'manifest.json',inputs/'clock.json',tmp_path/'result',1,start_offset_s=.0001)
    assert not (tmp_path/'result').exists()
    assert json.loads((tmp_path/'result.partial/failure.json').read_text())['state']=='incomplete'


def test_unaligned_entry_explicitly_rejects_and_single_station_is_insufficient(inputs,tmp_path):
    with pytest.raises(ValueError,match='requires correlate-aligned'):
        correlate_session(inputs/'manifest.json',tmp_path/'result')
    edit(inputs,'manifest.json',lambda c:c.update(stations=c['stations'][:1]))
    with pytest.raises(ValueError,match='station count'):load_session(inputs/'manifest.json',allow_sigmf=True)
    assert not (tmp_path/'result').exists()
