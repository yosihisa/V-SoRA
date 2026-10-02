import numpy as np
import pytest
from vsora_correlator.fringe import solve_fringe,apply_calibration
from vsora_formats.spectral import save_spectral,load_spectral


def fixture(noise=0):
    t=np.arange(32)*.03125;f=1.42e9+np.arange(32)*64000
    p=np.array([(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)])
    a=np.array([1.2,.8,1.1,.9]);ph=np.array([0,.4,-.7,1.4])
    de=np.array([0,2.3e-6,-1.7e-6,.38e-6]);ra=np.array([0,2.7,-1.3,4.1])
    # Forward expression is independent of the production gain application.
    response=a*np.exp(1j*(ph+2*np.pi*((t[:,None,None]-t.mean())*ra+
                   (f[None,:,None]-f.mean())*de)))
    model=np.ones((len(t),len(f),len(p)),complex)*1000
    measured=model*response[...,p[:,0]]*np.conj(response[...,p[:,1]])
    rng=np.random.default_rng(202);measured+=noise*(rng.normal(size=model.shape)+1j*rng.normal(size=model.shape))
    return measured,model,np.ones(model.shape),p,t,f,a,ph,de,ra


def test_recover_unknown_station_errors_and_weight_propagation():
    v,m,w,p,t,f,a,ph,de,ra=fixture()
    c=solve_fringe(v,m,w,p,t,f)
    np.testing.assert_allclose(c['amplitude'],a,rtol=1e-9)
    np.testing.assert_allclose(c['delay_s'],de,atol=1e-14,rtol=0)
    np.testing.assert_allclose(c['rate_hz'],ra,atol=1e-8,rtol=0)
    np.testing.assert_allclose(np.exp(1j*np.array(c['phase_rad'])),np.exp(1j*ph),atol=1e-8)
    corrected,cw=apply_calibration(v,w,p,c,t,f)
    np.testing.assert_allclose(corrected,m,rtol=1e-8)
    np.testing.assert_allclose(cw,w*(a[p[:,0]]*a[p[:,1]])**2,rtol=1e-8)


def test_noise_flags_and_different_reference():
    v,m,w,p,t,f,a,ph,de,ra=fixture(noise=20)
    w[::4,:8]=0;v[::4,:8]=0
    c=solve_fringe(v,m,w,p,t,f,reference_station=2)
    np.testing.assert_allclose(c['delay_s'],de-de[2],atol=2e-9,rtol=0)
    np.testing.assert_allclose(c['rate_hz'],ra-ra[2],atol=.003,rtol=0)
    np.testing.assert_allclose(c['amplitude'],a,rtol=.003)


def test_missing_reference_baseline_and_nonidentifiable_amplitudes():
    v,m,w,p,t,f,*_=fixture()
    with pytest.raises(ValueError,match='reference'):
        solve_fringe(v[...,[0,2,3,4,5]],m[...,[0,2,3,4,5]],w[...,[0,2,3,4,5]],p[[0,2,3,4,5]],t,f)
    with pytest.raises(ValueError,match='identifiable'):
        solve_fringe(v[...,:3],m[...,:3],w[...,:3],p[:3],t,f)


def test_no_detection_and_alias_limits():
    v,m,w,p,t,f,*_=fixture();rng=np.random.default_rng(11)
    random=rng.normal(size=v.shape)+1j*rng.normal(size=v.shape)
    with pytest.raises(ValueError,match='not detected'): solve_fringe(random,m,w,p,t,f)
    with pytest.raises(ValueError,match='alias'): solve_fringe(v,m,w,p,t,f,delay_limit_s=20e-6)


def test_extrapolation_is_explicit():
    v,m,w,p,t,f,*_=fixture();c=solve_fringe(v,m,w,p,t,f)
    with pytest.raises(ValueError,match='extrapolation'): apply_calibration(v,w,p,c,t+10,f)
    apply_calibration(v,w,p,c,t+10,f,allow_extrapolation=True)


def test_spectral_roundtrip_and_malformed_axes(tmp_path):
    v,m,w,p,t,f,*_=fixture()
    d={'vis_jy':v,'weights':w,'pairs':p,'times_s':t,'frequencies_hz':f,'uvw_lambda':np.zeros((*v.shape,3))}
    path=tmp_path/'cube.npz';save_spectral(path,d,{'unit':'Jy'})
    r=load_spectral(path);np.testing.assert_array_equal(r['vis_jy'],v)
    d['frequencies_hz']=f[::-1]
    with pytest.raises(ValueError,match='increase'): save_spectral(tmp_path/'bad.npz',d,{})
