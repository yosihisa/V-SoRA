from itertools import permutations
import numpy as np
import pytest
from vsora_simulator.bispectrum_common_temporal import common_temporal_bispectrum_mean
from vsora_simulator.bispectrum_distinct import gaussian_ordinary_bispectrum_mean
from vsora_simulator.bispectrum_temporal import temporal_receiver_bispectrum_mean


def brute_mean(s,k,triangle,distinct):
    m=len(k);i,j,l=triangle;total=0j;count=0
    from itertools import product
    times_iter=permutations(range(m),3) if distinct else product(range(m),repeat=3)
    for times in times_iter:
        for perm in permutations(range(3)):
            term=1+0j
            for edge in range(3):term*=s[(i,j,l)[edge],(j,l,i)[perm[edge]]]*k[times[edge],times[perm[edge]]]
            total+=term
        count+=1
    return total/count


@pytest.mark.parametrize('m',[3,4,5])
def test_all_six_wick_contractions_and_time_triples(m):
    rng=np.random.default_rng(71+m);a=rng.normal(size=(4,4))+1j*rng.normal(size=(4,4));s=np.eye(4)+a @ a.conj().T
    a=rng.normal(size=(m,m+2))+1j*rng.normal(size=(m,m+2));a/=np.sqrt(np.sum(abs(a)**2,axis=1))[:,None];k=a @ a.conj().T
    s0=s.copy();k0=k.copy();q=common_temporal_bispectrum_mean(s,k)
    for row,triangle in enumerate(q['triangles']):
        for distinct,key in [(False,'ordinary_bispectrum_mean'),(True,'distinct_bispectrum_mean')]:
            np.testing.assert_allclose(q[key][row],brute_mean(s,k,triangle,distinct),rtol=1e-11,atol=1e-11)
    np.testing.assert_array_equal(s,s0);np.testing.assert_array_equal(k,k0)
    assert not q['variance_or_likelihood_calculated'] and not q['actual_temporal_independence_verified']


@pytest.mark.parametrize('m,power',[(3,1.),(16,2.),(128,.5)])
def test_white_time_limit(m,power):
    s=np.eye(4)+.1*np.ones((4,4));q=common_temporal_bispectrum_mean(s,power*np.eye(m))
    iid=gaussian_ordinary_bispectrum_mean(power*s,m)
    np.testing.assert_allclose(q['ordinary_bispectrum_mean'],iid['ordinary_product_mean'],rtol=1e-13,atol=0)
    np.testing.assert_allclose(q['distinct_bispectrum_mean'],iid['true_bispectrum'],rtol=1e-13,atol=0)
    np.testing.assert_array_equal(q['distinct_pair_bias'],0);np.testing.assert_array_equal(q['distinct_cycle_bias'],0)


@pytest.mark.parametrize('m',[3,16])
def test_identical_time_samples_are_not_iid(m):
    s=np.eye(3)+.1*np.ones((3,3));q=common_temporal_bispectrum_mean(s,np.ones((m,m)))
    iid_single=gaussian_ordinary_bispectrum_mean(s,1)
    np.testing.assert_allclose(q['distinct_bispectrum_mean'],iid_single['ordinary_product_mean'],rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(q['ordinary_bispectrum_mean'],q['distinct_bispectrum_mean'],rtol=1e-12,atol=1e-12)
    assert not np.allclose(q['distinct_bispectrum_mean'],q['true_marginal_bispectrum'])


def test_zero_source_matches_previous_receiver_formula():
    k=np.full((4,4),-.2);np.fill_diagonal(k,1)
    q=common_temporal_bispectrum_mean(np.eye(3),k);previous=temporal_receiver_bispectrum_mean(np.repeat(k[None],3,axis=0))
    np.testing.assert_allclose(q['distinct_bispectrum_mean'][0],previous['distinct_bispectrum_mean'],rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(q['ordinary_bispectrum_mean'][0],previous['ordinary_bispectrum_mean'],rtol=1e-12,atol=1e-12)
    assert q['distinct_bispectrum_mean'][0].real<0


def test_fixed_complex_station_gain_scales_mean_without_extra_phase():
    s=np.eye(4)+.1*np.ones((4,4));k=.2*np.ones((4,4))+.8*np.eye(4)
    gain=np.array([.4,3,1.5,.75])*np.exp(1j*np.array([.2,-.7,1.1,2.1]))
    q=common_temporal_bispectrum_mean(s,k);r=common_temporal_bispectrum_mean(s*gain[:,None]*gain.conj()[None,:],k)
    factor=np.prod(abs(gain[q['triangles']])**2,axis=1)
    for name in ('true_marginal_bispectrum','distinct_pair_bias','distinct_cycle_bias','distinct_bispectrum_mean','ordinary_bispectrum_mean'):
        np.testing.assert_allclose(r[name],q[name]*factor,rtol=1e-12,atol=1e-12)


@pytest.mark.parametrize('k',[[],np.eye(2),np.eye(257),[[1,2,0],[0,1,0],[0,0,1]],np.full((3,3),np.nan),-np.eye(3),np.zeros((3,3)),np.diag([1,1,2]),np.ma.array(np.eye(3)),np.array([[1,2,0],[2,1,0],[0,0,1]])])
def test_invalid_temporal_covariance(k):
    with pytest.raises(ValueError):common_temporal_bispectrum_mean(np.eye(3),k)


@pytest.mark.parametrize('s',[np.eye(2),np.eye(9),np.ma.array(np.eye(3)),np.full((3,3),np.inf),-np.eye(3)])
def test_invalid_station_covariance(s):
    with pytest.raises(ValueError):common_temporal_bispectrum_mean(s,np.eye(3))


@pytest.mark.parametrize('scale',[1e200,1e-200])
def test_numerical_range_is_rejected(scale):
    with pytest.raises(ValueError):common_temporal_bispectrum_mean(np.eye(3),scale*np.eye(3))


def test_zero_station_power_can_have_zero_mean():
    q=common_temporal_bispectrum_mean(np.zeros((3,3)),np.eye(3));np.testing.assert_array_equal(q['distinct_bispectrum_mean'],0)
