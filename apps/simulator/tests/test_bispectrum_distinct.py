from itertools import permutations
import numpy as np
import pytest
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum,gaussian_ordinary_bispectrum_mean


def raw(m=7,n=4):
    rng=np.random.default_rng(53)
    return rng.normal(size=(m,n))+1j*rng.normal(size=(m,n))


@pytest.mark.parametrize('m',[3,4,7])
def test_inclusion_exclusion_matches_all_ordered_distinct_triples(m):
    x=raw(m);q=distinct_sample_bispectrum(x)
    for a,(i,j,k) in enumerate(q['triangles']):
        z1=x[:,i]*x[:,j].conj();z2=x[:,j]*x[:,k].conj();z3=x[:,k]*x[:,i].conj()
        brute=sum(z1[r]*z2[s]*z3[t] for r,s,t in permutations(range(m),3))/(m*(m-1)*(m-2))
        assert q['distinct_sample_bispectrum'][a]==pytest.approx(brute,rel=1e-11,abs=1e-12)
        assert q['ordinary_visibility_product'][a]==pytest.approx(z1.mean()*z2.mean()*z3.mean())
    assert not q['input_sample_independence_verified'] and not q['closure_phase_unbiased_guarantee']
    assert not q['generating_truth_used'] and not q['production_rml_noise_model_changed']


def test_gain_transform_and_conjugation():
    x=raw();q=distinct_sample_bispectrum(x);gain=np.array([.4,3,1.5,.75])*np.exp(1j*np.array([.3,-1,2,1.1]))
    transformed=distinct_sample_bispectrum(x*gain)
    factor=np.prod(abs(gain[q['triangles']])**2,axis=-1)
    for key in ('distinct_sample_bispectrum','ordinary_visibility_product'):
        np.testing.assert_allclose(transformed[key],q[key]*factor,rtol=1e-11,atol=1e-12)
        np.testing.assert_allclose(distinct_sample_bispectrum(x.conj())[key],q[key].conj(),rtol=1e-11,atol=1e-12)


def test_batch_subset_and_complex64_promoted():
    x=np.stack([raw(),raw()*2]);q=distinct_sample_bispectrum(x,[[0,2,3]])
    np.testing.assert_allclose(q['distinct_sample_bispectrum'][:,0],[distinct_sample_bispectrum(a)['distinct_sample_bispectrum'][2] for a in x])
    a=x.astype(np.complex64);b=distinct_sample_bispectrum(a)['distinct_sample_bispectrum']
    assert b.dtype==np.complex128
    np.testing.assert_array_equal(b,distinct_sample_bispectrum(a.astype(np.complex128))['distinct_sample_bispectrum'])


def test_saved_covariance_and_count_insufficient_to_reconstruct_u3():
    x=raw(m=7,n=3);rotation=np.linalg.qr(np.random.default_rng(54).normal(size=(7,7)))[0]
    y=rotation @ x
    np.testing.assert_allclose(x.T @ x.conj(),y.T @ y.conj(),rtol=1e-12,atol=1e-12)
    q=distinct_sample_bispectrum(x);r=distinct_sample_bispectrum(y)
    np.testing.assert_allclose(q['ordinary_visibility_product'],r['ordinary_visibility_product'],rtol=1e-12,atol=1e-12)
    assert abs(q['distinct_sample_bispectrum'][0]-r['distinct_sample_bispectrum'][0])>1e-3


@pytest.mark.parametrize('m',[1,2,3,32,128])
def test_gaussian_naive_expectation_matches_index_partitions(m):
    phase=np.exp(1j*np.array([0,.7,1.9]));s=.2*np.ones((3,3))+.15*phase[:,None]*phase.conj()[None,:]+np.eye(3)
    q=gaussian_ordinary_bispectrum_mean(s,m);a,b,c=s[0,1],s[1,2],s[2,0];truth=a*b*c
    eab=a*b+s[0,2]*s[1,1];eac=a*c+s[0,0]*s[2,1];ebc=b*c+s[1,0]*s[2,2]
    permanent=sum(np.prod([s[i,p[i]] for i in range(3)]) for p in permutations(range(3)))
    partition=(m-1)*(m-2)/m**2*truth+(m-1)/m**2*(eab*c+eac*b+ebc*a)+permanent/m**2
    assert q['ordinary_product_mean'][0]==pytest.approx(partition,rel=1e-12,abs=1e-12)


def test_gaussian_zero_and_rank_one_limits():
    for m in (1,3,32,128):
        q=gaussian_ordinary_bispectrum_mean(np.diag([1.,2.,3.]),m)
        assert q['true_bispectrum'][0]==0 and q['ordinary_product_mean'][0]==pytest.approx(6/m**2)
        q=gaussian_ordinary_bispectrum_mean(np.ones((3,3)),m)
        assert q['ordinary_product_mean'][0]==pytest.approx((m+1)*(m+2)/m**2)


@pytest.mark.parametrize('kind',['few','stations','many_stations','real','nan','inf','empty','masked','overflow','work_limit'])
def test_voltage_input_rejections(kind):
    x=raw()
    if kind=='few':x=x[:2]
    elif kind=='stations':x=x[:,:2]
    elif kind=='many_stations':x=raw(n=9)
    elif kind=='real':x=x.real
    elif kind=='nan':x[0,0]=np.nan
    elif kind=='inf':x[0,0]=np.inf
    elif kind=='empty':x=np.empty((0,7,4),complex)
    elif kind=='masked':x=np.ma.array(x,mask=False)
    elif kind=='overflow':x[:]=1e100+1e100j
    elif kind=='work_limit':x=np.broadcast_to(np.array(1+0j),(1001,1000,8))
    with pytest.raises(ValueError):distinct_sample_bispectrum(x)


@pytest.mark.parametrize('t',[[[1,0,2]],[[0,1,1]],[[0,1,4]],[[0,1,2],[0,1,2]],[[0.,1.,2.]],[],[0,1,2]])
def test_triangle_rejections(t):
    with pytest.raises(ValueError):distinct_sample_bispectrum(raw(),t)


@pytest.mark.parametrize('kind',['shape','negative','nonhermitian','samples_bool','samples_zero'])
def test_gaussian_covariance_rejections(kind):
    s=np.eye(3,dtype=complex);m=32
    if kind=='shape':s=s[:,:2]
    elif kind=='negative':s[0,0]=-1
    elif kind=='nonhermitian':s[0,1]=1j
    elif kind=='samples_bool':m=True
    elif kind=='samples_zero':m=0
    with pytest.raises(ValueError):gaussian_ordinary_bispectrum_mean(s,m)


def test_gaussian_fixed_models_and_unresolved_weak_signal():
    from workflows.bispectrum_distinct_validation import experiment
    for label in ('zero_source','weak_unresolved','low_snr','two_components','rank_one'):
        q=experiment(label,trials=512,seed=53)
        assert q['all_mean_components_within_6se']
        assert not q['estimator_generating_truth_used'] and not q['closure_phase_unbiased_guarantee']
        if label=='weak_unresolved':assert not q['known_true_mean_above_six_mc_standard_errors']
        if label=='zero_source':assert q['ordinary_analytic_bias'][0]>0 and q['true_bispectrum']==[0,0]


def test_workflow_summary_and_plot(tmp_path):
    from workflows.bispectrum_distinct_validation import run
    q=run(tmp_path/'check',trials=128)
    assert len(q['cases'])==5 and (tmp_path/'check/bispectrum-distinct.png').is_file()
    assert not q['physical_adc_vdif_processed'] and not q['production_correlator_statistics_changed']
    with pytest.raises(FileExistsError):run(tmp_path/'check',trials=128)
