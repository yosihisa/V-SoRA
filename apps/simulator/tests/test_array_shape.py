from itertools import combinations
import numpy as np
import pytest
from vsora_simulator.array_shape import population_closure_signature


def edges(n): return np.array(list(combinations(range(n),2)))


@pytest.mark.parametrize('n',[3,4,8])
def test_point_has_zero_population_signature(n):
    p=edges(n);q=population_closure_signature(np.full(len(p),1000.+0j),p,1000.)
    assert q['phase_rms_from_point']==0.
    assert q['logamp_rms_from_point']==(None if n==3 else 0.)
    assert q['phase_valid_rows']==len(q['triangles'])
    assert q['rows_assumed_statistically_independent'] is False


@pytest.mark.parametrize('n',[4,8])
def test_known_station_gains_cancel_in_population_closures(n):
    p=edges(n);rng=np.random.default_rng(81+n)
    v=(.5+rng.random(len(p)))*np.exp(1j*rng.normal(size=len(p)))
    g=(.4+rng.random(n))*np.exp(1j*rng.normal(size=n))
    q=population_closure_signature(v,p,2.)
    r=population_closure_signature(v*g[p[:,0]]*g[p[:,1]].conj(),p,2.)
    for kind in ('phase','logamp'):
        np.testing.assert_allclose(q[kind+'_values'],r[kind+'_values'],atol=4e-15,rtol=1e-14)


def test_numerical_floor_masks_only_affected_rows():
    p=edges(4);v=np.ones(len(p),complex);v[0]=1e-12
    q=population_closure_signature(v,p,1.)
    assert q['phase_valid']==[False,False,True,True]
    assert q['phase_values'][:2]==[None,None]
    assert q['logamp_valid']==[False,False]
    assert q['logamp_rms_from_point'] is None
    assert q['noise_or_detection_threshold_applied'] is False


@pytest.mark.parametrize('flux',[0.,-1.,np.nan,np.inf,True,1+0j,'1',np.ma.array(1.)])
def test_invalid_flux(flux):
    with pytest.raises(ValueError):population_closure_signature(np.ones(6,complex),edges(4),flux)


@pytest.mark.parametrize('value',[np.ones(6),np.ones((1,6),complex),np.full(6,np.nan+0j),np.full(6,np.inf+0j),np.ma.array(np.ones(6,complex))])
def test_invalid_visibility(value):
    with pytest.raises(ValueError):population_closure_signature(value,edges(4),1.)


@pytest.mark.parametrize('pairs',[edges(4).astype(float),edges(4)[::-1,::-1],np.zeros((6,2),int),np.ma.array(edges(4)),edges(3)])
def test_invalid_pairs(pairs):
    with pytest.raises(ValueError):population_closure_signature(np.ones(6,complex),pairs,1.)


def test_too_many_stations():
    p=edges(9)
    with pytest.raises(ValueError):population_closure_signature(np.ones(len(p),complex),p,1.)


def test_empty_closure_family_is_explicit():
    q=population_closure_signature(np.array([1+0j]),np.array([[0,1]]),1.)
    assert q['phase_values']==[] and q['phase_rms_from_point'] is None


@pytest.mark.parametrize('visibility,flux',[(complex(1.7e308,1.7e308),1.),(1+0j,1e-320),(1e308+0j,1e-10)])
def test_unsupported_numerical_range(visibility,flux):
    with pytest.raises(ValueError):population_closure_signature(np.full(6,visibility),edges(4),flux)
