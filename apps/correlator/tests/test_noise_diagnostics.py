import hashlib
import json
import numpy as np
import pytest
from vsora_correlator.noise_diagnostics import diagnose_noise_cell,diagnose_noise_file
from vsora_correlator.stream_fx import FXAccumulator
from vsora_formats.spectral import save_spectral
from vsora_simulator.visibility_noise_estimate import estimate_visibility_noise


def fixture(mask=None,m=512):
    rng=np.random.default_rng(47);mode=np.exp(1j*np.array([0.,.4,1.1,2.2]))
    s=np.ones((4,4))+.7*mode[:,None]*mode.conj()[None,:]+1.5*np.eye(4)
    z=(rng.normal(size=(m*64,4))+1j*rng.normal(size=(m*64,4)))/np.sqrt(2)
    x=(z @ np.linalg.cholesky(s).T).T;valid=np.ones(x.shape,bool)
    if mask=='common':valid[:,:64]=False
    elif mask=='different':valid[1,:64]=False
    quality={'channel_weights':True,'min_sk_blocks':24,'sk_bounds':[.2,5.],'exclude_rf_ranges_hz':[]}
    accumulator=FXAccumulator(4,2048000,64,1.42e9,quality)
    for first in range(0,x.shape[1],8192):accumulator.consume(x[:,first:first+8192],valid[:,first:first+8192])
    r=accumulator.finish();v=r.pop('vis_jy');r.update(visibilities=v,uvw_lambda=np.zeros((*v.shape,3)),
        metadata={'visibility_unit':'ADC^2','diagnostic_power_unit':'ADC^2',
            'config':{'stations':[{'id':f'ST{i+1:02d}'} for i in range(4)]}})
    spectrum=np.fft.fft(x.reshape(4,-1,64).transpose(1,2,0),axis=1,norm='ortho')
    selected=spectrum[1:] if mask=='common' else spectrum
    direct=selected[:,0,:].T @ selected[:,0,:].conj()/len(selected)
    return r,direct


@pytest.mark.parametrize('mask',[None,'common'])
def test_gaussian_iq_fft_covariance_matches_direct_samples(mask):
    data,direct=fixture(mask);q=diagnose_noise_cell(data,0,32)
    assert q['state']=='conditional_estimate' and q['nominal_common_fft_blocks']==(511 if mask else 512)
    np.testing.assert_allclose(np.array(q['station_sample_covariance_real'])+1j*np.array(q['station_sample_covariance_imag']),direct,rtol=1e-12,atol=1e-13)
    expected=estimate_visibility_noise(direct,q['nominal_common_fft_blocks'])
    np.testing.assert_allclose(q['estimated_visibility_covariance'],expected['real_covariance'],rtol=1e-11,atol=1e-14)
    assert all(q['closure_joint_valid']) and not q['iid_fft_independence_verified']
    assert q['visibility_covariance_ensemble_unbiased_only_if_assumptions_hold']
    assert q['closure_covariance_first_order_not_unbiased_guarantee']
    assert not q['production_rml_noise_model_changed'] and not q['real_hardware_validation_performed']


def test_different_station_masks_not_a_common_sample_covariance():
    data,_=fixture('different');q=diagnose_noise_cell(data,0,32)
    assert q['state']=='unverified' and q['reason']=='station_and_baseline_fft_sets_differ'


@pytest.mark.parametrize('kind,reason',[
    ('missing','missing_station_power_flags_or_fft_counts'),('unit','power_visibility_units_differ_or_missing'),
    ('flag','station_quality_flag'),('partial','partial_baseline_mask'),('all','no_positive_baseline_weights'),
    ('station_count','station_and_baseline_fft_sets_differ'),('pair_count','station_and_baseline_fft_sets_differ'),
    ('few','insufficient_common_fft_blocks'),('identity','missing_or_invalid_station_identity'),
    ('duplicate','missing_or_invalid_station_identity'),('psd','invalid_station_sample_covariance'),
    ('incomplete','incomplete_baseline_set')])
def test_unverified_and_inactive_conditions(kind,reason):
    data,_=fixture()
    if kind=='missing':data.pop('valid_fft_count')
    elif kind=='unit':data['metadata']['diagnostic_power_unit']='Jy'
    elif kind=='flag':data['diagnostic_station_flags'][0,32,0]=4
    elif kind=='partial':data['weights'][0,32,0]=0
    elif kind=='all':data['weights'][0,32]=0
    elif kind=='station_count':data['diagnostic_station_valid_fft_count'][0,1]-=1
    elif kind=='pair_count':data['valid_fft_count'][0,1]-=1
    elif kind=='few':data['diagnostic_station_valid_fft_count'][:]=3;data['valid_fft_count'][:]=3
    elif kind=='identity':data['metadata']['config'].pop('stations')
    elif kind=='duplicate':data['metadata']['config']['stations'][1]['id']='ST01'
    elif kind=='psd':data['visibilities'][0,32,0]=1000
    elif kind=='incomplete':
        for key in ('visibilities','weights'):data[key]=data[key][:,:,:-1]
        data['pairs']=data['pairs'][:-1];data['valid_fft_count']=data['valid_fft_count'][:,:-1]
        data['uvw_lambda']=data['uvw_lambda'][:,:,:-1]
    q=diagnose_noise_cell(data,0,32)
    assert q['state']==('inactive' if kind=='all' else 'unverified') and q['reason']==reason
    assert 'estimated_visibility_covariance' not in q


@pytest.mark.parametrize('kind',['counts_shape','counts_float','negative_count','power_nan','power_complex','flags_shape','negative_power'])
def test_malformed_statistics_fail(kind):
    data,_=fixture()
    if kind=='counts_shape':data['valid_fft_count']=np.ones((6,),int)
    elif kind=='counts_float':data['valid_fft_count']=data['valid_fft_count'].astype(float)
    elif kind=='negative_count':data['valid_fft_count'][0,0]=-1
    elif kind=='power_nan':data['diagnostic_station_power'][0,32,0]=np.nan
    elif kind=='power_complex':data['diagnostic_station_power']=data['diagnostic_station_power'].astype(complex)
    elif kind=='flags_shape':data['diagnostic_station_flags']=data['diagnostic_station_flags'][:,:,:-1]
    elif kind=='negative_power':data['diagnostic_station_power'][0,32,0]=-1
    with pytest.raises(ValueError):diagnose_noise_cell(data,0,32)


@pytest.mark.parametrize('t,f',[(-1,32),(1,32),(True,32),(0,-1),(0,64),(0,2.5)])
def test_invalid_cell_indices(t,f):
    data,_=fixture()
    with pytest.raises(ValueError):diagnose_noise_cell(data,t,f)


def test_file_identity_and_no_overwrite(tmp_path):
    data,_=fixture();metadata=data.pop('metadata');source=tmp_path/'input.npz'
    save_spectral(source,data,metadata);out=tmp_path/'noise.json'
    q=diagnose_noise_file(source,out,32)
    assert q==json.loads(out.read_text()) and q['input_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    assert q['state']=='conditional_estimate'
    with pytest.raises(FileExistsError):diagnose_noise_file(source,out,32)
    with pytest.raises(ValueError):diagnose_noise_file(source,tmp_path/'wrong.txt',32)


def test_aligned_vdif_preserves_nominal_fft_counts(tmp_path):
    from workflows.vdif_closure_validation import make_fixture
    from vsora_correlator.aligned import correlate_aligned
    from vsora_formats.spectral import load_spectral
    make_fixture(tmp_path/'input',47,rates_hz=[0,0,0,0],frame_count=160)
    correlate_aligned(tmp_path/'input/manifest.json',tmp_path/'input/clock.json',tmp_path/'correlation',1)
    data=load_spectral(tmp_path/'correlation/shard-00000.npz');meta=data['metadata']
    expected=data['integration_s']*meta['fft_sample_rate_hz']/meta['fft_length']
    np.testing.assert_allclose(data['valid_fft_count'],expected,atol=1e-8)
    q=diagnose_noise_cell(data,0,meta['fft_length']//2)
    assert q['state']=='conditional_estimate' and not q['iid_fft_independence_verified']
    assert not q['real_hardware_validation_performed']
