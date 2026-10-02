import numpy as np
import pytest
from vsora_correlator.quality import channel_diagnostics,validate_quality
from vsora_correlator.fx import fx_correlate_series


QUALITY={'channel_weights':True,'min_sk_blocks':128,'sk_bounds':[.3,3.], 'exclude_rf_ranges_hz':[]}


def fixture(seed=1,m=1024,c=64,s=4):
    rng=np.random.default_rng(seed)
    return (rng.normal(size=(m,c,s))+1j*rng.normal(size=(m,c,s)))/np.sqrt(2)


def test_gaussian_and_bandpass_scale_invariance():
    x=fixture();valid=np.ones((len(x),4),bool);f=np.arange(64)+1.42e9
    d=channel_diagnostics(x,valid,f,QUALITY)
    assert not d['diagnostic_station_flags'].any()
    assert abs(d['diagnostic_station_sk'].mean()-1)<.02
    gains=np.geomspace(.01,100,64)[:,None]*np.array([1,2,3,4])[None,:]
    scaled=channel_diagnostics(x*gains[None,:,:],valid,f,QUALITY)
    np.testing.assert_allclose(scaled['diagnostic_station_sk'],d['diagnostic_station_sk'],atol=1e-12)


def test_continuous_and_impulsive_interference_flag_affected_pairs():
    x=fixture();x[:,10,0]=100; x[0,20,1]+=1000
    samples=np.fft.ifft(x,axis=1,norm='ortho').transpose(2,0,1).reshape(4,-1)
    r=fx_correlate_series(samples,2048000,64,1024,spectral_quality=QUALITY)
    frequency=1.42e9+np.fft.fftfreq(64,1/2048000);i10=np.flatnonzero(r['frequencies_hz']==frequency[10])[0]
    i20=np.flatnonzero(r['frequencies_hz']==frequency[20])[0]
    assert r['diagnostic_station_flags'][0,i10,0]&2
    assert r['diagnostic_station_flags'][0,i20,1]&4
    for b,(i,j) in enumerate(r['pairs']):
        assert (r['weights'][0,i10,b]==0)==(0 in (i,j))
        assert (r['weights'][0,i20,b]==0)==(1 in (i,j))
    assert np.isfinite(r['vis_jy']).all()


def test_insufficient_blocks_and_manual_exclusion():
    x=fixture(m=16);valid=np.ones((16,4),bool);valid[:,3]=False
    quality={**QUALITY,'exclude_rf_ranges_hz':[[1.42e9+5,1.42e9+7]]}
    r=channel_diagnostics(x,valid,np.arange(64)+1.42e9,quality)
    assert not r['diagnostic_station_sk_eligible'].any()
    assert np.all(r['diagnostic_station_flags'][5:8]&8)
    assert np.all(r['diagnostic_station_flags'][:,3]&1)
    assert not np.any(r['diagnostic_station_flags'][:5,:3])


def test_channel_weights_follow_colored_noise_power():
    x=fixture(m=4096,c=32,s=3);g=np.linspace(.5,2,32)
    x*=g[None,:,None]
    samples=np.fft.ifft(x,axis=1,norm='ortho').transpose(2,0,1).reshape(3,-1)
    r=fx_correlate_series(samples,2048000,32,4096,spectral_quality=QUALITY)
    order=np.argsort(1.42e9+np.fft.fftfreq(32,1/2048000))
    expected=2*4096/g[order]**4
    np.testing.assert_allclose(r['weights'][0,:,0],expected,rtol=.08)


@pytest.mark.parametrize('change',[{'channel_weights':1},{'min_sk_blocks':16},{'sk_bounds':[1,2]}, {'exclude_rf_ranges_hz':[[4,3]]}])
def test_quality_config_rejected(change):
    with pytest.raises(ValueError): validate_quality({**QUALITY,**change})
