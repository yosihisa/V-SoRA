"""Synthetic multi-window connection; no image fitting or receiver claim."""
import json
from pathlib import Path
import time

import pytest

from vsora_correlator.sequence import process_sequence, _plan_windows
from vsora_correlator.closure_pipeline import process_closure_session
from vsora_correlator.input_identity import InputIdentity
from workflows.vdif_closure_validation import make_fixture
from workflows.sigmf_pipeline_validation import prepare


@pytest.fixture
def inputs(tmp_path):
    make_fixture(tmp_path/'stored',frame_count=140,seed=231)
    prepare(tmp_path/'stored',tmp_path/'input',frame_count=140)
    return tmp_path/'input'


def options():
    return dict(window_count=2,pilot_integrations=64,integration_s=.1,
                max_rate_hz=100.,correlation_only=True,save_bispectrum=True)


def test_actual_sequence_identifies_once_and_saves_windows_without_synthesis(inputs,tmp_path,monkeypatch):
    from vsora_correlator import input_identity
    import vsora_imaging.synthesis as synthesis
    calls=[];digest=input_identity.digest_file
    def count(path):calls.append(Path(path));return digest(path)
    def forbidden(*a,**k):raise AssertionError('correlation-only must not synthesize')
    monkeypatch.setattr(input_identity,'digest_file',count)
    monkeypatch.setattr(synthesis,'image_synthesis',forbidden)
    import vsora_correlator.sequence as sequence
    monkeypatch.setattr(sequence,'_validate_sequence_fourier_size',forbidden)
    out=tmp_path/'result'
    result=process_sequence(inputs/'manifest.json',inputs/'clock.json',out,**options())
    assert result['completed_windows']==[0,1] and result['completed_steps']==result['total_steps']==6
    assert result['phase']=='correlations_saved' and result['correlation_only']
    assert result['closures'] is result['rml'] is result['synthesis'] is None
    assert not (out/'synthesis').exists() and 'input_vdif' not in result
    assert result['nominal_correlation_exposure_per_station_s']==pytest.approx(.2)
    assert 'nominal_image_exposure_per_station_s' not in result
    assert len([p for p in calls if p.suffix=='.sigmf-data'])==4
    assert result['input_identity']['sigmf_data_hash_bytes']==4*140*4096*4
    assert result['input_identity']['sequence_data_full_sha_passes_per_station']==1
    for i in range(2):
        child=json.loads((out/f'window-{i:04d}/summary.json').read_text())
        assert child['input_sigmf']==result['input_sigmf']
        assert child['input_identity']['reuse_mode']=='shared_sequence_snapshot'
        assert child['input_identity']['pipeline_data_hash_file_reads']==4
        assert 'do not sum' in child['input_identity']['hash_accounting_scope']
        assert all(x['sigmf_data_hash_file_reads']==0 for x in child['input_identity']['direct_subruns'])
    with pytest.raises(FileExistsError):process_sequence(inputs/'manifest.json',inputs/'clock.json',out,**options())


def test_sigmf_final_uses_fft_grid_not_vdif_grid(inputs,tmp_path):
    result=process_sequence(inputs/'manifest.json',inputs/'clock.json',tmp_path/'result',
        **{**options(),'integration_s':.100015625,'save_bispectrum':False})
    assert len(result['windows'])==2 and result['synthesis'] is None
    with pytest.raises(ValueError,match='FFT blocks'):
        process_sequence(inputs/'manifest.json',inputs/'clock.json',tmp_path/'bad',
            **{**options(),'integration_s':.10001})
    assert not (tmp_path/'bad.partial').exists()


@pytest.mark.parametrize('name',['manifest.json','clock.json','observation.json','station-1.sigmf-meta','station-1.sigmf-data'])
def test_between_window_changes_keep_completed_window_and_stop(inputs,tmp_path,monkeypatch,name):
    import vsora_correlator.sequence as sequence
    original=sequence.process_closure_session;calls=[]
    def changed(*args,**kwargs):
        calls.append(1)
        if len(calls)==2:
            path=inputs/name;time.sleep(.02)
            if path.suffix=='.sigmf-data':
                data=bytearray(path.read_bytes());data[-1]^=1;path.write_bytes(data)
            else:path.write_text(path.read_text()+' ')
        return original(*args,**kwargs)
    monkeypatch.setattr(sequence,'process_closure_session',changed)
    with pytest.raises(ValueError,match='changed'):
        process_sequence(inputs/'manifest.json',inputs/'clock.json',tmp_path/'bad',**options())
    partial=tmp_path/'bad.partial';failure=json.loads((partial/'failure.json').read_text())
    assert failure['state']=='incomplete' and failure['completed_windows']==[0]
    assert (partial/'window-0000/correlation/shard-00000.npz').exists()
    assert not (partial/'window-0001/correlation').exists() and not (partial/'synthesis').exists()


def test_short_input_preserves_first_completed_window(inputs,tmp_path):
    for p in inputs.glob('*.sigmf-data'):
        with p.open('r+b') as stream:stream.truncate(70*4096*4)
    with pytest.raises(ValueError,match='input ends'):
        process_sequence(inputs/'manifest.json',inputs/'clock.json',tmp_path/'short',**options())
    state=json.loads((tmp_path/'short.partial/failure.json').read_text())
    assert state['completed_windows']==[0] and not (tmp_path/'short').exists()


@pytest.mark.parametrize('value',[None,0,1,'yes'])
def test_explicit_bool_gate_precedes_input_access(tmp_path,value):
    with pytest.raises(ValueError,match='correlation_only bool'):
        process_sequence('missing','missing',tmp_path/'bad',correlation_only=value)
    assert not (tmp_path/'bad.partial').exists()


def test_shared_pipeline_rejects_wrong_parent_and_digest_claim(inputs,tmp_path):
    identity=InputIdentity(inputs/'legacy.json',inputs/'clock.json')
    for parent,error in [(identity,ValueError),({'sha256':'claim'},TypeError)]:
        with pytest.raises(error):
            process_closure_session(inputs/'manifest.json',inputs/'clock.json',tmp_path/type(parent).__name__,
                correlation_only=True,pilot_integrations=64,integration_s=.1,_source_identity=parent)


def test_sequence_sigmf_planning_still_rejects_overlap_counts_and_cell_capacity():
    c={'sample_rate_hz':2048000,'fft_length':32,'blocks_per_integration':128,
       'stations':[{}]*4,'input_format':'sigmf_ci16_le'}
    for count,step,match in [(1,None,'2..64'),(65,None,'2..64'),(2,.1,'overlap')]:
        with pytest.raises(ValueError,match=match):_plan_windows(c,count,step,.002,64,None,.1)
    with pytest.raises(ValueError,match='one million spectral'):
        _plan_windows({**c,'fft_length':8192,'blocks_per_integration':1},32,None,.002,32,None,.1)
