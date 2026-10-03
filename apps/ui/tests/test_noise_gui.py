"""Actual GUI workers for saved statistics; no receiver/image verification."""
import hashlib
import time
from itertools import combinations
import numpy as np
import pytest
from fastapi.testclient import TestClient
from vsora_formats.spectral import save_spectral
from vsora_correlator.noise_diagnostics import diagnose_noise_cell
from vsora_ui.server import create_app

HEADERS={'X-VSoRA-Request':'1'}


def fixture(path,m=512,mode=None):
    pairs=np.array(list(combinations(range(4),2)));v=np.ones((2,3,6),complex)
    data={'visibilities':v,'weights':np.ones(v.shape),'pairs':pairs,'uvw_lambda':np.zeros((*v.shape,3)),
          'times_s':np.array([.1,.2]),'frequencies_hz':np.array([1.419e9,1.42e9,1.421e9]),
          'integration_s':np.full((2,6),.1),'valid_fft_count':np.full((2,6),m,dtype=np.int64),
          'diagnostic_station_power':np.full((2,3,4),2.),'diagnostic_station_valid_fft_count':np.full((2,4),m,dtype=np.int64),
          'diagnostic_station_flags':np.zeros((2,3,4),dtype=np.int64)}
    meta={'visibility_unit':'ADC^2','diagnostic_power_unit':'ADC^2','time_origin_utc':'2026-10-02T08:00:00Z',
          'config':{'stations':[{'id':f'ST{i+1:02d}'} for i in range(4)]}}
    if mode=='old':data.pop('valid_fft_count')
    elif mode=='inactive':data['weights'][:]=0
    save_spectral(path,data,meta);return data,meta


def wait(client,job_id):
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        d=client.get('/api/jobs/'+job_id).json()
        if d['state'] not in ('queued','running'):return d
        time.sleep(.05)
    raise AssertionError('noise worker timed out')


@pytest.mark.parametrize('fields',[{}, {'input':'a'},{'input':'a','channel_index':-1},
    {'input':'a','channel_index':True},{'input':'a','channel_index':1.5},
    {'input':'a','channel_index':0,'time_index':True},{'input':'a','channel_index':0,'command':'sh'}])
def test_noise_request_rejection(tmp_path,fields):
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as client:
        assert client.post('/api/jobs',json={'kind':'noise',**fields},headers=HEADERS).status_code==422
        assert client.get('/api/jobs').json()==[]


def test_axes_and_actual_noise_worker_match_library(tmp_path):
    data,meta=fixture(tmp_path/'input.npz');data['metadata']=meta
    sha=hashlib.sha256((tmp_path/'input.npz').read_bytes()).hexdigest()
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as client:
        assert '雑音診断' in client.get('/').text
        assert client.post('/api/noise-input',json={'input':'input.npz'}).status_code==403
        r=client.post('/api/noise-input',json={'input':'input.npz'},headers=HEADERS);assert r.status_code==200
        axes=r.json();assert axes['times_s']==[.1,.2] and axes['frequencies_hz']==[1.419e9,1.42e9,1.421e9]
        assert axes['diagnostic_pair_counts_available']
        r=client.post('/api/jobs',json={'kind':'noise','input':'input.npz','time_index':1,'channel_index':2},headers=HEADERS)
        assert r.status_code==202;d=wait(client,r.json()['id']);assert d['state']=='complete',d
        expected=diagnose_noise_cell(data,1,2)
        assert d['summary']=={**expected,'input_sha256':sha}
        assert d['summary']['state']=='conditional_estimate' and all(d['summary']['closure_joint_valid'])
        assert d['summary']['pairs']==data['pairs'].tolist()
        assert len(d['summary']['triangles'])==4 and len(d['summary']['quadrangles'])==2
        artifact=client.get(f"/api/jobs/{d['id']}/artifacts/noise.json");assert artifact.json()==d['summary']
        assert hashlib.sha256((tmp_path/'input.npz').read_bytes()).hexdigest()==sha


def test_unverified_inactive_and_low_snr_workers(tmp_path):
    for name in ('old','inactive','low'):
        fixture(tmp_path/f'{name}.npz',m=4 if name=='low' else 512,mode=name)
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as client:
        axes=client.post('/api/noise-input',json={'input':'old.npz'},headers=HEADERS).json()
        assert not axes['diagnostic_pair_counts_available']
        for name,state in [('old','unverified'),('inactive','inactive'),('low','conditional_estimate')]:
            r=client.post('/api/jobs',json={'kind':'noise','input':f'{name}.npz','channel_index':1},headers=HEADERS)
            d=wait(client,r.json()['id']);assert d['state']=='complete' and d['summary']['state']==state,d
            if name=='low':
                assert not any(d['summary']['closure_joint_valid'])
                assert np.count_nonzero(d['summary']['estimated_joint_closure_covariance'])==0
            elif name=='old':assert 'estimated_visibility_covariance' not in d['summary']


def test_missing_corrupt_and_out_of_range_input(tmp_path):
    fixture(tmp_path/'input.npz');(tmp_path/'corrupt.npz').write_bytes(b'not an npz')
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as client:
        for name in ('missing.npz','corrupt.npz'):
            r=client.post('/api/noise-input',json={'input':name},headers=HEADERS)
            assert r.status_code==400 and '読込に失敗' in r.json()['detail']
        for name,index,text in [('missing.npz',0,'見つかりません'),('input.npz',3,'範囲外')]:
            r=client.post('/api/jobs',json={'kind':'noise','input':name,'channel_index':index},headers=HEADERS)
            d=wait(client,r.json()['id']);assert d['state']=='failed' and text in d['error_message'],d
            assert d['summary'] is None
