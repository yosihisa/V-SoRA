"""Known-model moments of equally averaged independent short-window U3."""
import numpy as np
from .bispectrum_moments import gaussian_distinct_bispectrum_moments


def gaussian_averaged_bispectrum_moments(station_covariance, samples, windows, triangles=None):
    """Same known station covariance in independent windows; no image likelihood.

    Each window retains its own distinct-sample U3. Pooling voltage samples into
    one larger U3 is a different statistic with a different finite-M covariance.
    """
    if isinstance(windows, bool) or not isinstance(windows, (int, np.integer)) or not 1 <= windows <= 1000000:
        raise ValueError('integer independent window count1..1000000 required')
    q = gaussian_distinct_bispectrum_moments(station_covariance, samples, triangles)
    result = dict(q)
    for key in ('complex_covariance', 'complex_pseudocovariance', 'real_covariance'):
        result[key] = q[key] / int(windows)
        if not np.isfinite(result[key]).all():
            raise ValueError('averaged bispectrum covariance outside finite range')
    s = np.asarray(station_covariance)
    positive = (s.diagonal().real[q['triangles']] > 0).all(axis=1)
    if np.any(positive & (result['complex_covariance'].diagonal().real <= 0)):
        raise ValueError('averaged bispectrum covariance underflow')
    result.update(
        windows=int(windows), statistic='equal_mean_of_independent_window_U3',
        independent_windows_assumed=True, window_independence_verified_for_hardware=False,
        same_known_covariance_in_all_windows=True, voltage_samples_pooled=False,
        distribution_gaussian_assumed=False,
        scope='Conditional exact mean/covariance only: known iid proper Gaussian voltage S, common sample count M, independent windows Q with the same mean and covariance. No observed selection, unknown gain-amplitude variation, actual FFT independence or Gaussian U3/image likelihood.'
    )
    return result
