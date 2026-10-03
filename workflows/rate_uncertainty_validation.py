"""Conditional Gaussian parameter-error experiment; optional archived profiles."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from vsora_correlator.rate_uncertainty import linear_rate_uncertainty, PARAMETER_ORDER


def gaussian_profile(c):
    return {'schema_version': 1, 'type': 'station_rate_linear',
        'station_ids': ['ST01', 'ST02', 'ST03', 'ST04'], 'station_indices': [0, 1, 2, 3],
        'reference_station': 0, 'time_origin_utc': '2026-10-03T00:00:00Z',
        'time_reference_s': 1.5, 'valid_time_range_s': [.001, 2.999],
        'sample_cadence_s': .002, 'temporal_nyquist_hz': 250., 'max_baseline_rate_hz': 100.,
        'station_rates_hz': [0., 1., -1., 2.], 'station_rate_slopes_hz_per_s': [0., .1, -.1, .2],
        'parameter_covariance': c.tolist(), 'covariance_station_order': [1, 2, 3],
        'parameter_order': PARAMETER_ORDER}


def run(output, profiles=None):
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(40); matrix = rng.normal(size=(6, 6))*.075
    c = matrix @ matrix.T; p = gaussian_profile(c)
    expected = linear_rate_uncertainty(p, p['station_ids'], p['time_origin_utc'], .2, 2.6)
    # Independent draws, using the same covariance as the conditional formula.
    draws = rng.multivariate_normal(np.zeros(6), c, size=65536)
    z, w = np.polynomial.legendre.leggauss(128); x = 1.2*z
    batches = []
    for row in expected['baselines']:
        i, j = row['pair']
        rate = np.zeros(len(draws)); slope = np.zeros(len(draws))
        for station, sign in ((i, 1.), (j, -1.)):
            if station:
                rate += sign*draws[:, station-1]; slope += sign*draws[:, 3+station-1]
        samples = []
        for start in range(0, len(draws), 2048):
            phase = 2*np.pi*(rate[start:start+2048, None]*x+
                slope[start:start+2048, None]*(-.1*x+.5*x*x))
            samples.append(np.exp(1j*phase) @ (w/2))
        samples = np.concatenate(samples); mean = samples.mean()
        sigma = float(samples.real.std(ddof=1)/np.sqrt(len(samples)))
        assert abs(mean.real-row['expected_centered_complex_coherence']) < 6*sigma+1e-5
        batches.append({'pair': row['pair'], 'calculated_expected_centered_complex_coherence': row['expected_centered_complex_coherence'],
            'sample_mean_real': float(mean.real), 'sample_mean_imaginary': float(mean.imag),
            'sample_standard_error_real': sigma, 'sample_mean_absolute_coherence': float(np.mean(abs(samples)))})
    archived = []
    if profiles is not None:
        specification = Path(profiles)
        for spec in json.loads(specification.read_text()):
            source = (specification.parent/spec['profile']).resolve(); raw = source.read_bytes(); p = json.loads(raw)
            result = linear_rate_uncertainty(p, p['station_ids'], p['time_origin_utc'], spec['start_s'], spec['end_s'])
            archived.append({'label': spec['label'], 'profile_sha256': hashlib.sha256(raw).hexdigest(),
                'diagnostic': result,
                'matched_control_minimum_amplitude_ratio': spec.get('matched_control_minimum_amplitude_ratio'),
                'ratio_source_sha256': spec.get('ratio_source_sha256')})
    summary = {'type': 'rate_uncertainty_validation', 'seed': 40, 'draws': len(draws),
        'gaussian_profile': gaussian_profile(c), 'gaussian_results': batches, 'archived_profiles': archived,
        'actual_hardware_data': False, 'covariance_calibrated_against_rate_solver': False,
        'scope': 'Conditional formula checked with draws from its own assumed Gaussian covariance; archive diagnostics reuse saved measured profiles, without rerunning IQ/correlation/RML. Means of centered complex integrals differ from means of magnitudes. No real receiver coherence or calibrated inference guarantee.'}
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n'); plot(summary, out)
    return summary


def plot(summary, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    archived = summary['archived_profiles']
    fig, axes = plt.subplots(1, 2 if archived else 1, figsize=(10 if archived else 6, 3.8))
    axes = np.atleast_1d(axes)
    rows = summary['gaussian_results']; x = np.arange(len(rows))
    axes[0].plot(x, [r['calculated_expected_centered_complex_coherence'] for r in rows], 'x', markersize=9, label='Conditional formula')
    axes[0].errorbar(x, [r['sample_mean_real'] for r in rows], yerr=[6*r['sample_standard_error_real'] for r in rows], fmt='o', label='Gaussian draws (6 SE)')
    axes[0].plot(x, [r['sample_mean_absolute_coherence'] for r in rows], 's', label='Mean magnitude (different quantity)')
    axes[0].set(xlabel='Baseline index', ylabel='Centered coherence', title='Explicit Gaussian error assumption'); axes[0].legend(fontsize=7)
    for i, r in enumerate(archived):
        axes[1].plot(i, r['diagnostic']['minimum_expected_centered_complex_coherence'], 'o', color='C0')
        measured = r['matched_control_minimum_amplitude_ratio']
        if measured is not None: axes[1].plot(i, measured, 'x', color='C1', markersize=8)
    if archived:
        axes[1].set_xticks(range(len(archived)), [r['label'] for r in archived], rotation=35, ha='right', fontsize=6)
        axes[1].set(ylabel='Minimum diagnostic / control ratio', title='Blue: parameter error only; orange: archive ratio', ylim=(.8, 1.01))
    fig.tight_layout(); fig.savefig(out/'rate-uncertainty.png', dpi=140); plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True); parser.add_argument('--profiles')
    summary = run(**vars(parser.parse_args()))
    print(json.dumps({'draws': summary['draws'], 'maximum_formula_sample_difference': max(
        abs(r['sample_mean_real']-r['calculated_expected_centered_complex_coherence']) for r in summary['gaussian_results']),
        'archived': [{'label': r['label'], 'minimum_expected': r['diagnostic']['minimum_expected_centered_complex_coherence'],
            'matched_control_ratio': r['matched_control_minimum_amplitude_ratio']} for r in summary['archived_profiles']]}, indent=2))
