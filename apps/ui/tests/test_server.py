import json
from pathlib import Path
import time
import pytest
pytest.importorskip('fastapi')
pytest.importorskip('httpx')
from fastapi.testclient import TestClient
from vsora_ui.server import create_app
from vsora_ui.jobs import JobManager,write_json
from vsora_ui.models import SimulationRequest


HEADERS={'X-VSoRA-Request':'1'}


def wait(client,job_id,timeout=25):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        d=client.get('/api/jobs/'+job_id).json()
        if d['state'] not in ('queued','running'): return d
        time.sleep(.1)
    raise AssertionError('GUI scientific job timed out')


def test_japanese_home_and_local_request_policy(tmp_path):
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as c:
        home=c.get('/');assert home.status_code==200 and '模擬観測から画像を作る' in home.text
        assert "frame-ancestors 'none'" in home.headers['content-security-policy']
        assert c.post('/api/jobs',json={'kind':'simulation'}).status_code==403
        assert c.post('/api/jobs',json={'kind':'simulation'},headers={**HEADERS,'Origin':'https://example.invalid'}).status_code==403
        assert c.get('/',headers={'Host':'example.invalid'}).status_code==400


def test_simulation_job_real_subprocess_and_artifact(tmp_path):
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as c:
        r=c.post('/api/jobs',json={'kind':'simulation','stations':4,'duration_s':600,'integration_s':60},headers=HEADERS)
        assert r.status_code==202;job=r.json()['id'];d=wait(c,job)
        assert d['state']=='complete',d
        assert d['summary']['imaging']['converged']
        assert abs(d['summary']['imaging']['image_peak_jy']-1000)<1e-6
        picture=c.get(f'/api/jobs/{job}/artifacts/imaging/images.png')
        assert picture.status_code==200 and picture.headers['content-type']=='image/png'
        assert c.get(f'/api/jobs/{job}/artifacts/../../../../pyproject.toml').status_code==404
        assert c.post(f'/api/jobs/{job}/cancel',headers=HEADERS).json()['state']=='complete'


@pytest.mark.parametrize('validation',['closure','rate'])
def test_closure_validation_real_subprocess(tmp_path,validation):
    (tmp_path/'tools').mkdir()
    (tmp_path/'tools/run.py').symlink_to(Path(__file__).resolve().parents[3]/'tools/run.py')
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as c:
        r=c.post('/api/jobs',json={'kind':'validation','validation':validation},headers=HEADERS)
        assert r.status_code==202
        d=wait(c,r.json()['id'])
        assert d['state']=='complete',d
        if validation=='closure':
            assert d['summary']['actual_iq_fx']['corrected_max_logcamp_error'] < 1e-12
        else:
            assert d['summary']['maximum_rate_error_hz']<.05
            assert not d['summary']['estimate']['amplitude_or_sky_phase_calibration']


def test_rml_simulation_real_subprocess(tmp_path):
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as c:
        r=c.post('/api/jobs',json={'kind':'rml','model':'double','stations':4,'snapshots':8,
                                 'starts':1,'max_iterations':100},headers=HEADERS)
        assert r.status_code==202
        d=wait(c,r.json()['id'])
        assert d['state']=='complete',d
        assert d['summary']['coherent_integration_s']==.3
        assert not d['summary']['rml']['absolute_flux_measured']
        assert d['summary']['rml']['input_unit']=='ADC^2'


def test_vdif_analysis_real_subprocess(tmp_path):
    from workflows.vdif_closure_validation import make_fixture
    make_fixture(tmp_path/'input',23)
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as c:
        r=c.post('/api/jobs',json={'kind':'analysis','manifest':'input/manifest.json','clock_model':'input/clock.json',
                                  'starts':1,'max_iterations':100},headers=HEADERS)
        assert r.status_code==202
        d=wait(c,r.json()['id'])
        assert d['state']=='complete',d
        assert d['summary']['rml']['input_unit']=='ADC^2'
        assert d['completed_steps']==5 and d['summary']['closures']['phase_valid']>0
        assert d['summary']['rate_consistency_policy']=='report'
        assert not d['summary']['rate_consistency']['coherence_stability_measured']


@pytest.mark.parametrize('payload',[
    {'kind':'simulation','duration_s':61}, {'kind':'simulation','noise':1},
    {'kind':'simulation','extra_command':'sh'}, {'kind':'simulation','flux_jy':0},
    {'kind':'simulation','duration_s':14400,'integration_s':5}, {'kind':'validation','validation':'unknown'}])
def test_invalid_requests_are_rejected(tmp_path,payload):
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as c:
        assert c.post('/api/jobs',json=payload,headers=HEADERS).status_code==422
        assert c.get('/api/jobs').json()==[]


def test_restart_marks_unfinished_job_interrupted(tmp_path):
    root=tmp_path/'outputs/gui/20261002T000000-1234abcd';root.mkdir(parents=True)
    write_json(root/'status.json',{'id':root.name,'state':'running','phase':'old'})
    manager=JobManager(tmp_path)
    try: assert manager.status(root.name)['state']=='interrupted'
    finally: manager.close()


def test_queued_cancel_does_not_start_worker(tmp_path):
    manager=JobManager(tmp_path)
    # Occupy the only executor slot without starting a scientific process.
    import threading
    gate=threading.Event();block=manager.executor.submit(gate.wait)
    try:
        result=manager.submit(SimulationRequest())
        assert manager.cancel(result['id'])['state']=='cancelled'
        assert not (manager.directory(result['id'])/'execution.log').exists()
    finally:
        gate.set();block.result(timeout=2);manager.close()


def test_synthesis_and_duplicate_failure_real_subprocess(tmp_path):
    from itertools import combinations
    import numpy as np
    from vsora_observation import load_config
    from vsora_formats.spectral import save_spectral
    config=load_config(Path(__file__).resolve().parents[3]/'configs/experiments/ideal-point.json')
    config['source']['model']='unknown';config['source'].pop('total_flux_jy')
    pairs=np.array(list(combinations(range(4),2)))
    for i in range(2):
        origin=f'2026-10-02T08:00:{i*10:02d}Z'
        v=np.ones((1,1,6),complex)
        data={'visibilities':v,'weights':np.full(v.shape,1e4),'pairs':pairs,
              'uvw_lambda':np.zeros((*v.shape,3)),'times_s':np.array([.15]),
              'frequencies_hz':np.array([1.42e9]),'integration_s':np.full((1,6),.1)}
        save_spectral(tmp_path/f'input-{i}.npz',data,{'config':config,'visibility_unit':'ADC^2',
            'time_origin_utc':origin,'clock_mapping_applied':True,'phase_center_corrected':True,
            'nominal_integration_s':.1})
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as c:
        payload={'kind':'synthesis','inputs':['input-0.npz','input-1.npz'],'starts':1,'max_iterations':100}
        r=c.post('/api/jobs',json=payload,headers=HEADERS);assert r.status_code==202
        d=wait(c,r.json()['id']);assert d['state']=='complete',d
        assert d['summary']['synthesis']['time_cells']==2
        assert d['summary']['rml']['input_unit']=='ADC^2'
        assert abs(d['summary']['rml']['image_sum']-1)<1e-12
        assert d['summary']['rml']['independent_closure_counts']=={'phase':6,'logamp':4}
        payload['inputs']=['input-0.npz','input-0.npz']
        r=c.post('/api/jobs',json=payload,headers=HEADERS);d=wait(c,r.json()['id'])
        assert d['state']=='failed' and '重複' in d['error_message']
        directory=tmp_path/'outputs/gui'/d['id']
        assert (directory/'synthesis.partial/failure.json').is_file()
        assert not (directory/'synthesis').exists()


def test_sensitivity_plan_real_subprocess(tmp_path):
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as c:
        r=c.post('/api/jobs',json={'kind':'sensitivity','diameter_m':1.,'system_temperature_k':100.},headers=HEADERS)
        assert r.status_code==202;d=wait(c,r.json()['id']);assert d['state']=='complete',d
        assert d['summary']['type']=='sensitivity_plan'
        assert d['summary']['assumptions']['station_sefd_jy'][0]>500000
        assert d['summary']['independent_closure_counts']=={'phase':0,'logamp':0}
        assert d['summary']['antenna_assumptions']['mode']=='dish'
        r=c.post('/api/jobs',json={'kind':'sensitivity','antenna_mode':'effective','effective_area_m2':1.},headers=HEADERS)
        d=wait(c,r.json()['id']);assert d['summary']['assumptions']['station_sefd_jy'][0]==pytest.approx(276129.8)


def test_dense_pilot_request_and_japanese_controls():
    from vsora_ui.models import AnalysisRequest
    request=AnalysisRequest(manifest='manifest.json',clock_model='clock.json',pilot_integrations=4096,
                            pilot_integration_s=.00025,max_rate_hz=1500,integration_s=1)
    assert request.pilot_integration_s==.00025 and request.pilot_integrations==4096
    assert AnalysisRequest(manifest='manifest.json',clock_model='clock.json').pilot_integration_s is None
    with pytest.raises(ValueError):AnalysisRequest(manifest='a',clock_model='b',pilot_integrations=16385)
    with pytest.raises(ValueError):AnalysisRequest(manifest='a',clock_model='b',pilot_integration_s=-1)


@pytest.mark.parametrize('options',[{'window_count':1},{'window_count':33},{'window_count':True},
                                  {'step_s':0},{'step_s':float('nan')},{'resume':True}])
def test_sequence_request_limits(options):
    from vsora_ui.models import SequenceRequest
    with pytest.raises(ValueError):SequenceRequest(manifest='m',clock_model='c',**options)


def test_sequence_gui_real_subprocess_and_failure(tmp_path):
    import numpy as np
    from workflows.vdif_closure_validation import make_fixture
    from workflows.sequence_validation import RATES
    make_fixture(tmp_path/'input',seed=32,frame_count=800,
        rate_changes=[{'start_s':.514,'rates_hz':RATES[1]},{'start_s':1.026,'rates_hz':RATES[2]}])
    make_fixture(tmp_path/'short',seed=23)
    payload={'kind':'sequence','manifest':'input/manifest.json','clock_model':'input/clock.json',
             'window_count':3,'starts':1,'max_iterations':100}
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as c:
        response=c.post('/api/jobs',json=payload,headers=HEADERS);assert response.status_code==202
        d=wait(c,response.json()['id'],90);assert d['state']=='complete',d
        assert d['completed_steps']==d['total_steps']==10
        result=d['summary'];assert len(result['windows'])==3
        assert result['nominal_image_exposure_per_station_s']==pytest.approx(.9)
        assert result['rml']['image_sum']==pytest.approx(1.) and result['rml']['input_unit']=='ADC^2'
        for index,row in enumerate(result['windows']):
            assert np.max(abs(np.array(row['rate_estimate']['station_rates_hz'])-RATES[index]))<.05
        assert c.get(f"/api/jobs/{d['id']}/artifacts/sequence/rates.png").status_code==200
        payload.update(manifest='short/manifest.json',clock_model='short/clock.json',window_count=2)
        response=c.post('/api/jobs',json=payload,headers=HEADERS);d=wait(c,response.json()['id'],60)
        assert d['state']=='failed' and 'VDIFがありません' in d['error_message']
        assert d['sequence_failure']['completed_window_count']==1 and d['sequence_failure']['current_window_index']==1
        assert c.get(f"/api/jobs/{d['id']}/artifacts/sequence.partial/window-0000/correlation/shard-00000.npz").status_code==200
        payload['step_s']=.1
        response=c.post('/api/jobs',json=payload,headers=HEADERS);d=wait(c,response.json()['id'])
        assert d['state']=='failed' and '間隔がpilotより短く' in d['error_message']


def test_gui_required_rate_consistency_stops_before_image(tmp_path):
    from workflows.vdif_closure_validation import make_fixture
    make_fixture(tmp_path/'input',seed=23,rate_slopes_hz_per_s=[0.,20.,-10.,30.])
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as c:
        payload={'kind':'analysis','manifest':'input/manifest.json','clock_model':'input/clock.json',
                 'require_rate_consistency':True,'starts':1,'max_iterations':100}
        response=c.post('/api/jobs',json=payload,headers=HEADERS);assert response.status_code==202
        d=wait(c,response.json()['id'],40)
        assert d['state']=='failed' and '分割rateの整合を必須' in d['error_message']
        assert d['rate_consistency']['state']=='variation_detected' and d['completed_steps']==1
        assert d['summary'] is None
        assert c.get(f"/api/jobs/{d['id']}/artifacts/rate-parts.png").status_code==200
        assert not (tmp_path/'outputs/gui'/d['id']/'analysis.partial/correlation').exists()
        payload['require_rate_consistency']=1
        assert c.post('/api/jobs',json=payload,headers=HEADERS).status_code==422


@pytest.mark.parametrize('kind,model,required',[
    ('analysis','linear',True),('sequence','linear',True),('analysis','other',False),('sequence',True,False)])
def test_invalid_rate_model_policy(tmp_path,kind,model,required):
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as c:
        r=c.post('/api/jobs',json={'kind':kind,'manifest':'m','clock_model':'c',
             'rate_model':model,'require_rate_consistency':required},headers=HEADERS)
        assert r.status_code==422 and c.get('/api/jobs').json()==[]


def test_linear_sequence_gui_real_subprocess(tmp_path):
    from workflows.vdif_closure_validation import make_fixture
    make_fixture(tmp_path/'input',seed=38,frame_count=800,rate_slopes_hz_per_s=[0.,1.,-.5,1.5])
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as c:
        r=c.post('/api/jobs',json={'kind':'sequence','manifest':'input/manifest.json','clock_model':'input/clock.json',
            'rate_model':'linear','window_count':3,'starts':1,'max_iterations':100},headers=HEADERS)
        assert r.status_code==202
        d=wait(c,r.json()['id'],90);assert d['state']=='complete',d
        assert d['summary']['rate_model']=='linear'
        assert all(w['rate_estimate']['type']=='station_rate_linear' for w in d['summary']['windows'])
        assert all(w['rate_estimate']['integration_uncertainty']['type']=='linear_rate_uncertainty' for w in d['summary']['windows'])
        assert all(not w['rate_estimate']['integration_uncertainty']['coherence_stability_measured'] for w in d['summary']['windows'])
        assert d['summary']['nominal_image_exposure_per_station_s']==pytest.approx(.9)
        assert c.get(f"/api/jobs/{d['id']}/artifacts/sequence/rates.png").status_code==200


def test_periodic_phase_validation_real_subprocess(tmp_path):
    (tmp_path/'tools').mkdir()
    (tmp_path/'tools/run.py').symlink_to(Path(__file__).resolve().parents[3]/'tools/run.py')
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as c:
        r=c.post('/api/jobs',json={'kind':'validation','validation':'phase'},headers=HEADERS)
        assert r.status_code==202
        d=wait(c,r.json()['id'],480);assert d['state']=='complete',d
        assert d['summary']['type']=='periodic_phase_validation' and not d['summary']['actual_hardware_data']
        assert d['summary']['cases'][0]['state']=='complete'
        assert len(d['summary']['cases'])==4
        fast=next(r for r in d['summary']['cases'] if r['case']=='fast' and r['rate_model']=='linear')
        assert fast['rate_estimate']['integration_uncertainty']['minimum_expected_centered_complex_coherence']>.99
        assert min(fast['measured_amplitude_ratio_to_same_noise_control'])<.9
        assert c.get(f"/api/jobs/{d['id']}/artifacts/validation/periodic-coherence.png").status_code==200


def test_uncertainty_validation_real_subprocess(tmp_path):
    (tmp_path/'tools').mkdir()
    (tmp_path/'tools/run.py').symlink_to(Path(__file__).resolve().parents[3]/'tools/run.py')
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as c:
        r=c.post('/api/jobs',json={'kind':'validation','validation':'uncertainty'},headers=HEADERS)
        assert r.status_code==202
        d=wait(c,r.json()['id'],90);assert d['state']=='complete',d
        q=d['summary'];assert q['type']=='rate_uncertainty_validation' and q['draws']==65536
        assert not q['actual_hardware_data'] and not q['covariance_calibrated_against_rate_solver']
        assert len(q['gaussian_results'])==6
        assert c.get(f"/api/jobs/{d['id']}/artifacts/validation/rate-uncertainty.png").status_code==200


def test_covariance_validation_real_subprocess(tmp_path):
    (tmp_path/'tools').mkdir()
    (tmp_path/'tools/run.py').symlink_to(Path(__file__).resolve().parents[3]/'tools/run.py')
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as c:
        r=c.post('/api/jobs',json={'kind':'validation','validation':'covariance'},headers=HEADERS)
        assert r.status_code==202
        d=wait(c,r.json()['id'],120);assert d['state']=='complete',d
        q=d['summary'];assert q['type']=='rate_covariance_validation' and q['trials_per_group']==1024
        assert not q['actual_hardware_data'] and not q['physical_iq_vdif_processed'] and len(q['groups'])==8
        assert all(r['statistics_conditioned_on_accepted'] for r in q['groups'])
        assert q['groups'][3]['accepted_count']<1024
        assert c.get(f"/api/jobs/{d['id']}/artifacts/validation/rate-covariance.png").status_code==200
