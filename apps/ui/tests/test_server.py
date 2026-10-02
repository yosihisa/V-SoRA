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


def wait(client,job_id):
    deadline=time.monotonic()+25
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
    from vsora_ui.jobs import source_root
    (tmp_path/'tools').mkdir()
    (tmp_path/'tools/run.py').symlink_to(source_root()/'tools/run.py')
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
