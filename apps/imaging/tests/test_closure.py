from itertools import combinations
import numpy as np
import pytest
from vsora_imaging.closure import closure_design, form_closures, independent_closures, wrap_phase, extract_closures
from vsora_formats.spectral import save_spectral


def pairs(n): return np.array(list(combinations(range(n), 2)))


def test_arbitrary_station_gain_and_flux_invariance():
    rng = np.random.default_rng(820)
    p = pairs(8)
    uv = rng.normal(size=(3, 4, len(p), 2)) * 1500
    # Independent analytic two point-source Fourier sum.
    v = .7 * np.exp(-2j*np.pi*uv[..., 0]*.0003) + .3 * np.exp(2j*np.pi*uv[..., 1]*.0006)
    g = np.exp(rng.uniform(-2, 2, (3, 4, 8)) + 1j*rng.uniform(-20, 20, (3, 4, 8)))
    gains = g[..., p[:, 0]] * g[..., p[:, 1]].conj()
    a = form_closures(v, np.ones(v.shape)*1e6, p)
    b = form_closures(v*gains, np.ones(v.shape)*1e6/abs(gains)**2, p)
    assert np.max(abs(wrap_phase(a['phase']-b['phase']))) < 1e-12
    assert np.max(abs(a['logamp']-b['logamp'])) < 1e-12
    assert np.allclose(a['baseline_variance'], b['baseline_variance'])
    # Use consistent station-derived uv coordinates for translation invariance.
    station_uv = rng.normal(size=(8, 2))*1500
    edge_uv = station_uv[p[:, 1]]-station_uv[p[:, 0]]
    shift = np.exp(-2j*np.pi*(edge_uv[:, 0]*.0005+edge_uv[:, 1]*.0007))
    c = form_closures(v*shift*17, np.ones(v.shape)*1e6/17**2, p)
    assert np.max(abs(wrap_phase(a['phase']-c['phase']))) < 1e-12
    assert np.max(abs(a['logamp']-c['logamp'])) < 1e-12


@pytest.mark.parametrize('n,phase_rank,amp_rank', [(4, 3, 2), (8, 21, 20)])
def test_independent_ranks_and_covariance(n, phase_rank, amp_rank):
    c = form_closures(np.ones(len(pairs(n)), complex), np.ones(len(pairs(n)))*1e4, pairs(n))
    for key, expected in [('phase', phase_rank), ('logamp', amp_rank)]:
        selected, cov = independent_closures(c[key+'_matrix'], c[key+'_valid'], c['baseline_variance'])
        assert len(selected) == expected
        assert np.linalg.eigvalsh(cov).min() > 0
        assert np.max(abs(cov-np.diag(np.diag(cov)))) > 0


def test_flags_low_snr_and_missing_baselines():
    p = pairs(4); w = np.ones(6)*100.; w[0] = 0; w[1] = 1
    c = form_closures(np.ones(6, complex), w, p)
    for name in ['phase', 'logamp']:
        assert not np.any(c[name+'_valid'] & np.any(c[name+'_matrix'][:, :2] != 0, axis=1))
        assert np.all(c[name][~c[name+'_valid']] == 0)
    design = closure_design(p[2:])
    assert design['phase_matrix'].shape == (1, 4)
    with pytest.raises(ValueError): closure_design(np.array([[0, 1], [0, 1]]))
    with pytest.raises(ValueError): form_closures(np.ones(6, complex), w, p, 2.)


def test_gaussian_covariance_monte_carlo():
    rng = np.random.default_rng(2020); p = pairs(4); samples = 40000
    v = 1 + .01*(rng.normal(size=(samples, 6))+1j*rng.normal(size=(samples, 6)))
    c = form_closures(v, np.full(v.shape, 1e4), p)
    for name in ['phase', 'logamp']:
        a = c[name+'_matrix']; expected = a@a.T*1e-4
        measured = np.cov(c[name], rowvar=False)
        assert np.linalg.norm(measured-expected)/np.linalg.norm(expected) < .03


def test_adc_closure_profile(tmp_path):
    p = pairs(4); v = np.ones((1, 2, 6), complex)
    data = {'visibilities': v, 'weights': np.full(v.shape, 1e4), 'pairs': p,
            'times_s': np.array([.15]), 'frequencies_hz': np.array([1.42e9, 1.4201e9]),
            'uvw_lambda': np.zeros((*v.shape, 3))}
    save_spectral(tmp_path/'input.npz', data, {'visibility_unit': 'ADC^2', 'config': {}})
    result = extract_closures(tmp_path/'input.npz', tmp_path/'closure.npz')
    assert result['input_unit'] == 'ADC^2' and not result['absolute_flux_available']
    with np.load(tmp_path/'closure.npz', allow_pickle=False) as f:
        assert f['phase'].shape == (1, 2, 4)
        assert 'ADC^2' in str(f['metadata_json'])
    with pytest.raises(FileExistsError): extract_closures(tmp_path/'input.npz', tmp_path/'closure.npz')


def test_frequency_mismatch_is_not_station_separable():
    p = pairs(4); rates = np.array([0., 1.31, -.67, 2.23]); duration = .3
    delta = rates[p[:, 0]]-rates[p[:, 1]]
    v = (np.sinc(delta*duration)*np.exp(2j*np.pi*delta*duration/2)).astype(complex)
    c = form_closures(v, np.ones(6)*1e8, p)
    assert np.max(abs(c['phase'])) < 1e-12
    assert np.max(abs(c['logamp'])) > .5
    corrected = form_closures(np.ones(6, complex), np.ones(6)*1e8, p)
    assert np.max(abs(corrected['logamp'])) == 0
