from itertools import permutations
import numpy as np
import pytest
from vsora_simulator.bispectrum_moments import gaussian_distinct_bispectrum_moments,overlap_weights


def station_model():
    phase=np.exp(1j*np.array([0,.7,1.9,-.5]))
    return np.eye(4)+.2*np.ones((4,4))+.15*phase[:,None]*phase.conj()[None,:]


def terms(triangle,times):
    i,j,k=triangle;a,b,c=times
    return [(i,a,1),(j,a,-1),(j,b,1),(k,b,-1),(k,c,1),(i,c,-1)]


def independent_wick_moment(variables,s):
    result=1+0j
    for time in {t for _,t,_ in variables}:
        positive=[i for i,t,sign in variables if t==time and sign==1]
        negative=[i for i,t,sign in variables if t==time and sign==-1]
        if len(positive)!=len(negative):return 0j
        result*=sum(np.prod([s[i,j] for i,j in zip(positive,p)]) for p in permutations(negative))
    return result


@pytest.mark.parametrize('m',[3,4])
def test_all_time_index_wick_enumeration(m):
    s=station_model();triangles=np.array([[0,1,2],[0,2,3]])
    q=gaussian_distinct_bispectrum_moments(s,m,triangles);triples=list(permutations(range(m),3))
    for i,t in enumerate(triangles):
        for j,u in enumerate(triangles):
            for conjugate,key in ((True,'complex_covariance'),(False,'complex_pseudocovariance')):
                second=0j
                for a in triples:
                    left=terms(t,a)
                    for b in triples:
                        right=terms(u,b)
                        if conjugate:right=[(station,time,-sign) for station,time,sign in right]
                        second+=independent_wick_moment(left+right,s)
                mean_second=q['mean'][j].conjugate() if conjugate else q['mean'][j]
                expected=second/len(triples)**2-q['mean'][i]*mean_second
                assert q[key][i,j]==pytest.approx(expected,rel=1e-11,abs=1e-12)


@pytest.mark.parametrize('m',[3,4,5,6,128,1000000])
def test_partial_matching_weights_partition_sample_assignments(m):
    assert np.dot(overlap_weights(m),[1,9,18,6])==pytest.approx(1,rel=1e-14)


@pytest.mark.parametrize('m',[3,8,128,1000000])
def test_null_and_rank_one_limits(m):
    power=np.array([1.,2.,3.,4.]);q=gaussian_distinct_bispectrum_moments(np.diag(power),m)
    factor=np.prod(power[q['triangles']],axis=1)**2/(m*(m-1)*(m-2))
    np.testing.assert_allclose(q['complex_covariance'],np.diag(factor),rtol=1e-13,atol=0)
    np.testing.assert_array_equal(q['complex_pseudocovariance'],0)
    rank=gaussian_distinct_bispectrum_moments(np.ones((4,4)),m)
    expected=np.dot(overlap_weights(m),[1*(2**0-1),9*(2**1-1),18*(2**2-1),6*(2**3-1)])
    np.testing.assert_allclose(rank['complex_covariance'],expected,rtol=1e-13)
    np.testing.assert_allclose(rank['complex_pseudocovariance'],expected,rtol=1e-13)
    np.testing.assert_allclose(rank['real_covariance'][4:,:],0,atol=0)


def test_fixed_gain_conjugation_subset_psd_and_input_preserved():
    s=station_model();original=s.copy();q=gaussian_distinct_bispectrum_moments(s,32)
    gain=np.array([.4,3,1.5,.75])*np.exp(1j*np.array([.2,-.7,1.1,2.1]))
    r=gaussian_distinct_bispectrum_moments(s*gain[:,None]*gain.conj()[None,:],32)
    scale=np.prod(abs(gain[q['triangles']])**2,axis=1)
    np.testing.assert_allclose(r['mean'],q['mean']*scale,rtol=1e-12,atol=1e-12)
    conjugate=gaussian_distinct_bispectrum_moments(s.conj(),32)
    for key in ('complex_covariance','complex_pseudocovariance'):
        np.testing.assert_allclose(r[key],q[key]*scale[:,None]*scale[None,:],rtol=1e-12,atol=1e-12)
        np.testing.assert_allclose(conjugate[key],q[key].conj(),rtol=1e-12,atol=1e-12)
    subset=gaussian_distinct_bispectrum_moments(s,32,[[0,2,3]])
    np.testing.assert_allclose(subset['complex_covariance'],q['complex_covariance'][2:3,2:3])
    np.testing.assert_array_equal(s,original)
    assert np.linalg.eigvalsh(q['real_covariance']).min()>-1e-12
    assert not q['distribution_gaussian_assumed'] and not q['actual_temporal_independence_verified']
    assert not q['production_rml_noise_model_changed']


@pytest.mark.parametrize('kind',['masked','masked_triangles','shape','few','many','nan','nonhermitian','negative','samples_bool','samples_small','samples_large','samples_float','overflow','underflow','triangles'])
def test_input_rejections(kind):
    s=station_model();m=32;t=None
    if kind=='masked':s=np.ma.array(s,mask=False)
    elif kind=='masked_triangles':t=np.ma.array([[0,1,2]],mask=False)
    elif kind=='shape':s=s[:,:3]
    elif kind=='few':s=np.eye(2)
    elif kind=='many':s=np.eye(9)
    elif kind=='nan':s[0,0]=np.nan
    elif kind=='nonhermitian':s[0,1]=2j
    elif kind=='negative':s=-np.eye(4)
    elif kind=='samples_bool':m=True
    elif kind=='samples_small':m=2
    elif kind=='samples_large':m=1000001
    elif kind=='samples_float':m=32.
    elif kind=='overflow':s=np.eye(4)*1e60
    elif kind=='underflow':s=np.eye(4)*1e-200
    elif kind=='triangles':t=[[0,1,2],[0,1,2]]
    with pytest.raises(ValueError):gaussian_distinct_bispectrum_moments(s,m,t)


def test_fixed_gaussian_joint_moments_models():
    from workflows.bispectrum_moments_validation import experiment
    for i,label in enumerate(('zero','weak','low','two_components','rank_one')):
        q=experiment(label,trials=512,seed=59+i)
        assert q['all_means_and_real_covariances_within_6se']
        assert not q['gaussian_bispectrum_likelihood_assumed'] and not q['observed_sample_selection_used']
        if label=='zero':np.testing.assert_allclose(q['exact_complex_to_null_variance_ratio_range'],1)
        if label=='rank_one':assert q['maximum_absolute_offdiagonal_real_correlation']>.99


def test_workflow_files_and_existing_output(tmp_path):
    from workflows.bispectrum_moments_validation import run
    q=run(tmp_path/'moments')
    assert len(q['cases'])==5 and (tmp_path/'moments/bispectrum-moments.png').is_file()
    assert not q['production_rml_noise_model_changed'] and not q['gaussian_bispectrum_likelihood_assumed']
    with pytest.raises(FileExistsError):run(tmp_path/'moments')


def test_failed_fixed_criterion_is_saved_as_failure(tmp_path):
    import json
    from workflows.bispectrum_moments_validation import run
    with pytest.raises(RuntimeError):run(tmp_path/'too_few',trials=128)
    q=json.loads((tmp_path/'too_few/summary.json').read_text())
    assert q['state']=='failed_validation'
    assert any(not c['all_means_and_real_covariances_within_6se'] for c in q['cases'])
    assert (tmp_path/'too_few/bispectrum-moments.png').is_file()
