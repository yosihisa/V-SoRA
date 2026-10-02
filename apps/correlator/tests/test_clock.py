import numpy as np
import pytest
from vsora_correlator.clock import resample_station,estimate_clock_mapping


def signal(t):
    frequency=np.array([-21000,-13000,-7000,1000,5000,17000,22000])
    phase=np.arange(len(frequency))*.9
    return np.exp(2j*np.pi*np.asarray(t)[:,None]*frequency+1j*phase).sum(axis=1)/np.sqrt(len(frequency))


def test_fractional_offsets_and_adc_drift_independent_continuous_wave():
    fs=65536;actual=fs*(1+80e-6);start=3.25/fs;n=32768
    x=signal(start+np.arange(n)/actual);t=np.arange(200,32000)/fs
    out,good=resample_station(x,start,actual,t,fs,23000)
    assert good.all()
    np.testing.assert_allclose(out,signal(t),atol=.0006,rtol=0)


def test_unknown_clock_mapping():
    fs=65536;actual=fs*(1-65e-6);start=-2.4/fs;n=16384
    ref=signal(np.arange(n)/fs);x=signal(start+np.arange(n)/actual)*(.8+.3j)
    result=estimate_clock_mapping(ref,x,fs)
    assert abs(result['sample_rate_error_ppm']+65)<.02
    assert abs(result['effective_start_s']-start)*fs<.002
    assert result['coherence']>.99999


def test_guard_band_edges_and_invalid_support():
    fs=65536;x=signal(np.arange(4096)/fs);mask=np.ones(4096,bool);mask[2000:2010]=False
    t=np.arange(1800,2200)/fs
    out,good=resample_station(x,0,fs,t,fs,23000,mask)
    assert not good[168:242].all() and good[:150].all()
    assert np.all(out[~good]==0)
    with pytest.raises(ValueError,match='guard samples'): resample_station(x,0,fs,np.array([0,1/fs]),fs,23000)
    with pytest.raises(ValueError,match='Nyquist guard'): resample_station(x,0,fs,t,fs,32000)


def test_continuous_geometric_delay_and_rf_phase_sign():
    fs=65536;fc=1.42e9;n=8192;t=np.arange(100,8000)/fs;delays=np.array([0,1.4e-6,-.7e-6])
    outputs=[]
    for delay in delays:
        # Forward arrival is early at positive position dot source/c.
        x=signal(np.arange(n)/fs+delay)*np.exp(2j*np.pi*fc*delay)
        aligned,_=resample_station(x,0,fs,t-delay,fs,23000)
        outputs.append(aligned*np.exp(-2j*np.pi*fc*delay))
    np.testing.assert_allclose(outputs,np.broadcast_to(signal(t),(3,len(t))),atol=.0006,rtol=0)
