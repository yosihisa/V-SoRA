from fractions import Fraction
from itertools import combinations, permutations
import math
import numpy as np
import pytest
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum
from vsora_simulator.bispectrum_observed_power import (
    observed_power_normalized_bispectrum as calculate,
    gaussian_rank_one_observed_power_moments as rank_one,
)


def voltage(seed=85, shape=(7, 4)):
    rng = np.random.default_rng(seed)
    return rng.normal(size=shape) + 1j * rng.normal(size=shape)


@pytest.mark.parametrize('samples', [3, 4, 6])
def test_direct_ordered_distinct_enumeration(samples):
    x = voltage(shape=(samples, 4)); power = np.mean(abs(x)**2, axis=0)
    q = calculate(x); expected = []
    for i, j, k in combinations(range(4), 3):
        terms = [x[a, i] * x[a, j].conjugate() * x[b, j] * x[b, k].conjugate()
                 * x[c, k] * x[c, i].conjugate() for a, b, c in permutations(range(samples), 3)]
        expected.append(np.mean(terms) / (power[i] * power[j] * power[k]))
    np.testing.assert_allclose(q['observed_power_normalized_u3'], expected, rtol=2e-13, atol=2e-14)


def test_raw_u3_divided_by_same_empirical_power():
    x = voltage(shape=(2, 3, 13, 5)); q = calculate(x); raw = distinct_sample_bispectrum(x)
    powers = np.mean(abs(x)**2, axis=-2)
    denominator = np.prod(powers[..., q['triangles']], axis=-1)
    for result, key in [('observed_power_normalized_u3', 'distinct_sample_bispectrum'),
                        ('observed_power_normalized_ordinary_product', 'ordinary_visibility_product')]:
        np.testing.assert_allclose(q[result], raw[key] / denominator, rtol=2e-12, atol=2e-14)


@pytest.mark.parametrize('shape', [(3, 3), (32, 8), (2, 4, 19, 5)])
def test_arbitrary_constant_complex_gain_per_window_cancels(shape):
    x = voltage(shape=shape); g = voltage(seed=86, shape=shape[:-2] + (shape[-1],))
    a, b = calculate(x), calculate(x * g[..., None, :])
    np.testing.assert_allclose(a['observed_power_normalized_u3'], b['observed_power_normalized_u3'], rtol=2e-12, atol=2e-14)
    np.testing.assert_allclose(a['observed_power_normalized_ordinary_product'], b['observed_power_normalized_ordinary_product'], rtol=2e-12, atol=2e-14)


def test_extreme_finite_station_scales_without_raw_power_overflow():
    x = voltage(); factors = np.array([1e-200, 1e150, 1e-120, 1e200])
    a, b = calculate(x), calculate(x * factors)
    np.testing.assert_allclose(a['observed_power_normalized_u3'], b['observed_power_normalized_u3'], rtol=2e-12, atol=2e-14)
    assert np.isfinite(b['mean_conditioned_power']).all()


def test_selected_triangles_leading_axes_and_input_unchanged():
    x = voltage(shape=(2, 3, 8, 5)); before = x.copy(); selected = np.array([[0, 1, 4], [1, 3, 4]])
    q = calculate(x, selected)
    assert q['observed_power_normalized_u3'].shape == (2, 3, 2)
    for a in range(2):
        for b in range(3):
            np.testing.assert_allclose(q['observed_power_normalized_u3'][a, b], calculate(x[a, b], selected)['observed_power_normalized_u3'], rtol=2e-13, atol=2e-14)
    np.testing.assert_array_equal(x, before)


def test_time_varying_station_phase_is_not_cancelled():
    x = voltage(shape=(16, 4)); altered = x.copy()
    altered[:, 1] *= np.exp(2j * np.pi * np.arange(16) / 16)
    assert np.max(abs(calculate(x)['observed_power_normalized_u3'] - calculate(altered)['observed_power_normalized_u3'])) > .01


def test_same_power_complete_shared_voltage_ordinary_one_and_u3_not_one():
    z = np.array([1., 2., 3.], complex)
    x = z[:, None] * np.array([1., 2j, .3 + .4j])[None, :]
    q = calculate(x)
    np.testing.assert_allclose(q['observed_power_normalized_ordinary_product'], 1., atol=2e-14)
    np.testing.assert_allclose(q['observed_power_normalized_u3'], 36 / ((14 / 3)**3), atol=2e-14)
    assert abs(q['observed_power_normalized_u3'][0] - 1) > .5


def test_result_does_not_claim_known_power_moments_or_phase_confidence():
    q = calculate(voltage())
    for key in ('finite_sample_unbiased_guarantee', 'known_power_moment_formula_applied',
                'closure_phase_unbiased_guarantee', 'production_rml_noise_model_changed',
                'real_hardware_validation_performed', 'input_sample_independence_verified'):
        assert q[key] is False


@pytest.mark.parametrize('bad', [None, 1j, np.ones((3, 3)), np.ones((2, 3), complex),
    np.ones((3, 2), complex), np.ones((3, 9), complex), np.ones((0, 3, 3), complex),
    np.full((3, 3), np.nan+0j), np.full((3, 3), np.inf+0j), np.zeros((3, 3), complex),
    np.ma.array(np.ones((3, 3), complex), mask=False),
    np.broadcast_to(1j, (1000001, 3)), np.broadcast_to(1j, (2, 1000000, 8))])
def test_invalid_voltage_rejected(bad):
    with pytest.raises(ValueError): calculate(bad)


def test_one_station_with_zero_empirical_power_is_rejected():
    x = voltage(); x[:, 2] = 0
    with pytest.raises(ValueError, match='positive empirical power'): calculate(x)


@pytest.mark.parametrize('triangles', [[[0, 1, 1]], [[1, 0, 2]], [[0, 1, 4]],
    [[0., 1., 2.]], [[0, 1, 2], [0, 1, 2]], np.ma.array([[0, 1, 2]], mask=False)])
def test_invalid_triangles_rejected(triangles):
    with pytest.raises(ValueError): calculate(voltage(), triangles)


@pytest.mark.parametrize('samples', [3, 4, 16, 128, 1000000])
def test_rank_one_moments_against_independent_index_multiset_integrals(samples):
    # Fix one ordered triple (0,1,2); enumerate all right triples by overlap.
    # Degree-six Dirichlet monomials have numerator product(factorial(count)).
    m = samples; left = (0, 1, 2); total = 0
    for right in permutations(range(min(m, 6)), 3):
        new = sorted(set(right) - set(left)); k = len(new)
        if new != list(range(3, 3 + k)): continue
        multiplicity = math.prod(range(m - 3 - k + 1, m - 2)) if k else 1
        multiplicity //= math.factorial(k)
        counts = [left.count(i) + right.count(i) for i in set(left + right)]
        total += multiplicity * math.prod(math.factorial(c) for c in counts)
    second = Fraction(m**6 * total, (m*(m-1)*(m-2)) * math.prod(range(m, m+6)))
    mean = Fraction(m*m, (m+1)*(m+2)); q = rank_one(m)
    assert q['mean_real'] == float(mean)
    assert q['second_moment_real'] == float(second)
    assert q['variance_real'] == float(second - mean**2) > 0
    assert q['variance_imaginary'] == 0


@pytest.mark.parametrize('bad', [True, np.bool_(False), 2, 1000001, 3., '3', None])
def test_rank_one_sample_count_rejected(bad):
    with pytest.raises(ValueError): rank_one(bad)
