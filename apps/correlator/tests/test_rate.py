from itertools import combinations
import numpy as np
import pytest
from vsora_correlator.rate import estimate_station_rates


def data(seed=22,noise=True):
    rng=np.random.default_rng(seed);p=np.array(list(combinations(range(4),2)))
    t=(np.arange(128)+.5)*.002;rates=np.array([0,17.3,-11.7,26.1])
    sky=rng.uniform(.5,1.5,(8,6))*np.exp(1j*rng.uniform(-np.pi,np.pi,(8,6)))
    v=sky[None]*np.exp(2j*np.pi*t[:,None,None]*(rates[p[:,0]]-rates[p[:,1]])[None,None])
    if noise: v+=.1*(rng.normal(size=v.shape)+1j*rng.normal(size=v.shape))
    return {'visibilities':v,'weights':np.full(v.shape,100.),'times_s':t,'pairs':p},rates


def test_unknown_sky_channel_phase_and_station_rate():
    d,true=data();r=estimate_station_rates(d)
    assert np.max(abs(np.array(r['station_rates_hz'])-true))<.02
    assert r['accepted_baselines']==6
    assert not r['amplitude_or_sky_phase_calibration']


def test_rate_gain_invariance():
    d,_=data(noise=False);rng=np.random.default_rng(7)
    gain=np.exp(rng.uniform(-2,2,(8,4))+1j*rng.uniform(-5,5,(8,4)))
    p=d['pairs'];g=gain[:,p[:,0]]*gain[:,p[:,1]].conj()
    changed={**d,'visibilities':d['visibilities']*g[None],'weights':d['weights']/abs(g[None])**2}
    a=estimate_station_rates(d);b=estimate_station_rates(changed)
    assert np.max(abs(np.array(a['station_rates_hz'])-b['station_rates_hz']))<1e-7


def test_missing_direct_reference_link_uses_graph():
    d,true=data();d['weights'][:,:,0]=0;d['weights'][:,:,1]=0
    r=estimate_station_rates(d)
    assert np.max(abs(np.array(r['station_rates_hz'])-true))<.03
    d['weights'][:,:,2]=0
    with pytest.raises(ValueError,match='disconnected'):estimate_station_rates(d)


def test_bad_search_and_time_axis():
    d,_=data()
    with pytest.raises(ValueError,match='Nyquist'):estimate_station_rates(d,max_rate_hz=500)
    with pytest.raises(ValueError,match='disconnected'):estimate_station_rates(d,max_rate_hz=5)
    long={**d,'times_s':d['times_s']*15}
    with pytest.raises(ValueError,match='three seconds'):estimate_station_rates(long)
    d['times_s'][3]+=.0001
    with pytest.raises(ValueError,match='uniform'):estimate_station_rates(d)


def test_noise_only_is_not_detected():
    for seed in range(20):
        d,_=data(seed);rng=np.random.default_rng(500+seed)
        d['visibilities']=.1*(rng.normal(size=d['visibilities'].shape)+1j*rng.normal(size=d['visibilities'].shape))
        with pytest.raises(ValueError,match='disconnected'):estimate_station_rates(d)




def test_three_second_uniform_stable_unknown_sky():
    d,true=data(14);rng=np.random.default_rng(39)
    times=(np.arange(750)+.5)*.004;pairs=d['pairs']
    sky=rng.uniform(.5,1.5,(8,6))*np.exp(1j*rng.uniform(-np.pi,np.pi,(8,6)))
    v=sky[None]*np.exp(2j*np.pi*times[:,None,None]*(true[pairs[:,0]]-true[pairs[:,1]])[None,None,:])
    v+=.01*(rng.normal(size=v.shape)+1j*rng.normal(size=v.shape))
    d.update(visibilities=v,weights=np.full(v.shape,1e4),times_s=times)
    r=estimate_station_rates(d)
    assert max(abs(np.array(r['station_rates_hz'])-true))<.002
