import copy
import numpy as np
import pytest
from scipy.special import erf
from vsora_correlator.rate_uncertainty import linear_rate_uncertainty, PARAMETER_ORDER


def profile(covariance=None):
    c = np.diag([.01, .02, .03, .005, .006, .007]) if covariance is None else np.asarray(covariance)
    return {'schema_version': 1, 'type': 'station_rate_linear',
        'station_ids': ['A', 'B', 'C', 'D'], 'station_indices': [0, 1, 2, 3],
        'reference_station': 0, 'time_origin_utc': '2026-10-03T00:00:00Z',
        'time_reference_s': 1.5, 'valid_time_range_s': [.001, 2.999],
        'sample_cadence_s': .002, 'temporal_nyquist_hz': 250., 'max_baseline_rate_hz': 100.,
        'station_rates_hz': [0., 1., -1., 2.], 'station_rate_slopes_hz_per_s': [0., .1, -.1, .2],
        'parameter_covariance': c.tolist(), 'covariance_station_order': [1, 2, 3],
        'parameter_order': PARAMETER_ORDER}


def evaluate(p, start=0., end=3., pairs=None):
    return linear_rate_uncertainty(p, p['station_ids'], p['time_origin_utc'], start, end, pairs)


def test_zero_covariance_and_constant_rate_gaussian_integral():
    q = evaluate(profile(np.zeros((6, 6))))
    assert q['minimum_expected_centered_complex_coherence'] == 1.
    assert not q['coherence_stability_measured'] and not q['hardware_confidence_calibrated']
    for sigma in (.001, .1, 1., 10.):
        c = np.zeros((6, 6)); c[0, 0] = sigma**2
        value = evaluate(profile(c), pairs=[[0, 1]])['baselines'][0]['expected_centered_complex_coherence']
        a = 2*np.pi**2*sigma**2*3**2
        expected = np.sqrt(np.pi/a)*erf(np.sqrt(a)/2)
        assert value == pytest.approx(expected, abs=1e-10)


def test_cross_station_and_cross_parameter_covariances_matter():
    c = np.diag([.04, .04, .02, .01, .01, .005]); c[0, 1] = c[1, 0] = .03
    correlated = evaluate(profile(c), pairs=[[1, 2]])
    independent = evaluate(profile(np.diag(np.diag(c))), pairs=[[1, 2]])
    assert correlated['minimum_expected_centered_complex_coherence'] > independent['minimum_expected_centered_complex_coherence']+.1
    c[0, 3] = c[3, 0] = .012
    full = evaluate(profile(c), 0., 1., [[0, 1]])
    no_cross = c.copy(); no_cross[0, 3] = no_cross[3, 0] = 0.
    assert abs(full['minimum_expected_centered_complex_coherence']-evaluate(profile(no_cross), 0., 1., [[0, 1]])['minimum_expected_centered_complex_coherence']) > .005


def test_epoch_rebase_and_station_reference_are_coordinate_choices():
    rng = np.random.default_rng(40); m = rng.normal(size=(6, 6))*.025; c = m @ m.T
    p = profile(c); original = evaluate(p, .2, 2.6)
    shift = .5; transform = np.eye(6); transform[:3, 3:] = shift*np.eye(3)
    other = copy.deepcopy(p); other['time_reference_s'] += shift
    other['station_rates_hz'] = (np.array(p['station_rates_hz'])+shift*np.array(p['station_rate_slopes_hz_per_s'])).tolist()
    other['parameter_covariance'] = (transform @ c @ transform.T).tolist()
    rebased = evaluate(other, .2, 2.6)
    np.testing.assert_allclose([r['expected_centered_complex_coherence'] for r in original['baselines']],
        [r['expected_centered_complex_coherence'] for r in rebased['baselines']], atol=1e-13)
    # Change reference from station 0 to 2, retaining covariances of differences.
    unknown = [0, 1, 3]; rows = []
    for s in unknown:
        rows.append([float(k == s)-float(k == 2) for k in (1, 2, 3)])
    basis = np.array(rows); transform = np.zeros((6, 6)); transform[:3, :3] = basis; transform[3:, 3:] = basis
    other = copy.deepcopy(p); other.update(reference_station=2, covariance_station_order=unknown,
        parameter_covariance=(transform @ c @ transform.T).tolist())
    for key in ('station_rates_hz', 'station_rate_slopes_hz_per_s'):
        other[key] = (np.array(p[key])-p[key][2]).tolist()
    rebased = evaluate(other, .2, 2.6)
    np.testing.assert_allclose([r['expected_centered_complex_coherence'] for r in original['baselines']],
        [r['expected_centered_complex_coherence'] for r in rebased['baselines']], atol=1e-13)


@pytest.mark.parametrize('key,value', [
    ('parameter_covariance', np.full((6, 6), np.nan).tolist()),
    ('parameter_covariance', (-np.eye(6)).tolist()),
    ('parameter_covariance', np.ones((5, 5)).tolist()),
    ('parameter_covariance', (np.eye(6)+np.eye(6, k=1)).tolist()),
    ('covariance_station_order', [3, 2, 1]),
    ('parameter_order', 'slopes then rates'), ('reference_station', True),
    ('time_reference_s', 4.), ('parameter_covariance', (np.eye(6)*1e8).tolist())])
def test_invalid_covariance_contract(key, value):
    p = profile(); p[key] = value
    with pytest.raises(ValueError): evaluate(p)


@pytest.mark.parametrize('start,end,pairs', [
    (False, 3., None), (0., np.nan, None), (1., 1., None), (0., 3.1, None),
    (-.1, 2., None), (0., 3., [[1, 0]]), (0., 3., [[0., 1.]]),
    (0., 3., [[0, 1], [0, 1]]), (0., 3., [[0, 4]]), (0., 3., [])])
def test_invalid_windows_and_pairs(start, end, pairs):
    with pytest.raises(ValueError): evaluate(profile(), start, end, pairs)


def test_correlated_gaussian_draws_estimate_complex_mean_not_mean_modulus():
    rng = np.random.default_rng(40); m = rng.normal(size=(6, 6))*.075; c = m @ m.T
    expected = evaluate(profile(c), .2, 2.6, [[1, 3]])['minimum_expected_centered_complex_coherence']
    errors = rng.multivariate_normal(np.zeros(6), c, size=16384)
    z, w = np.polynomial.legendre.leggauss(96); x = z*1.2
    # Epoch 1.5; window center 1.4. Remove center phase before averaging.
    phase = 2*np.pi*((errors[:, 0]-errors[:, 2])[:, None]*x+
        (errors[:, 3]-errors[:, 5])[:, None]*(-.1*x+.5*x*x))
    samples = np.exp(1j*phase) @ (w/2)
    assert abs(samples.mean().real-expected) < .006
    assert abs(samples.mean().imag) < .006
    assert np.mean(abs(samples)) > expected+.002
