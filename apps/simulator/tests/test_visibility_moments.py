import numpy as np
import pytest
from vsora_simulator.visibility_moments import visibility_noise_moments


def test_two_station_parallel_and_perpendicular_variance():
    rho=.6;phase=.7;s=np.array([[2.,rho*np.exp(1j*phase)],[rho*np.exp(-1j*phase),3.]])
    q=visibility_noise_moments(s,32)
    assert q['complex_covariance'][0,0]==pytest.approx(6/32)
    assert q['complex_pseudocovariance'][0,0]==pytest.approx(s[0,1]**2/32)
    rotation=np.array([[np.cos(phase),np.sin(phase)],[-np.sin(phase),np.cos(phase)]])
    np.testing.assert_allclose(rotation @ q['real_covariance'] @ rotation.T,
        np.diag([(6+rho**2)/64,(6-rho**2)/64]),atol=1e-15)


def test_common_signal_limit_and_independent_receivers():
    q=visibility_noise_moments(np.ones((4,4)),10)
    np.testing.assert_allclose(q['real_covariance'][:6,:6],.1)
    np.testing.assert_allclose(q['real_covariance'][6:,:],0,atol=1e-15)
    independent=visibility_noise_moments(np.diag([2.,3.,4.,5.]),10)
    assert np.count_nonzero(independent['real_covariance']-np.diag(np.diag(independent['real_covariance'])))==0
    np.testing.assert_allclose(independent['complex_pseudocovariance'],0)
    assert not q['distribution_gaussian_assumed']


def test_full_complex_gain_covariance_rotation_and_voltage_samples():
    rng=np.random.default_rng(42);m=(rng.normal(size=(4,4))+1j*rng.normal(size=(4,4)))/np.sqrt(8)
    s=m @ m.conj().T;gain=np.array([.6,1.2,2.,.9])*np.exp(1j*np.array([.4,-.2,1.,2.]))
    q=visibility_noise_moments(s,8);r=visibility_noise_moments(gain[:,None]*s*gain[None,:].conj(),8)
    factor=np.array([gain[i]*gain[j].conj() for i,j in q['pairs']])
    transform=np.block([[np.diag(factor.real),-np.diag(factor.imag)],
        [np.diag(factor.imag),np.diag(factor.real)]])
    np.testing.assert_allclose(r['real_covariance'],transform @ q['real_covariance'] @ transform.T,atol=1e-14)
    voltages=(rng.normal(size=(65536,8,4))+1j*rng.normal(size=(65536,8,4)))/np.sqrt(2)
    voltages=voltages @ np.linalg.cholesky(s).T
    i,j=q['pairs'].T;visibility=(voltages[:,:,i]*voltages[:,:,j].conj()).mean(axis=1)
    residual=visibility-q['mean'];values=np.c_[residual.real,residual.imag]
    observed=np.cov(values,rowvar=False);scale=np.sqrt(np.diag(q['real_covariance'])[:,None]*np.diag(q['real_covariance'])[None,:])
    assert np.max(abs(observed-q['real_covariance'])/scale)<.025
    mean_error=abs(visibility.mean(axis=0)-q['mean'])/np.sqrt(np.diag(q['complex_covariance']).real/len(visibility))
    assert mean_error.max()<5.


@pytest.mark.parametrize('covariance,samples,pairs',[
    (np.eye(1),10,None),(np.eye(33),10,None),(np.full((3,3),np.nan),10,None),
    (-np.eye(3),10,None),(np.array([[1,1j],[1j,1]]),10,None),
    (np.eye(3),False,None),(np.eye(3),0,None),(np.eye(3),1.5,None),
    (np.eye(3),10,[[1,0]]),(np.eye(3),10,[[0.,1.]]),
    (np.eye(3),10,[[0,1],[0,1]]),(np.eye(3),10,[[0,3]]),
    (np.eye(3),10,[]),(np.eye(3)*1e200,10,None)])
def test_invalid_noise_moment_inputs(covariance,samples,pairs):
    with pytest.raises(ValueError):visibility_noise_moments(covariance,samples,pairs)
