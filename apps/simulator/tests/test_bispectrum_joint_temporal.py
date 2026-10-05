from itertools import permutations,product
import numpy as np
import pytest
from vsora_simulator.bispectrum_common_temporal import common_temporal_bispectrum_mean
from vsora_simulator.bispectrum_joint_temporal import joint_temporal_bispectrum_mean


def brute(c,triangle,distinct):
    m,n=c.shape[:2];total=0j;count=0
    for times in permutations(range(m),3) if distinct else product(range(m),repeat=3):
        positive=list(zip(times,triangle));negative=list(zip(times,triangle[[1,2,0]]))
        sub=np.array([[c[t,i,u,j] for u,j in negative] for t,i in positive])
        total+=sum(np.prod(sub[np.arange(3),p]) for p in permutations(range(3)));count+=1
    return total/count


@pytest.mark.parametrize('m,n',[(3,3),(4,4),(5,3)])
def test_general_covariance_all_contractions(m,n):
    rng=np.random.default_rng(780+m);a=rng.normal(size=(m*n,m*n+2))+1j*rng.normal(size=(m*n,m*n+2));c=(a @ a.conj().T/(m*n)).reshape(m,n,m,n);before=c.copy()
    q=joint_temporal_bispectrum_mean(c)
    for i,t in enumerate(q['triangles']):
        for distinct,key in [(False,'ordinary_bispectrum_mean'),(True,'distinct_bispectrum_mean')]:np.testing.assert_allclose(q[key][i],brute(c,t,distinct),rtol=1e-12,atol=1e-12)
    np.testing.assert_array_equal(c,before);assert not q['variance_or_likelihood_calculated']


@pytest.mark.parametrize('m,n',[(3,3),(8,4),(32,8)])
@pytest.mark.parametrize('kind',['white','correlated'])
def test_common_space_time_limit(m,n,kind):
    s=np.eye(n)+.1*np.ones((n,n));k=np.eye(m) if kind=='white' else .4**abs(np.arange(m)[:,None]-np.arange(m)[None,:])
    c=np.einsum('tu,ij->tiuj',k,s);q=joint_temporal_bispectrum_mean(c);known=common_temporal_bispectrum_mean(s,k)
    for key in ('ordinary_bispectrum_mean','distinct_bispectrum_mean'):np.testing.assert_allclose(q[key],known[key],rtol=1e-12,atol=1e-12)


def test_fixed_gain_and_common_changing_phase():
    m,n=8,4;s=np.eye(n)+.1*np.ones((n,n));c=np.einsum('tu,ij->tiuj',np.eye(m),s)
    g=np.array([.5,2,3,.7])*np.exp(1j*np.arange(n));q=joint_temporal_bispectrum_mean(c);r=joint_temporal_bispectrum_mean(c*g[None,:,None,None]*g.conj()[None,None,None,:])
    factor=np.prod(abs(g[q['triangles']])**2,axis=1)
    for key in ('ordinary_bispectrum_mean','distinct_bispectrum_mean'):np.testing.assert_allclose(r[key],q[key]*factor,rtol=1e-12,atol=1e-12)
    h=np.exp(2j*np.pi*np.arange(m)*.31);r=joint_temporal_bispectrum_mean(c*h[:,None,None,None]*h.conj()[None,None,:,None])
    for key in ('ordinary_bispectrum_mean','distinct_bispectrum_mean'):np.testing.assert_allclose(r[key],q[key],rtol=1e-12,atol=1e-12)


def test_station_time_phase_leaves_instant_mean_but_changes_u3():
    m,n=8,4;s=np.eye(n)+.1*np.ones((n,n));c=np.einsum('tu,ij->tiuj',np.eye(m),s)
    phase=np.exp(2j*np.pi*np.arange(m)[:,None]*np.arange(n)[None,:]/m)
    changed=c*phase[:,:,None,None]*phase.conj()[None,None,:,:]
    q=joint_temporal_bispectrum_mean(c);r=joint_temporal_bispectrum_mean(changed)
    np.testing.assert_allclose(r['instantaneous_population_bispectrum'],q['instantaneous_population_bispectrum'],rtol=1e-12,atol=1e-12)
    assert np.max(abs(r['distinct_bispectrum_mean']-q['distinct_bispectrum_mean']))>1e-4
    corrected=changed*phase.conj()[:,:,None,None]*phase[None,None,:,:]
    np.testing.assert_allclose(joint_temporal_bispectrum_mean(corrected)['distinct_bispectrum_mean'],q['distinct_bispectrum_mean'],rtol=1e-12,atol=1e-12)


def test_zero_and_subset():
    c=np.einsum('tu,ij->tiuj',np.eye(3),np.eye(4));q=joint_temporal_bispectrum_mean(c,[[0,2,3]])
    assert q['triangles'].tolist()==[[0,2,3]]
    np.testing.assert_array_equal(joint_temporal_bispectrum_mean(np.zeros((3,4,3,4)))['distinct_bispectrum_mean'],0)


@pytest.mark.parametrize('c',[[],np.eye(9),np.zeros((2,3,2,3)),np.zeros((33,3,33,3)),np.zeros((3,2,3,2)),np.zeros((3,9,3,9)),np.zeros((3,3,4,3)),np.full((3,3,3,3),np.nan),np.full((3,3,3,3),True),np.ma.array(np.zeros((3,3,3,3)))])
def test_invalid_shape_dtype(c):
    with pytest.raises(ValueError):joint_temporal_bispectrum_mean(c)


@pytest.mark.parametrize('kind',['nonhermitian','indefinite','large','small','badtriangles','maskedtriangles'])
def test_invalid_covariance_and_range(kind):
    c=np.eye(9,dtype=complex).reshape(3,3,3,3);triangles=None
    if kind=='nonhermitian':c[0,0,1,1]=.1j
    if kind=='indefinite':c[0,0,0,0]=-1
    if kind=='large':c*=1e200
    if kind=='small':c*=1e-200
    if kind=='badtriangles':triangles=[[0,0,2]]
    if kind=='maskedtriangles':triangles=np.ma.array([[0,1,2]])
    with pytest.raises(ValueError):joint_temporal_bispectrum_mean(c,triangles)


@pytest.mark.parametrize("complex_input",[False,True])
def test_extended_precision_overflow_is_rejected(complex_input):
    c=np.eye(9,dtype=np.longdouble).reshape(3,3,3,3)*np.longdouble("1e400")
    if complex_input:c=c.astype(np.clongdouble)
    with pytest.raises(ValueError,match="complex128 range"):joint_temporal_bispectrum_mean(c)
