"""Equal-window moments are distinct from pooled-sample U3 moments."""
import numpy as np
import pytest
from vsora_simulator.bispectrum_average import gaussian_averaged_bispectrum_moments as averaged
from vsora_simulator.bispectrum_moments import gaussian_distinct_bispectrum_moments as single
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum


@pytest.mark.parametrize('windows',[1,4,16,64,1000000])
def test_exact_mean_and_covariance_scaling(windows):
    s=np.eye(4)+.1*np.ones((4,4));before=s.copy()
    a=single(s,32);q=averaged(s,32,windows)
    np.testing.assert_array_equal(q['mean'],a['mean'])
    for field in ('complex_covariance','complex_pseudocovariance','real_covariance'):
        np.testing.assert_array_equal(q[field],a[field]/windows)
    assert q['statistic']=='equal_mean_of_independent_window_U3' and not q['voltage_samples_pooled']
    assert not q['distribution_gaussian_assumed'] and not q['production_rml_noise_model_changed']
    np.testing.assert_array_equal(s,before)


def test_zero_source_average_differs_from_pooled_voltage_statistic():
    m,q=32,16;s=np.eye(4)
    a=averaged(s,m,q);pooled=single(s,m*q)
    expected=1/(q*m*(m-1)*(m-2))
    np.testing.assert_allclose(a['complex_covariance'],np.eye(4)*expected,rtol=1e-14,atol=0)
    assert not np.allclose(a['complex_covariance'],pooled['complex_covariance'],rtol=1e-3,atol=0)


def test_fixed_station_phase_can_vary_between_windows_only():
    rng=np.random.default_rng(68)
    x=rng.normal(size=(3,4,7,4))+1j*rng.normal(size=(3,4,7,4))
    phase=np.exp(1j*rng.uniform(-np.pi,np.pi,size=(3,4,4)))
    original=distinct_sample_bispectrum(x)['distinct_sample_bispectrum']
    transformed=distinct_sample_bispectrum(x*phase[:,:,None,:])['distinct_sample_bispectrum']
    np.testing.assert_allclose(transformed,original,rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(transformed.mean(axis=1),original.mean(axis=1),rtol=1e-12,atol=1e-12)


@pytest.mark.parametrize('windows',[True,False,0,-1,1.5,'4',1000001])
def test_invalid_window_counts(windows):
    with pytest.raises(ValueError,match='window count'):averaged(np.eye(4),32,windows)


def test_integer_numpy_count_and_deterministic_zero_covariance():
    q=averaged(np.zeros((3,3)),3,np.int64(4))
    assert q['windows']==4 and np.count_nonzero(q['real_covariance'])==0


def test_scaled_covariance_underflow_refused():
    with pytest.raises(ValueError,match='underflow'):averaged(np.eye(4)*1e-53,3,1000000)
