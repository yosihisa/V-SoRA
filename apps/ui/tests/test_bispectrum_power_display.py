"""Display rounding and actual local worker transport for normalized values."""
import hashlib,time
import pytest
from tools.verify_bispectrum_power_ui import javascript_exponential

@pytest.mark.parametrize('value,expected',[(0.,'0.000000e+0'),(-0.,'0.000000e+0'),(3906250.5,'3.906251e+6'),
    (-3906250.5,'-3.906251e+6'),(9999999.5,'1.000000e+7'),(1e-300,'1.000000e-300'),(5e-324,'4.940656e-324')])
def test_display_rounding(value,expected):assert javascript_exponential(value)==expected

@pytest.mark.parametrize('value',[float('nan'),float('inf'),-float('inf')])
def test_nonfinite_display_rejected(value):
    with pytest.raises(ValueError):javascript_exponential(value)

@pytest.mark.parametrize('mode,version',[('complete',2),('two',2),('zero_station',2),('complete',1)])
def test_actual_gui_worker_normalized_json(tmp_path,mode,version):
    from fastapi.testclient import TestClient
    from vsora_ui.server import create_app
    from vsora_simulator.bispectrum_archive_validation import _example
    from vsora_formats.bispectrum import save_bispectrum,load_bispectrum
    from vsora_correlator.bispectrum_inspect import inspect_bispectrum_cell
    d,meta,source,_=_example(tmp_path,mode)
    if version==1:d.pop('common_station_power_sums')
    raw=tmp_path/'raw.npz';save_bispectrum(raw,d,meta,schema_version=version)
    headers={'X-VSoRA-Request':'1','Origin':'http://127.0.0.1'}
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as client:
        response=client.post('/api/bispectrum-input',json={'input':raw.name,'source_visibility':source.name},headers=headers)
        assert response.status_code==200;axes=response.json()
        request={'kind':'bispectrum_inspection','input':raw.name,'source_visibility':source.name,'time_index':0,'channel_index':1,
            'raw_bispectrum_sha256':axes['raw_bispectrum_sha256'],'source_visibility_sha256':axes['source_visibility_sha256']}
        response=client.post('/api/jobs',json=request,headers=headers);assert response.status_code==202
        job_id=response.json()['id'];deadline=time.monotonic()+40
        while time.monotonic()<deadline:
            job=client.get('/api/jobs/'+job_id).json()
            if job['state'] not in ('queued','running'):break
            time.sleep(.05)
        assert job['state']=='complete',job
        expected=inspect_bispectrum_cell(load_bispectrum(raw,source),0,1)
        expected.update(source_visibility_verified=True,raw_bispectrum_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
            source_visibility_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        assert job['summary']==expected and expected['raw_schema_version']==version
        assert client.get(f'/api/jobs/{job_id}/artifacts/bispectrum-inspection.json').json()==expected
        assert '共通電力で割った三次統計' in client.get('/assets/app.js').text
        assert not expected['noise_covariance_estimated'] and not expected['production_rml_noise_model_changed']
