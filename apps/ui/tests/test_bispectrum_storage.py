"""Observer opt-in storage and unchanged ordinary relative image pipeline."""
import json,time
from pathlib import Path
import numpy as np
import pytest
pytest.importorskip('fastapi')
pytest.importorskip('httpx')
from fastapi.testclient import TestClient
from pydantic import ValidationError
from vsora_ui.models import AnalysisRequest,SequenceRequest
from vsora_ui.server import create_app
from vsora_correlator.closure_pipeline import process_closure_session
from vsora_correlator.sequence import process_sequence
from vsora_formats.spectral import load_spectral
from vsora_formats.bispectrum import load_bispectrum

HEADERS={'X-VSoRA-Request':'1','Origin':'http://127.0.0.1'}


def wait(client,jid,timeout=60):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        q=client.get('/api/jobs/'+jid).json()
        if q['state'] not in ('queued','running'):return q
        time.sleep(.05)
    raise AssertionError('scientific GUI job timeout')


@pytest.mark.parametrize('model',[AnalysisRequest,SequenceRequest])
def test_storage_default_and_explicit_bool(model):
    args={'manifest':'manifest.json','clock_model':'clock.json'}
    assert model(**args).save_bispectrum is False
    assert model(**args,save_bispectrum=True).save_bispectrum is True


@pytest.mark.parametrize('kind',['analysis','sequence'])
@pytest.mark.parametrize('bad',[1,0,'true',None])
def test_api_rejects_non_bool_storage_before_job(tmp_path,kind,bad):
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as c:
        response=c.post('/api/jobs',json={'kind':kind,'manifest':'absent.json','clock_model':'absent.json','save_bispectrum':bad},headers=HEADERS)
        assert response.status_code==422 and not c.get('/api/jobs').json()


@pytest.mark.parametrize('operation',[process_closure_session,process_sequence])
@pytest.mark.parametrize('bad',[1,'true',None])
def test_pipeline_rejects_non_bool_before_input_or_output(tmp_path,operation,bad):
    with pytest.raises(ValueError,match='bool'):operation('absent','absent',tmp_path/'out',save_bispectrum=bad)
    assert not (tmp_path/'out').exists() and not (tmp_path/'out.partial').exists()


def test_actual_analysis_gui_raw_download_and_identical_image(tmp_path):
    from workflows.vdif_closure_validation import make_fixture
    make_fixture(tmp_path/'input',seed=23)
    ordinary=process_closure_session(tmp_path/'input/manifest.json',tmp_path/'input/clock.json',tmp_path/'ordinary',starts=1,max_iterations=100)
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as c:
        response=c.post('/api/jobs',json={'kind':'analysis','manifest':'input/manifest.json','clock_model':'input/clock.json',
            'starts':1,'max_iterations':100,'save_bispectrum':True},headers=HEADERS)
        assert response.status_code==202
        q=wait(c,response.json()['id']);assert q['state']=='complete',q
        root=tmp_path/'outputs/gui'/q['id']/'analysis'
        source=root/'correlation/shard-00000.npz';raw_path=root/'correlation/raw-bispectrum.npz'
        raw=load_bispectrum(raw_path,source);assert raw['source_visibility_verified']
        a=load_spectral(tmp_path/'ordinary/correlation/shard-00000.npz');b=load_spectral(source)
        for k,v in a.items():
            if isinstance(v,np.ndarray):np.testing.assert_array_equal(v,b[k])
        assert a['metadata']==b['metadata']
        np.testing.assert_array_equal(np.load(tmp_path/'ordinary/rml/relative-model.npy'),np.load(root/'rml/relative-model.npy'))
        assert 'raw_bispectrum' not in ordinary['correlation'] and not (root/'pilot/raw-bispectrum.npz').exists()
        assert not raw['metadata']['production_rml_noise_model_changed']
        detail=c.get('/').text
        assert detail.count('name="save_bispectrum"')==2
        for name in ('raw-bispectrum.npz','shard-00000.npz'):
            downloaded=c.get(f"/api/jobs/{q['id']}/artifacts/analysis/correlation/{name}")
            assert downloaded.status_code==200 and downloaded.content==(root/'correlation'/name).read_bytes()
        assert '三次統計' in c.get('/assets/app.js').text


@pytest.mark.parametrize('name',['closure_pipeline','sequence'])
def test_unsupported_storage_dimensions_rejected_before_pipeline_output(tmp_path,monkeypatch,name):
    from vsora_correlator import closure_pipeline,sequence
    selected={'closure_pipeline':closure_pipeline,'sequence':sequence}[name]
    c={'sample_rate_hz':2048000,'fft_length':8192,'blocks_per_integration':4,
       'stations':[{}]*4,'phase_center_correction':True,'_config':{}}
    monkeypatch.setattr(selected,'load_session',lambda _:c)
    operation=selected.process_closure_session if name=='closure_pipeline' else selected.process_sequence
    with pytest.raises(ValueError,match='raw bispectrum'):
        operation('not-read','not-read',tmp_path/'out',pilot_integrations=8,integration_s=.1,max_rate_hz=10.,save_bispectrum=True)
    assert not (tmp_path/'out').exists() and not (tmp_path/'out.partial').exists()
