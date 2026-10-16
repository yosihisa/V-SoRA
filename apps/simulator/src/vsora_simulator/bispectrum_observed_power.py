"""Experimental same-sample power-normalized U3, without a likelihood claim."""
from fractions import Fraction
import math
import numpy as np
from .bispectrum_distinct import distinct_sample_bispectrum


def observed_power_normalized_bispectrum(voltages, triangles=None):
    """Normalize each station/window by its own empirical RMS before U3.

    Equivalent to raw U3/(P_i P_j P_k), P_i=mean(abs(x_i)**2).
    A nonzero complex gain constant over the sample axis cancels for every
    realization. No Gaussian/iid assumption is needed for that identity.
    Random powers from these same samples generally change the expectation;
    known-power U3 moments and unbiasedness must not be reused for this ratio.
    """
    if np.ma.isMaskedArray(voltages) or np.ma.isMaskedArray(triangles):
        raise ValueError('unmasked common voltages and triangle indices required')
    x = np.asarray(voltages)
    if (x.ndim < 2 or not np.iscomplexobj(x) or not 3 <= x.shape[-2] <= 1000000
            or not 3 <= x.shape[-1] <= 8 or not x.size or x.size > 8000000
            or not np.isfinite(x).all()):
        raise ValueError('finite complex [...,M,N], M3..1e6, N3..8, at most 8 million values required')
    with np.errstate(over='ignore', invalid='ignore'):
        x = x.astype(np.complex128, copy=False)
    if not np.isfinite(x).all():
        raise ValueError('voltage components must be representable as complex128')
    # Component scaling avoids squaring very large or very small voltages.
    scale = np.maximum(np.abs(x.real), np.abs(x.imag)).max(axis=-2)
    if np.any(scale <= 0):
        raise ValueError('strictly positive empirical power at every station/window required')
    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        scaled = x.real / scale[..., None, :] + 1j * (x.imag / scale[..., None, :])
        scaled_power = np.mean(scaled.real**2 + scaled.imag**2, axis=-2)
        normalized = scaled / np.sqrt(scaled_power)[..., None, :]
    q = distinct_sample_bispectrum(normalized, triangles)
    return {
        'triangles': q['triangles'], 'samples': q['samples'],
        'observed_power_normalized_u3': q['distinct_sample_bispectrum'],
        'observed_power_normalized_ordinary_product': q['ordinary_visibility_product'],
        'voltage_conditioning_scale': scale.copy(),
        'mean_conditioned_power': scaled_power.copy(),
        'normalization_uses_same_voltage_samples': True,
        'known_population_power_supplied': False,
        'constant_station_gain_cancels_per_realization': True,
        'input_sample_independence_verified': False,
        'finite_sample_unbiased_guarantee': False,
        'known_power_moment_formula_applied': False,
        'station_gain_estimation_performed': False,
        'closure_phase_unbiased_guarantee': False,
        'production_rml_noise_model_changed': False,
        'real_hardware_validation_performed': False,
        'scope': 'Experimental dimensionless same-sample power ratio on a supplied common sample set; '
                 'gain cancellation requires a nonzero gain constant within each window. No phase '
                 'likelihood, bias correction, detection calibration, LO correction or image confidence.'}


def gaussian_rank_one_observed_power_moments(samples):
    """Exact scalar moments only for x_i=g_i*z, iid proper Gaussian z.

    With r_a=abs(z_a)**2/sum(abs(z)**2), r~Dirichlet(1,...,1).
    Integrating degree-three and degree-six monomials gives the mean and
    second moment. Fraction arithmetic avoids cancellation in the variance.
    The ordinary normalized product is identically one. This is not a
    debiasing factor or a variance model for a general nonzero receiver S.
    """
    if (isinstance(samples, (bool, np.bool_))
            or not isinstance(samples, (int, np.integer)) or not 3 <= samples <= 1000000):
        raise ValueError('integer independent Gaussian sample count 3..1000000 required')
    m = int(samples)

    def falling(order):
        return math.prod(range(m - order + 1, m + 1)) if m >= order else 0

    mean = Fraction(m**2, (m + 1) * (m + 2))
    overlap_sum = sum(math.comb(3, k) * math.perm(3, k) * falling(6 - k) * 2**k
                      for k in range(4))
    second = Fraction(m**6 * overlap_sum, falling(3)**2 * math.prod(range(m, m + 6)))
    variance = second - mean**2
    return {
        'samples': m, 'mean_real': float(mean), 'mean_imaginary': 0.,
        'variance_real': float(variance), 'variance_imaginary': 0.,
        'second_moment_real': float(second),
        'ordinary_normalized_product': 1.,
        'population_power_normalized_bispectrum': 1.,
        'rank_one_complete_shared_voltage_assumed': True,
        'iid_proper_gaussian_voltage_assumed': True,
        'general_covariance_formula': False,
        'bias_correction_applied': False,
        'scope': 'Exact rank-one Gaussian same-sample empirical-power ratio only; '
                 'not general-sky moments, an observed uncertainty estimate or a likelihood.'}
