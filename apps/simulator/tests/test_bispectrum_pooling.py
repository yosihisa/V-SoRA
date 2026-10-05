from itertools import permutations
import numpy as np
import pytest
from vsora_simulator.bispectrum_pooling import pooled_covariance_bispectrum_mean


def model(groups=4):
    s=np.eye(4)+.1*np.ones((4,4))
    gain=np.exp(2j*np.pi*np.arange(groups)[:,None]*np.arange(4)[None,:]/groups)
    return gain[:,:,None]*s*gain[:,None,:].conj()


@pytest.mark.parametrize('groups,m',[(1,3),(2,3),(3,4)])
def test_mean_against_independent_ordered_triples(groups,m):
    rng=np.random.default_rng(74);z=rng.normal(size=(groups,4,4))+1j*rng.normal(size=(groups,4,4))
    s=z @ z.conj().transpose(0,2,1);before=s.copy();q=pooled_covariance_bispectrum_mean(s,m)
    expanded=np.repeat(s,m,axis=0)
    for index,(i,j,k) in enumerate(q['triangles']):
        products=[expanded[a,i,j]*expanded[b,j,k]*expanded[c,k,i] for a,b,c in permutations(range(groups*m),3)]
        assert np.allclose(np.mean(products),q['pooled_u3_mean'][index],rtol=1e-12,atol=1e-12)
    np.testing.assert_array_equal(s,before)


@pytest.mark.parametrize('groups',[1,4,16])
def test_same_covariance_limit(groups):
    s=np.eye(4)+.1*np.ones((4,4));q=pooled_covariance_bispectrum_mean(np.repeat(s[None],groups,axis=0),32)
    np.testing.assert_allclose(q['pooled_u3_mean'],q['equal_group_u3_mean'],rtol=1e-12,atol=1e-15)


def test_frequency_dependent_phase_changes_pooling_mean():
    q=pooled_covariance_bispectrum_mean(model(),32);n=128
    np.testing.assert_allclose(q['equal_group_u3_mean'],.001,atol=1e-15)
    np.testing.assert_allclose(q['pooled_u3_mean'],.002/((n-1)*(n-2)),atol=1e-15)
    assert not q['heterogeneous_group_covariance_calculated'] and not q['frequency_phase_alignment_performed']


def test_one_fixed_gain_transforms_both_means():
    s=model();gain=np.array([1.2,.8,2.,.7])*np.exp(1j*np.array([.7,-.2,1.3,2.1]))
    original=pooled_covariance_bispectrum_mean(s,32)
    changed=pooled_covariance_bispectrum_mean(gain[None,:,None]*s*gain[None,None,:].conj(),32)
    factor=np.prod(abs(gain[original['triangles']])**2,axis=1)
    for key in ('equal_group_u3_mean','pooled_u3_mean'):np.testing.assert_allclose(changed[key],original[key]*factor,rtol=1e-12,atol=1e-15)


@pytest.mark.parametrize('m',[True,2,3.,-1,1000001])
def test_bad_sample_count(m):
    with pytest.raises(ValueError):pooled_covariance_bispectrum_mean(model(),m)


@pytest.mark.parametrize('s',[np.eye(4),np.ones((0,4,4)),np.ones((65,4,4)),np.ones((1,2,2)),np.ones((1,4,3)),np.full((1,4,4),np.nan),-np.eye(4)[None],np.ma.array(np.eye(4)[None],mask=False)])
def test_bad_covariance_groups(s):
    with pytest.raises(ValueError):pooled_covariance_bispectrum_mean(s,3)


def test_triangle_selection_and_zero_model():
    q=pooled_covariance_bispectrum_mean(np.zeros((2,4,4)),3,[[0,1,3]])
    np.testing.assert_array_equal(q['pooled_u3_mean'],0)
    with pytest.raises(ValueError):pooled_covariance_bispectrum_mean(model(),3,[[1,0,2]])
