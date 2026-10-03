"""Actual workers on constructed statistics; no new physical ADC validation."""
import hashlib
import json
import time
from itertools import combinations
import numpy as np
import pytest
from fastapi.testclient import TestClient
from vsora_formats.spectral import save_spectral
from vsora_correlator.time_scatter import diagnose_time_scatter
from vsora_ui.server import create_app

HEADERS={'X-VSoRA-Request':'1'}


def fixture(path,mode=None):
    nt=64;pairs=np.array(list(combinations(range(4),2)));t=.003+np.arange(nt)*.002
    v=np.full((nt,3,6),.3+0j)
    data={'visibilities':v,'weights':np.ones(v.shape),'pairs':pairs,'times_s':t,
        'frequencies_hz':np.array([1.419e9,1.42e9,1.421e9]),'uvw_lambda':np.zeros((*v.shape,3)),
        'integration_s':np.full((nt,6),.002),'valid_fft_count':np.full((nt,6),128),
        'diagnostic_station_valid_fft_count':np.full((nt,4),128),
        'diagnostic_station_power':np.ones((nt,3,4)),'diagnostic_station_flags':np.zeros((nt,3,4),int)}
    meta={'visibility_unit':'ADC^2','diagnostic_power_unit':'ADC^2','time_origin_utc':'2026-10-04T00:00:00Z',
        'config':{'stations':[{'id':f'ST{i+1:02d}'} for i in range(4)]},'rate_profile_type':None,
        'rate_applied_hz':[0]*4,'rate_applied_slopes_hz_per_s':[0]*4}
    profile={'schema_version':1,'type':'station_rate_linear','station_indices':list(range(4)),
        'station_ids':[f'ST{i+1:02d}' for i in range(4)],'time_origin_utc':meta['time_origin_utc'],
        'station_rates_hz':[0,7,-3,2],'station_rate_slopes_hz_per_s':[0,.2,-.4,.3],
        'time_reference_s':float(np.mean(t)),'valid_time_range_s':[float(t[0]),float(t[-1])],
        'sample_cadence_s':.002,'max_baseline_rate_hz':100,'temporal_nyquist_hz':250}
    if mode=='old':data.pop('valid_fft_count')
    elif mode=='weak':data['visibilities'][:]=0
    elif mode=='double':meta['rate_profile_type']='station_rate_linear'
    save_spectral(path,data,meta);data['metadata']=meta
    return data,profile


def wait(client,id):
    end=time.monotonic()+20
    while time.monotonic()<end:
        job=client.get('/api/jobs/'+id).json()
        if job['state'] not in ('queued','running'):return job
        time.sleep(.05)
    raise AssertionError('time-scatter worker timed out')


@pytest.mark.parametrize('fields',[{}, {'input':'a','channel_index':True}, {'input':'a','channel_index':-1},
    {'input':'a','channel_index':.5},{'input':'a','channel_index':0,'rate_profile':''},
    {'input':'a','channel_index':0,'time_index':0},{'input':'a','channel_index':0,'command':'sh'},{'input':'a','channel_index':0,'rate_profile':True}])
def test_request_rejections(tmp_path,fields):
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as client:
        r=client.post('/api/jobs',json={'kind':'time_scatter',**fields},headers=HEADERS)
        assert r.status_code==422 and client.get('/api/jobs').json()==[]


def test_worker_profile_axes_and_saved_json_equal_api(tmp_path):
    data,profile=fixture(tmp_path/'input.npz');(tmp_path/'rate.json').write_text(json.dumps(profile))
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as client:
        assert 'pilot全体の時間方向' in client.get('/').text
        axes=client.post('/api/noise-input',json={'input':'input.npz'},headers=HEADERS).json()
        assert len(axes['times_s'])==64 and axes['frequencies_hz'][1]==1.42e9
        r=client.post('/api/jobs',json={'kind':'time_scatter','input':'input.npz','channel_index':1,'rate_profile':'rate.json'},headers=HEADERS)
        job=wait(client,r.json()['id']);assert job['state']=='complete',job
        expected=diagnose_time_scatter(data,1,profile)
        assert job['summary']=={**expected,'input_sha256':hashlib.sha256((tmp_path/'input.npz').read_bytes()).hexdigest(),
            'rate_profile_sha256':hashlib.sha256((tmp_path/'rate.json').read_bytes()).hexdigest()}
        assert client.get(f"/api/jobs/{job['id']}/artifacts/time-scatter.json").json()==job['summary']


def test_unverified_and_nonpositive_power_workers(tmp_path):
    for name in ('old','weak'):fixture(tmp_path/f'{name}.npz',name)
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as client:
        for name,state in [('old','unverified'),('weak','conditional_estimate')]:
            r=client.post('/api/jobs',json={'kind':'time_scatter','input':name+'.npz','channel_index':1},headers=HEADERS)
            job=wait(client,r.json()['id']);assert job['state']=='complete' and job['summary']['state']==state
            if name=='weak':assert all(b['mean_to_time_power_ratio_unbounded'] is None for b in job['summary']['baselines'])


@pytest.mark.parametrize('kind,text',[('missing','見つかりません'),('double','rate補正済み'),('origin','UTC原点'),('outside','有効時間')])
def test_profile_failures_in_japanese(tmp_path,kind,text):
    _,p=fixture(tmp_path/'input.npz','double' if kind=='double' else None)
    if kind=='origin':p['time_origin_utc']='2026-10-03T00:00:00Z'
    elif kind=='outside':p['valid_time_range_s'][1]-=.01
    if kind!='missing':(tmp_path/'rate.json').write_text(json.dumps(p))
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as client:
        r=client.post('/api/jobs',json={'kind':'time_scatter','input':'input.npz','channel_index':1,'rate_profile':'rate.json'},headers=HEADERS)
        job=wait(client,r.json()['id']);assert job['state']=='failed' and text in job['error_message'],job
        assert job['summary'] is None
