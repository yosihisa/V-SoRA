import numpy as np
import pytest
from scipy.signal import firwin,lfilter
from vsora_correlator.clock import interpolate_samples
from vsora_simulator.filtered_noise import aligned_fft_kernel,filtered_visibility_moments
from vsora_simulator.visibility_moments import visibility_noise_moments


def test_independent_rectangular_fft_matches_iid_formula():
    s=np.ones((4,4))+np.diag([1.,2.,3.,4.]);h=np.exp(-2j*np.pi*2*np.arange(8)/8)/np.sqrt(8)
    q=filtered_visibility_moments(s,np.tile(h,(4,1)),8,16);iid=visibility_noise_moments(s,16)
    np.testing.assert_allclose(q['real_covariance'],iid['real_covariance'],atol=1e-15)
    assert q['maximum_included_lag_blocks']==0 and q['common_kernel_variance_factor']==pytest.approx(1.)
    assert q['common_kernel_effective_count']==pytest.approx(16.)


def test_common_boxcar_variance_factor_and_finite_interval():
    s=np.ones((4,4))+np.eye(4);h=np.full((4,65),1/np.sqrt(65));m=16;hop=8
    q=filtered_visibility_moments(s,h,hop,m);iid=visibility_noise_moments(s,m)
    expected=1+2*sum((1-d/m)*(1-d*hop/65)**2 for d in range(1,9))
    assert q['common_kernel_variance_factor']==pytest.approx(expected)
    np.testing.assert_allclose(q['real_covariance'],iid['real_covariance']*expected,atol=1e-15)
    assert q['common_kernel_effective_count']==pytest.approx(m/expected)
    assert not q['distribution_gaussian_assumed'] and not q['production_rml_noise_model_changed']


def test_station_specific_time_shifts_create_cross_baseline_noise():
    s=np.ones((3,3))+np.eye(3);h=np.eye(3,dtype=complex);q=filtered_visibility_moments(s,h,1,8)
    np.testing.assert_allclose(q['mean'],0,atol=0)
    assert q['complex_covariance'][0,2]==pytest.approx(7/64)
    assert q['iid_counterfactual_real_covariance'][0,2]==0
    assert q['real_covariance'][0,2]==pytest.approx(7/128)
    assert not q['identical_station_kernels'] and q['common_kernel_effective_count'] is None
    np.testing.assert_allclose(q['complex_covariance'],q['complex_covariance'].conj().T,atol=1e-15)
    np.testing.assert_allclose(q['complex_pseudocovariance'],q['complex_pseudocovariance'].T,atol=1e-15)
    assert np.linalg.eigvalsh(q['real_covariance']).min()>=-1e-14


@pytest.mark.parametrize('length,channel,offset',[(8,4,0.),(32,16,.25),(32,24,.5),(64,8,.75)])
def test_kernel_matches_actual_fir_interpolator_and_fft(length,channel,offset):
    rng=np.random.default_rng(49);m=5;x=(rng.normal(size=m*length+192)+1j*rng.normal(size=m*length+192))/np.sqrt(2)
    taps=firwin(65,.35,fs=1.,window=('kaiser',8.6))
    y,valid=interpolate_samples(lfilter(taps,[1],x),96+offset+np.arange(m*length))
    expected=np.fft.fftshift(np.fft.fft(y.reshape(m,length),axis=1,norm='ortho'),axes=1)[:,channel]
    h=aligned_fft_kernel(length,channel,offset);actual=np.array([h @ x[a*length:a*length+len(h)] for a in range(m)])
    assert valid.all();np.testing.assert_allclose(actual,expected,rtol=1e-12,atol=1e-12)


@pytest.mark.parametrize('length,channel,offset',[(True,0,0.),(4,0,0.),(24,12,0.),(2048,0,0.),(32,True,0.),(32,-1,0.),(32,32,0.),(32,16,-.1),(32,16,1.),(32,16,np.nan)])
def test_invalid_kernel_parameters(length,channel,offset):
    with pytest.raises(ValueError):aligned_fft_kernel(length,channel,offset)


@pytest.mark.parametrize('s,h,hop,m',[(np.eye(1),np.ones((1,8)),8,16),(np.eye(9),np.ones((9,8)),8,16),
    (np.eye(3),np.ones((4,8)),8,16),(np.eye(3),np.zeros((3,8)),8,16),
    (np.eye(3),np.full((3,8),np.nan),8,16),(np.eye(3),np.ones((3,8)),True,16),
    (np.eye(3),np.ones((3,8)),0,16),(np.eye(3),np.ones((3,8)),8,True),
    (np.eye(3),np.ones((3,8)),8,0),(np.eye(3),np.ones((3,8)),8,1.5),
    (-np.eye(3),np.ones((3,8)),8,16),(np.eye(8),np.ones((8,4096)),1,1000)])
def test_invalid_moment_inputs(s,h,hop,m):
    with pytest.raises(ValueError):filtered_visibility_moments(s,h,hop,m)


def test_complex_station_gains_transform_full_covariance():
    rng=np.random.default_rng(49);a=rng.normal(size=(4,4))+1j*rng.normal(size=(4,4));s=a @ a.conj().T+np.eye(4)
    kernels=np.array([aligned_fft_kernel(8,6,x) for x in (0.,.25,.5,.75)])
    q=filtered_visibility_moments(s,kernels,8,16)
    g=np.array([.4,3.,1.5,.75])*np.exp(1j*np.array([.3,-1.,2.,1.1]))
    r=filtered_visibility_moments(g[:,None]*s*g.conj()[None,:],kernels,8,16)
    factor=np.array([g[i]*g[j].conj() for i,j in q['pairs']]);t=np.block([[np.diag(factor.real),-np.diag(factor.imag)],[np.diag(factor.imag),np.diag(factor.real)]])
    np.testing.assert_allclose(r['real_covariance'],t @ q['real_covariance'] @ t.T,rtol=1e-12,atol=1e-12)


def test_actual_gaussian_voltage_monte_carlo_full_covariance():
    from workflows.filtered_noise_validation import experiment
    s=np.ones((3,3))+np.eye(3);q=experiment(s,np.eye(3),1,8,8192,49)
    assert q['all_covariance_elements_within_six_standard_errors']
    assert q['all_mean_elements_within_six_standard_errors']


@pytest.mark.parametrize('offset',[True,.1+0j,np.array([.2])])
def test_offset_must_be_real_scalar(offset):
    with pytest.raises(ValueError):aligned_fft_kernel(32,16,offset)


def test_small_workflow_records_all_operators(tmp_path):
    from workflows.filtered_noise_validation import run
    q=run(tmp_path/'run',256)
    assert len(q['cases'])==6 and not q['measured_effective_sample_count']
    shifts=q['cases'][-1]
    assert shifts['known_variance_to_iid_variance_range']==[1.,1.]
    assert shifts['maximum_normalized_iid_counterfactual_difference']>.2
    assert (tmp_path/'run/filtered-noise.png').is_file()
