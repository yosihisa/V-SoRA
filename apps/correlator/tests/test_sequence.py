import json
import os
import numpy as np
import pytest
from vsora_correlator.sequence import plan_windows,process_sequence
from vsora_formats.spectral import load_spectral
from workflows.vdif_closure_validation import make_fixture
from workflows.sequence_validation import RATES


def config():
    return {'sample_rate_hz':2048000,'fft_length':32,'blocks_per_integration':128,'stations':[{}, {}, {}, {}]}


def test_window_plan_and_coverage():
    plan=plan_windows(config(),3,.512,.002,256,None,.3)
    assert plan[2]['start_offset_s']==pytest.approx(1.026)
    assert plan[2]['pilot_end_s']==pytest.approx(1.538)
    assert plan_windows(config(),3,None,.002,256,None,.3)==plan
    with pytest.raises(ValueError,match='finite pilot'):plan_windows(config(),3,None,.002,256,float('nan'),.3)
    with pytest.raises(ValueError,match='whole VDIF'):plan_windows(config(),3,None,.002,256,None,.155)
    with pytest.raises(ValueError,match='overlap'):plan_windows(config(),3,.5,.002,256,None,.3)
    with pytest.raises(ValueError,match='covered'):plan_windows(config(),3,.512,.002,256,None,1.)
    with pytest.raises(ValueError,match='2..64'):plan_windows(config(),True,.512,.002,256,None,.3)
    with pytest.raises(ValueError,match='frame grid'):plan_windows(config(),3,.512,.002,256,.0003,.3)


def test_sequence_local_rates_and_relative_synthesis(tmp_path):
    make_fixture(tmp_path/'input',seed=32,frame_count=800,
        rate_changes=[{'start_s':.514,'rates_hz':RATES[1]},{'start_s':1.026,'rates_hz':RATES[2]}])
    result=process_sequence(tmp_path/'input/manifest.json',tmp_path/'input/clock.json',tmp_path/'complete',
        window_count=3,step_s=.512,starts=1,max_iterations=100)
    assert result['state']=='complete' and result['completed_windows']==[0,1,2]
    assert result['completed_steps']==result['total_steps']==10
    assert result['nominal_image_exposure_per_station_s']==pytest.approx(.9)
    assert result['selected_pilot_start_to_end_span_s']==pytest.approx(1.536)
    for i,row in enumerate(result['windows']):
        assert max(abs(np.array(row['rate_estimate']['station_rates_hz'])-RATES[i]))<.05
        child=json.loads((tmp_path/f'complete/window-{i:04d}/summary.json').read_text())
        assert child['type']=='short_rate_correlation' and child['rml'] is None and child['closures'] is None
        assert len(child['completed_steps'])==3
    data=load_spectral(tmp_path/'complete/synthesis/visibility.npz')
    assert data['metadata']['visibility_unit']=='ADC^2' and data['visibilities'].shape[0]==3
    assert np.allclose(data['integration_s'].sum(axis=0),.9)
    assert result['rml']['amplitude_constraints_available']
    with pytest.raises(FileExistsError):process_sequence(tmp_path/'input/manifest.json',tmp_path/'input/clock.json',tmp_path/'complete')


def test_sequence_stops_and_keeps_completed_window_on_short_input(tmp_path):
    make_fixture(tmp_path/'input',seed=23)
    with pytest.raises(ValueError,match='input ends'):
        process_sequence(tmp_path/'input/manifest.json',tmp_path/'input/clock.json',tmp_path/'short',window_count=2)
    assert not (tmp_path/'short').exists()
    state=json.loads((tmp_path/'short.partial/failure.json').read_text())
    assert state['state']=='incomplete' and state['completed_windows']==[0] and state['current_window_index']==1
    assert (tmp_path/'short.partial/window-0000/correlation/shard-00000.npz').exists()
    assert not (tmp_path/'short.partial/synthesis').exists()


def test_sequence_rejects_changed_input_even_with_same_bytes(tmp_path):
    make_fixture(tmp_path/'input',seed=23);clock=tmp_path/'input/clock.json'
    def touch(label,done):
        if label=='window_0:rate_corrected_short_correlation':
            stat=clock.stat();os.utime(clock,ns=(stat.st_atime_ns,stat.st_mtime_ns+1_000_000))
    with pytest.raises(ValueError,match='input files changed'):
        process_sequence(tmp_path/'input/manifest.json',clock,tmp_path/'changed',window_count=2,progress=touch)
    assert not (tmp_path/'changed').exists()
    state=json.loads((tmp_path/'changed.partial/failure.json').read_text())
    assert state['state']=='incomplete' and state['current_window_index']==0


def test_synthesis_failure_is_distinguished_from_window_failure(tmp_path,monkeypatch):
    import vsora_correlator.sequence as sequence
    import vsora_imaging.synthesis as synthesis
    make_fixture(tmp_path/'input',seed=23,frame_count=16)
    def fake_window(*args,**kwargs):
        return {'input_manifest_sha256':'m','input_clock_sha256':'c','input_observation_sha256':'o',
                'input_vdif':[],'rate_estimate':{},'rate_acquisition':{},'correlation':{}}
    def fail_synthesis(*args,**kwargs):raise RuntimeError('synthetic synthesis-only unit failure')
    monkeypatch.setattr(sequence,'process_closure_session',fake_window);monkeypatch.setattr(synthesis,'image_synthesis',fail_synthesis)
    with pytest.raises(RuntimeError,match='unit failure'):
        process_sequence(tmp_path/'input/manifest.json',tmp_path/'input/clock.json',tmp_path/'failed-image',window_count=2)
    state=json.loads((tmp_path/'failed-image.partial/failure.json').read_text())
    assert state['completed_windows']==[0,1] and state['current_window_index'] is None
    assert state['phase']=='synthesis' and not (tmp_path/'failed-image').exists()
