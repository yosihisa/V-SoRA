import numpy as np
from vsora_simulator.iq import generate_iq
from vsora_correlator.fx import fx_correlate_series,remove_fringe_rate
from vsora_correlator.fringe import solve_fringe,apply_calibration
from vsora_formats.vdif import write_vdif,iter_vdif_frames,read_vdif


def test_short_fx_matches_independent_sample_correlation():
    rng=np.random.default_rng(7);common=rng.normal(size=32768)+1j*rng.normal(size=32768)
    x=np.array([common,common*(.8+.2j),common*(-.4+.9j)])
    result=fx_correlate_series(x,2048000,128,32)
    for time in range(8):
        block=x[:,time*4096:(time+1)*4096]
        expected=np.array([np.mean(block[i]*block[j].conj()) for i,j in result['pairs']])
        np.testing.assert_allclose(result['vis_jy'][time].mean(axis=0),expected,atol=1e-12)
    assert np.all(np.diff(result['frequencies_hz'])>0)
    assert result['times_s'][0]==.001


def test_voltage_rate_rephasing_before_averaging():
    fs=2048000;t=np.arange(16384)/fs;rate=np.array([0,26.1,-11.7])
    x=np.exp(2j*np.pi*rate[:,None]*(t[None,:]-.2))
    corrected=remove_fringe_rate(x,fs,rate,time_reference_s=.2)
    np.testing.assert_allclose(corrected,1,atol=1e-14)


def test_iq_unknown_rate_and_delay_then_fit():
    fs=2048000;fc=1.42e9;nfft=64;groups=32;blocks=128
    pairs=np.array([(0,1),(0,2),(1,2)]);image=np.zeros((16,16));image[8,8]=1000
    delay=np.array([0,1.3e-6,-.9e-6]);rate=np.array([0,17.3,-11.7]);phase=np.array([0,.3,-.7])
    x,_=generate_iq(np.zeros((3,3)),pairs,image,16,np.full(3,500.),fs,fc,nfft,groups*blocks,77,delay)
    fref=fc-fs/(2*nfft);t=np.arange(x.shape[1])/fs;tm=(x.shape[1]/fs)/2
    x*=np.exp(1j*(phase[:,None]-2*np.pi*fref*delay[:,None]+2*np.pi*rate[:,None]*(t[None,:]-tm)))
    result=fx_correlate_series(x,fs,nfft,blocks,fc)
    model=np.ones(result['vis_jy'].shape)*1000
    cal=solve_fringe(result['vis_jy'],model,result['weights'],pairs,result['times_s'],result['frequencies_hz'])
    np.testing.assert_allclose(cal['delay_s'],delay,atol=1e-8,rtol=0)
    np.testing.assert_allclose(cal['rate_hz'],rate,atol=.08,rtol=0)
    corrected,w=apply_calibration(result['vis_jy'],result['weights'],pairs,cal,result['times_s'],result['frequencies_hz'])
    mean=np.sum(corrected*w,axis=(0,1))/np.sum(w,axis=(0,1))
    np.testing.assert_allclose(mean,1000,rtol=.02)


def test_detected_fringe_with_low_per_channel_snr():
    rng=np.random.default_rng(12);p=np.array([(0,1),(0,2),(1,2)])
    t=np.arange(32)*.004;f=1.42e9+np.arange(64)*32000
    model=np.ones((len(t),len(f),3))*1000
    de=np.array([0,1e-6,-2e-6]);ra=np.array([0,17.,-11.])
    response=np.exp(2j*np.pi*((t[:,None,None]-t.mean())*ra+(f[None,:,None]-f.mean())*de))
    measured=model*response[...,p[:,0]]*response[...,p[:,1]].conj()
    measured+=1000*(rng.normal(size=model.shape)+1j*rng.normal(size=model.shape))
    c=solve_fringe(measured,model,np.ones(model.shape)/1000**2,p,t,f)
    assert .8<c['reduced_noise_chi_square']<1.2
    np.testing.assert_allclose(c['delay_s'],de,atol=3e-8,rtol=0)


def test_vdif_iterator_is_bounded_and_matches_convenience(tmp_path):
    rng=np.random.default_rng(8);x=rng.normal(size=16384)+1j*rng.normal(size=16384)
    path=tmp_path/'station.vdif';valid=np.ones(len(x),bool);valid[4096:8192]=False
    write_vdif(path,x,'2026-10-01T08:00:00Z',2048000,1,scale=2,valid=valid)
    frames=list(iter_vdif_frames(path,2048000,1,2));whole,mask,meta=read_vdif(path,2048000,1,2)
    assert len(frames)==4 and all(len(f['data'])==4096 for f in frames)
    assert [f['sample_index'] for f in frames]==[0,4096,8192,12288]
    np.testing.assert_array_equal(np.concatenate([f['data'] for f in frames]),whole)
    np.testing.assert_array_equal(np.concatenate([f['valid'] for f in frames]),mask)
