import numpy as np
import pytest
from vsora_simulator.bispectrum_scale import known_bispectrum_moment_scale


def test_null_source_definitions_and_no_detection_claim():
    q=known_bispectrum_moment_scale(np.eye(4),32)
    np.testing.assert_array_equal(q['known_complex_rms_scale'],0.)
    np.testing.assert_array_equal(q['complex_to_null_variance_ratio'],1.)
    assert q['required_identical_independent_windows']==[None]*4
    assert q['conditional_window_count_state']==['zero_numeric_mean']*4
    assert not q['gaussian_detection_probability_calculated'] and not q['distribution_gaussian_assumed']


def test_nonzero_source_exact_scale_and_count():
    q=known_bispectrum_moment_scale(np.eye(4)+.1*np.ones((4,4)),128)
    expected=abs(q['mean'])/np.sqrt(q['complex_covariance'].diagonal().real)
    np.testing.assert_array_equal(q['known_complex_rms_scale'],expected)
    assert np.all(q['complex_to_null_variance_ratio']>1.)
    assert q['required_identical_independent_windows']==[int(np.ceil((5/r)**2)) for r in expected]
    assert q['conditional_window_count_state']==['finite']*4


def test_fixed_station_gain_does_not_change_moment_scale():
    s=np.eye(4)+.1*np.ones((4,4));gain=np.array([.2,7.,1.5,.05])*np.exp(1j*np.array([.3,-1.2,2.3,1.]))
    original=known_bispectrum_moment_scale(s,128);changed=known_bispectrum_moment_scale(gain[:,None]*s*gain[None,:].conj(),128)
    np.testing.assert_allclose(changed['known_complex_rms_scale'],original['known_complex_rms_scale'],rtol=1e-12)
    assert changed['required_identical_independent_windows']==original['required_identical_independent_windows']


@pytest.mark.parametrize('target',[True,0,-1,np.nan,np.inf,101,1+1j])
def test_invalid_target(target):
    with pytest.raises(ValueError):known_bispectrum_moment_scale(np.eye(4),32,target)


def test_zero_total_power_and_tiny_nonzero_mean_are_distinct():
    with pytest.raises(ValueError):known_bispectrum_moment_scale(np.zeros((4,4)),32)
    q=known_bispectrum_moment_scale(np.eye(4)+1e-100*np.ones((4,4)),32)
    assert np.all(q['known_complex_rms_scale']>0)
    assert q['conditional_window_count_state']==['above_supported_count_limit']*4
    assert q['required_identical_independent_windows']==[None]*4
