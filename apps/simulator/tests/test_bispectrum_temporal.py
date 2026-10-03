from itertools import permutations,product
import numpy as np
import pytest
from vsora_simulator.bispectrum_temporal import white_filter_temporal_covariance,temporal_receiver_bispectrum_mean


def covariances(m):
    rng=np.random.default_rng(55);a=rng.normal(size=(3,m,m))+1j*rng.normal(size=(3,m,m))
    return np.array([r @ r.conj().T/m for r in a])


@pytest.mark.parametrize('m',[3,4,7])
def test_index_enumeration_for_three_different_covariances(m):
    k=covariances(m);original=k.copy();q=temporal_receiver_bispectrum_mean(k)
    def term(a,b,c):return k[0,a,c]*k[1,b,a]*k[2,c,b]
    ordinary=sum(term(a,b,c) for a,b,c in product(range(m),repeat=3))/m**3
    distinct=sum(term(a,b,c) for a,b,c in permutations(range(m),3))/(m*(m-1)*(m-2))
    assert q['ordinary_bispectrum_mean']==pytest.approx(ordinary,rel=1e-11,abs=1e-12)
    assert q['distinct_bispectrum_mean']==pytest.approx(distinct,rel=1e-11,abs=1e-12)
    np.testing.assert_array_equal(k,original)
    assert q['true_astronomical_bispectrum']==0
    assert not q['actual_temporal_independence_verified'] and not q['production_rml_noise_model_changed']


@pytest.mark.parametrize('delta',[0,.25,.75])
def test_reference_fft_filter_covariance_equals_direct_white_operator(delta):
    from vsora_simulator.filtered_noise import aligned_fft_kernel
    h=aligned_fft_kernel(32,16,delta);m=8;hop=32;k=white_filter_temporal_covariance(h,hop,m)
    operator=np.zeros((m,(m-1)*hop+len(h)),complex)
    for a in range(m):operator[a,a*hop:a*hop+len(h)]=h
    np.testing.assert_allclose(k,operator @ operator.conj().T,rtol=1e-12,atol=1e-14)


def test_white_and_correlated_common_filter_and_guard():
    white=np.eye(128);q=temporal_receiver_bispectrum_mean(np.repeat(white[None],3,axis=0))
    assert q['ordinary_bispectrum_mean']==pytest.approx(1/128**2)
    assert q['distinct_bispectrum_mean']==0
    k=white_filter_temporal_covariance(np.ones(65)/np.sqrt(65),8,128)
    q=temporal_receiver_bispectrum_mean(np.repeat(k[None],3,axis=0))
    assert q['distinct_bispectrum_mean'].real>1e-4
    guard=k[::9,::9];np.testing.assert_allclose(guard,np.eye(15),atol=1e-14)
    q=temporal_receiver_bispectrum_mean(np.repeat(guard[None],3,axis=0))
    assert abs(q['distinct_bispectrum_mean'])<1e-14
    assert q['samples']==15


def test_common_gain_power_scaling_and_complex_means_possible():
    k=covariances(7);q=temporal_receiver_bispectrum_mean(k);gain_power=np.array([.4,3.,1.5])**2
    transformed=temporal_receiver_bispectrum_mean(k*gain_power[:,None,None])
    for key in ('ordinary_bispectrum_mean','distinct_bispectrum_mean'):
        assert transformed[key]==pytest.approx(q[key]*np.prod(gain_power),rel=1e-11,abs=1e-12)
    # Arbitrary nonstationary receiver covariances, no source. Not a claim for all stationary FIRs.
    assert abs(q['distinct_bispectrum_mean'].imag)>1e-4


@pytest.mark.parametrize('kind',['shape','stations','few','many','nonfinite','nonhermitian','negative','masked'])
def test_temporal_covariance_rejections(kind):
    k=np.repeat(np.eye(8)[None],3,axis=0).astype(complex)
    if kind=='shape':k=k[:,:,:7]
    elif kind=='stations':k=k[:2]
    elif kind=='few':k=k[:,:2,:2]
    elif kind=='many':k=np.broadcast_to(np.array(1+0j),(3,257,257))
    elif kind=='nonfinite':k[0,0,0]=np.nan
    elif kind=='nonhermitian':k[0,0,1]=1j
    elif kind=='negative':k[0,0,0]=-1
    elif kind=='masked':k=np.ma.array(k,mask=False)
    with pytest.raises(ValueError):temporal_receiver_bispectrum_mean(k)


@pytest.mark.parametrize('kind',['zero','nan','length','stride_bool','stride_zero','samples_bool','samples_small','samples_large','masked'])
def test_filter_parameters(kind):
    h=np.ones(8);hop=4;m=32
    if kind=='zero':h[:]=0
    elif kind=='nan':h[0]=np.nan
    elif kind=='length':h=np.ones(4097)
    elif kind=='stride_bool':hop=True
    elif kind=='stride_zero':hop=0
    elif kind=='samples_bool':m=True
    elif kind=='samples_small':m=2
    elif kind=='samples_large':m=257
    elif kind=='masked':h=np.ma.array(h,mask=False)
    with pytest.raises(ValueError):white_filter_temporal_covariance(h,hop,m)


def test_gaussian_temporal_workflow_fixed_models():
    from workflows.bispectrum_temporal_validation import experiment
    for index,label in enumerate(('white','long_average','reference_fft','guarded_average','guarded_reference')):
        q=experiment(label,trials=512,seed=55+index)
        assert q['all_mean_components_within_6se']
        assert not q['actual_temporal_independence_verified']
        assert not q['physical_raw_filter_convolution_performed']
        if label=='long_average':assert q['methods']['distinct']['known_coloured_model_mean'][0]>1e-4
        if label=='guarded_average':assert q['retained_outputs']==15 and q['conditional_temporal_covariance_is_identity']
        if label=='guarded_reference':assert q['retained_outputs']==26 and q['conditional_temporal_covariance_is_identity']


def test_workflow_files_and_existing_output_rejected(tmp_path):
    from workflows.bispectrum_temporal_validation import run
    q=run(tmp_path/'temporal',trials=128)
    assert len(q['cases'])==5 and (tmp_path/'temporal/bispectrum-temporal.png').is_file()
    assert not q['physical_adc_vdif_processed'] and not q['production_rml_noise_model_changed']
    with pytest.raises(FileExistsError):run(tmp_path/'temporal',trials=128)
