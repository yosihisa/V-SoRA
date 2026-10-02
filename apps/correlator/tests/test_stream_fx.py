import numpy as np
import pytest
from vsora_correlator.fx import fx_correlate_series
from vsora_correlator.stream_fx import FXAccumulator


@pytest.mark.parametrize('channel_weights',[None,False,True])
def test_chunk_statistics_match_whole_integration(channel_weights):
    rng=np.random.default_rng(73);nf=32;blocks=257
    x=rng.normal(size=(4,nf*blocks))+1j*rng.normal(size=(4,nf*blocks))
    # Gain/continuous tone and unequal holes exercise flags and exposure.
    x[1]*=3.;x[2]+=.8*np.exp(2j*np.pi*np.arange(nf*blocks)*4/nf)
    ok=np.ones(x.shape,bool);ok[0,100:103]=False;ok[1,2030:2110]=False;ok[3,3100:4200]=False
    quality=None if channel_weights is None else {'channel_weights':channel_weights,'min_sk_blocks':24,
        'sk_bounds':[.7,1.3],'exclude_rf_ranges_hz':[[1.42e9+100000,1.42e9+150000]]}
    expected=fx_correlate_series(x,2048000,nf,blocks,1.42e9,valid=ok,spectral_quality=quality,time_offset_s=.002)
    a=FXAccumulator(4,2048000,nf,1.42e9,quality)
    for start in range(0,x.shape[1],nf*37):a.consume(x[:,start:start+nf*37],ok[:,start:start+nf*37])
    actual=a.finish(.002)
    for key,value in expected.items():
        if isinstance(value,np.ndarray):assert np.allclose(actual[key],value,rtol=2e-13,atol=2e-13),key
        else:assert actual[key]==value
    assert a.maximum_chunk_samples==nf*37
    with pytest.raises(ValueError):a.consume(x)


def test_invalid_samples_and_empty_exposure():
    a=FXAccumulator(2,2048000,8,1.42e9,{'channel_weights':True,'min_sk_blocks':24,'sk_bounds':[.5,1.5],'exclude_rf_ranges_hz':[]})
    with pytest.raises(ValueError):a.consume(np.ones((2,7),complex))
    a.consume(np.ones((2,64),complex),np.zeros((2,64),bool));r=a.finish()
    assert np.all(r['weights']==0) and np.all(r['integration_s']==0)
    assert np.all(r['diagnostic_station_flags']==1)
