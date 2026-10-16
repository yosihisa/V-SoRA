"""Finite-voltage checks of same-sample power normalization; no detection test."""
import argparse
import json
from pathlib import Path
import numpy as np
from vsora_simulator.bispectrum_observed_power import (
    observed_power_normalized_bispectrum, gaussian_rank_one_observed_power_moments)
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum
from .bispectrum_moments_validation import model


def experiment(label, samples, trials=32768, seed=85):
    if isinstance(trials, bool) or not isinstance(trials, int) or not 1024 <= trials <= 32768:
        raise ValueError('integer trials1024..32768 required')
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32-1:
        raise ValueError('integer seed0..2^32-1 required')
    if label not in ('rank_one', 'null', 'low', 'two_components'):
        raise ValueError('supported fixed covariance model required')
    if isinstance(samples, bool) or not isinstance(samples, int) or not 3 <= samples <= 128:
        raise ValueError('integer fixed experiment sample count3..128 required')
    s = np.ones((4, 4), complex) if label == 'rank_one' else np.eye(4, dtype=complex) if label == 'null' else model(label)[0]
    root = None if label == 'rank_one' else np.linalg.cholesky(s)
    rng = np.random.default_rng(seed)
    gains = np.exp(np.array([-.8, .3, 1.2, -.3]) + 1j*np.array([.2, -1., 2.4, .6]))
    normalized_parts = []; known_parts = []; max_gain_difference = 0.; triangles = None
    for start in range(0, trials, 256):
        n = min(256, trials-start)
        z = (rng.normal(size=(n, samples, 1 if root is None else 4))
             + 1j*rng.normal(size=(n, samples, 1 if root is None else 4))) / np.sqrt(2)
        x = np.repeat(z, 4, axis=-1) if root is None else z @ root.T
        q = observed_power_normalized_bispectrum(x); triangles = q['triangles']
        changed = observed_power_normalized_bispectrum(x*gains)['observed_power_normalized_u3']
        max_gain_difference = max(max_gain_difference, float(np.max(abs(changed-q['observed_power_normalized_u3']))))
        normalized_parts.append(q['observed_power_normalized_u3'])
        raw = distinct_sample_bispectrum(x)['distinct_sample_bispectrum']
        known_parts.append(raw / np.prod(s.diagonal().real[triangles], axis=-1))
    normalized = np.concatenate(normalized_parts); known = np.concatenate(known_parts)
    i, j, k = triangles.T
    known_mean = s[i,j]*s[j,k]*s[k,i] / (s[i,i].real*s[j,j].real*s[k,k].real)
    observed_mean = normalized.mean(axis=0)
    observed_se = np.c_[normalized.real.std(axis=0, ddof=1), normalized.imag.std(axis=0, ddof=1)] / np.sqrt(trials)
    raw_mean = known.mean(axis=0)
    raw_se = np.c_[known.real.std(axis=0, ddof=1), known.imag.std(axis=0, ddof=1)] / np.sqrt(trials)
    raw_difference = np.c_[(raw_mean-known_mean).real, (raw_mean-known_mean).imag]
    raw_ok = bool(np.all(abs(raw_difference) <= 6*raw_se+1e-12))
    variance = normalized.real.var(axis=0, ddof=1)
    result = {
        'model': label, 'samples': samples, 'trials': trials, 'seed': seed,
        'station_covariance_real_imag': np.stack((s.real, s.imag), axis=-1).tolist(),
        'triangles': triangles.tolist(),
        'known_population_power_normalized_mean_real_imag': np.c_[known_mean.real, known_mean.imag].tolist(),
        'known_power_mc_mean_real_imag': np.c_[raw_mean.real, raw_mean.imag].tolist(),
        'known_power_mc_standard_error_real_imag': raw_se.tolist(),
        'known_power_means_within_6se': raw_ok,
        'observed_power_mc_mean_real_imag': np.c_[observed_mean.real, observed_mean.imag].tolist(),
        'observed_power_mc_standard_error_real_imag': observed_se.tolist(),
        'observed_power_real_sample_variance': variance.tolist(),
        'observed_power_minus_population_target_real_imag': np.c_[(observed_mean-known_mean).real, (observed_mean-known_mean).imag].tolist(),
        'maximum_constant_gain_change_abs': max_gain_difference,
        'constant_gain_invariance_checked': max_gain_difference <= 2e-12,
        'general_observed_power_unbiasedness_assumed': False,
    }
    if label == 'rank_one':
        theory = gaussian_rank_one_observed_power_moments(samples)
        residual = normalized.real-theory['mean_real']
        second = residual**2
        second_mean = second.mean(axis=0)
        second_se = second.std(axis=0, ddof=1)/np.sqrt(trials)
        means_ok = bool(np.all(abs(observed_mean.real-theory['mean_real']) <= 6*observed_se[:, 0]+1e-12)
                        and np.max(abs(normalized.imag)) <= 1e-12)
        variance_ok = bool(np.all(abs(second_mean-theory['variance_real']) <= 6*second_se+1e-12))
        result.update(known_rank_one_theory=theory, observed_power_mean_within_6se=means_ok,
                      observed_power_centered_second_moment=second_mean.tolist(),
                      observed_power_second_moment_mc_standard_error=second_se.tolist(),
                      observed_power_variance_within_6se=variance_ok)
    elif label == 'null':
        result['observed_power_mean_within_6se'] = bool(np.all(abs(np.c_[observed_mean.real, observed_mean.imag]) <= 6*observed_se+1e-12))
    return result


def run(output, trials=32768):
    out = Path(output)
    if out.exists(): raise FileExistsError('new observed-power validation output required')
    out.mkdir(parents=True)
    settings = [('rank_one', m) for m in (3, 4, 16, 128)] + [('null', m) for m in (3, 16, 128)] + [('low', 16), ('two_components', 16)]
    cases = [experiment(label, m, trials, 85+n) for n, (label, m) in enumerate(settings)]
    passed = all(c['known_power_means_within_6se'] and c['constant_gain_invariance_checked']
                 and c.get('observed_power_mean_within_6se', True)
                 and c.get('observed_power_variance_within_6se', True) for c in cases)
    q = {'type': 'observed_power_bispectrum_validation', 'state': 'complete' if passed else 'failed_validation',
         'trials_per_condition': trials, 'cases': cases,
         'finite_common_gaussian_voltages_generated': True, 'station_gain_constant_within_window_assumed': True,
         'general_observed_power_moments_calculated': False, 'bias_correction_applied': False,
         'classification_performed': False, 'phase_likelihood_calibrated': False,
         'physical_adc_vdif_processed': False, 'unknown_lo_estimated': False,
         'actual_temporal_independence_verified': False, 'real_hardware_validation_performed': False,
         'production_rml_noise_model_changed': False,
         'scope': 'Known iid Gaussian voltages and constant station gains only. Rank-one ratio moments and null mean are tested; arbitrary-S observed-power means are reported without claiming unbiasedness. No shape decision, low-SNR image likelihood or hardware guarantee.'}
    (out/'summary.json').write_text(json.dumps(q, indent=2, allow_nan=False)+'\n')
    plot(q, out/'observed-power-bispectrum.png')
    if not passed: raise RuntimeError('fixed observed-power validation criteria failed')
    return q


def plot(q, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cases = [c for c in q['cases'] if c['model'] == 'rank_one']; x = [c['samples'] for c in cases]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].plot(x, [c['known_rank_one_theory']['mean_real'] for c in cases], label='Same-sample power: exact rank-one mean')
    axes[0].errorbar(x, [c['observed_power_mc_mean_real_imag'][0][0] for c in cases],
                     yerr=[2*c['observed_power_mc_standard_error_real_imag'][0][0] for c in cases], fmt='o', capsize=3, label='Gaussian voltage MC, 2 SE')
    axes[0].axhline(1, color='black', linestyle='--', label='Known population power: target 1')
    axes[0].set(ylabel='Mean normalized U3', title='Gain cancellation retains finite-sample bias')
    axes[0].legend(fontsize=7)
    axes[1].plot(x, [c['known_rank_one_theory']['variance_real'] for c in cases], label='Exact rank-one variance')
    axes[1].errorbar(x, [c['observed_power_centered_second_moment'][0] for c in cases],
                     yerr=[2*c['observed_power_second_moment_mc_standard_error'][0] for c in cases], fmt='o', capsize=3, label='Gaussian voltage MC, 2 SE')
    axes[1].set(yscale='log', ylabel='Real variance', title='Known model only; not observed uncertainty')
    axes[1].legend(fontsize=7)
    for ax in axes:
        ax.set_xscale('log'); ax.set_xticks(x, [str(m) for m in x]); ax.set_xlabel('Independent samples M'); ax.grid(alpha=.2)
    fig.tight_layout(); fig.savefig(path, dpi=140); plt.close(fig)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', required=True); parser.add_argument('--trials', type=int, default=32768)
    result=run(**vars(parser.parse_args())); print(json.dumps({'state': result['state'], 'conditions': len(result['cases']), 'trials_per_condition': result['trials_per_condition']}))
