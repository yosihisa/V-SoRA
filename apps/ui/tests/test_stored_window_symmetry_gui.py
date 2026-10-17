"""Strict request and real worker transport for stored conditional symmetry."""
import hashlib,time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from vsora_formats.bispectrum import save_bispectrum,load_bispectrum
from vsora_simulator.bispectrum_archive_validation import _example
from vsora_correlator.bispectrum_window_symmetry import window_symmetry_from_bispectrum
from vsora_ui.server import create_app
from vsora_ui.models import BispectrumWindowSymmetryRequest

HEADERS={'X-VSoRA-Request':'1'}

def files(folder,mode='complete',version=2):
    arrays,meta,source,_=_example(folder,mode)
    if version==1:arrays.pop('common_station_power_sums')
    raw=folder/'raw.npz';save_bispectrum(raw,arrays,meta,schema_version=version)
    return raw,source

def selected(client,raw,source):
    response=client.post('/api/bispectrum-input',json={'input':raw.name,'source_visibility':source.name},headers=HEADERS)
    assert response.status_code==200
    axes=response.json()
    return {'kind':'bispectrum_window_symmetry','input':raw.name,'source_visibility':source.name,
        'channel_index':1,'raw_bispectrum_sha256':axes['raw_bispectrum_sha256'],
        'source_visibility_sha256':axes['source_visibility_sha256']},axes

def wait(client,id):
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        q=client.get('/api/jobs/'+id).json()
        if q['state'] not in ('queued','running'):return q
        time.sleep(.05)
    raise AssertionError('worker timeout')

@pytest.mark.parametrize('field,value',[
    ('channel_index',True),('channel_index',1.5),('channel_index',-1),
    ('raw_bispectrum_sha256','g'*64),('source_visibility_sha256','0'*63),
    ('input',''),('source_visibility',''),('time_index',0),('alpha',.05),('window_indices',[0])])
def test_strict_window_request(tmp_path,field,value):
    raw,source=files(tmp_path)
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as client:
        request,_=selected(client,raw,source);request[field]=value
        assert client.post('/api/jobs',json=request,headers=HEADERS).status_code==422
        assert client.get('/api/jobs').json()==[]

@pytest.mark.parametrize('mode,version,channel,success,message',[
    ('complete',2,1,True,None),
    ('complete',2,0,False,'すべての区間・三角形'),
    ('two',2,1,False,'すべての区間・三角形'),
    ('zero_station',2,1,False,'すべての区間・三角形'),
    ('complete',1,1,False,'version2'),
    ('complete',2,4,False,'範囲外')])
def test_actual_window_worker(tmp_path,mode,version,channel,success,message):
    raw,source=files(tmp_path,mode,version);before=raw.read_bytes(),source.read_bytes()
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as client:
        request,axes=selected(client,raw,source);assert axes['raw_schema_version']==version
        assert '全区間の条件付き対称性を確認' in client.get('/').text
        request['channel_index']=channel
        response=client.post('/api/jobs',json=request,headers=HEADERS);assert response.status_code==202
        job=wait(client,response.json()['id']);assert job['label']=='保存区間列の条件付き対称性'
        artifact=client.get('/api/jobs/'+job['id']+'/artifacts/window-symmetry.json')
        if success:
            expected=window_symmetry_from_bispectrum(load_bispectrum(raw,source),channel)
            expected.update(source_visibility_verified=True,raw_bispectrum_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
                            source_visibility_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
            assert job['state']=='complete' and job['summary']==expected==artifact.json()
        else:
            assert job['state']=='failed' and job['summary'] is None and message in job['error_message']
            assert artifact.status_code!=200
    assert before==(raw.read_bytes(),source.read_bytes())

@pytest.mark.parametrize('field',['raw_bispectrum_sha256','source_visibility_sha256'])
def test_selected_identity_rechecked(tmp_path,field):
    raw,source=files(tmp_path)
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as client:
        request,_=selected(client,raw,source);request[field]='0'*64
        job=wait(client,client.post('/api/jobs',json=request,headers=HEADERS).json()['id'])
        assert job['state']=='failed' and '読み直' in job['error_message']
        assert job['summary'] is None

def test_only_channel_and_no_time_in_model():
    q=BispectrumWindowSymmetryRequest(input='raw.npz',source_visibility='source.npz',channel_index=1,
        raw_bispectrum_sha256='0'*64,source_visibility_sha256='1'*64)
    assert set(q.model_dump())=={'kind','input','source_visibility','channel_index',
                                 'raw_bispectrum_sha256','source_visibility_sha256'}

def test_thirteen_windows_not_subset(tmp_path):
    from workflows.bispectrum_window_validation import fixture
    folder=tmp_path/'case';raw,source,_,_=fixture(folder,windows=13,modes=3)
    with TestClient(create_app(folder),base_url='http://127.0.0.1') as client:
        request,axes=selected(client,raw,source);assert len(axes['times_s'])==13
        job=wait(client,client.post('/api/jobs',json=request,headers=HEADERS).json()['id'])
        assert job['state']=='failed' and '区間数は1〜12' in job['error_message']
        assert job['summary'] is None
