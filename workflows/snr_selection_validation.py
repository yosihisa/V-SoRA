"""観測SNRで選別した群と全試行の雑音推定を、既存APIで区別する。"""
import argparse
import importlib.util
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
from vsora_correlator.noise_diagnostics import diagnose_noise_cell
from vsora_imaging.closure import form_closures
from vsora_imaging.closure_noise import joint_closure_noise
from vsora_simulator.visibility_moments import visibility_noise_moments
from vsora_simulator.visibility_noise_estimate import estimate_visibility_noise


spec = importlib.util.spec_from_file_location('existing_sample_noise', Path(__file__).with_name('sample_noise_validation.py'))
existing = importlib.util.module_from_spec(spec); spec.loader.exec_module(existing)
TRIALS = 4096
SAMPLES = 128
GROUPS = ('all', 'joint_baseline5', 'joint_triangle5', 'joint_baseline10', 'joint_triangle10',
          'production_baseline10', 'production_triangle10')


def statistics(values, estimates, selected):
    """真値からの残差、選別後の中心化共分散、MSEを混同しない。"""
    x = values[selected]; c = estimates[selected]; n = len(x)
    if n == 0:
        return {'count': 0, 'state': 'empty', 'statistics': None}
    mean = x.mean(axis=0); second = np.einsum('ti,tj->ij', x, x)/n
    result = {'mean_error': mean, 'mean_estimated_covariance': c.mean(axis=0), 'error_second_moment': second}
    if n == 1:
        result.update(centered_covariance=None, mean_mcse=None, covariance_estimate_mean_mcse=None, second_moment_mcse=None)
    else:
        centered = np.cov(x, rowvar=False, ddof=1)
        np.testing.assert_allclose(second, centered*(n-1)/n+np.outer(mean, mean), rtol=1e-11, atol=1e-13)
        result.update(centered_covariance=centered, mean_mcse=x.std(axis=0, ddof=1)/np.sqrt(n),
            covariance_estimate_mean_mcse=c.std(axis=0, ddof=1)/np.sqrt(n),
            second_moment_mcse=(x[:, :, None]*x[:, None, :]).std(axis=0, ddof=1)/np.sqrt(n))
    return {'count': n, 'state': 'descriptive' if n > 1 else 'insufficient_selected_trials', 'statistics': result}


def cell_probe(sample, weights, pairs, expected):
    n = len(sample); power = sample.diagonal().real
    data = {'visibilities': sample[pairs[:, 0], pairs[:, 1]][None, None, :],
        'weights': weights[None, None, :], 'pairs': pairs, 'times_s': np.array([.002]),
        'frequencies_hz': np.array([1.42e9]), 'uvw_lambda': np.zeros((1, 1, len(pairs), 3)),
        'valid_fft_count': np.full((1, len(pairs)), SAMPLES, dtype=np.int64),
        'diagnostic_station_power': power[None, None, :],
        'diagnostic_station_valid_fft_count': np.full((1, n), SAMPLES, dtype=np.int64),
        'diagnostic_station_flags': np.zeros((1, 1, n), dtype=np.uint8),
        'metadata': {'visibility_unit': 'ADC^2', 'diagnostic_power_unit': 'ADC^2',
                     'config': {'stations': [{'id': f'ST{i+1:02d}'} for i in range(n)]}}}
    q = diagnose_noise_cell(data, 0, 0)
    assert q['state'] == 'conditional_estimate'
    np.testing.assert_array_equal(q['closure_joint_valid'], expected['joint_valid'])
    return {'cell_state': q['state'], 'default5_joint_valid_rows': int(np.sum(q['closure_joint_valid'])),
            'phase_rows': q['phase_count'], 'logamp_rows': q['logamp_count'],
            'synthetic_format_unit_is_not_physical_adc_calibration': True}


def run(output):
    out = Path(output)
    if out.exists():
        raise FileExistsError('choose a new SNR selection output')
    began = time.monotonic(); out.mkdir(parents=True); arrays = {}; rows = []
    for case, rho in enumerate((0., .45, 1.6)):
        station = np.eye(4)+rho*np.ones((4, 4)); truth = visibility_noise_moments(station, SAMPLES)
        pairs = truth['pairs']; b = len(pairs); mu = np.r_[truth['mean'].real, truth['mean'].imag]
        rng = np.random.default_rng(144000+case); factor = np.linalg.cholesky(station)
        errors = np.empty((TRIALS, 2*b)); estimates = np.empty((TRIALS, 2*b, 2*b))
        masks = {g: np.zeros(TRIALS, bool) for g in GROUPS}; masks['all'][:] = True
        snr = np.empty((TRIALS, 2)); baseline_values = np.empty(TRIALS, complex)
        probe = None
        for first in range(0, TRIALS, 32):
            count = min(32, TRIALS-first)
            z = (rng.normal(size=(count, SAMPLES, 4))+1j*rng.normal(size=(count, SAMPLES, 4)))/np.sqrt(2)
            x = z @ factor.T; sample = np.einsum('tmi,tmj->tij', x, x.conj())/SAMPLES
            _, corrected = existing.batch_covariance(sample, SAMPLES, pairs)
            for local in range(count):
                trial = first+local; v = sample[local, pairs[:, 0], pairs[:, 1]]
                if trial < 2:
                    public = estimate_visibility_noise(sample[local], SAMPLES, pairs)
                    np.testing.assert_allclose(public['real_covariance'], corrected[local], rtol=1e-11, atol=1e-12)
                q5 = joint_closure_noise(v, corrected[local], pairs, min_snr=5.)
                q10 = joint_closure_noise(v, corrected[local], pairs, min_snr=10.)
                power = sample[local].diagonal().real
                weights = 2*SAMPLES/(power[pairs[:, 0]]*power[pairs[:, 1]])
                prod = form_closures(v, weights, pairs, min_snr=10.)
                assert tuple(q5['triangles'][0]) == (0, 1, 2) and tuple(prod['triangles'][0]) == (0, 1, 2)
                masks['joint_baseline5'][trial] = q5['baseline_valid'][0]
                masks['joint_triangle5'][trial] = q5['joint_valid'][0]
                masks['joint_baseline10'][trial] = q10['baseline_valid'][0]
                masks['joint_triangle10'][trial] = q10['joint_valid'][0]
                masks['production_baseline10'][trial] = prod['baseline_valid'][0]
                masks['production_triangle10'][trial] = prod['phase_valid'][0]
                assert np.all(q10['baseline_valid'] <= q5['baseline_valid'])
                errors[trial] = np.r_[v.real, v.imag]-mu; estimates[trial] = corrected[local]
                snr[trial] = [q5['baseline_snr'][0], prod['baseline_snr'][0]]; baseline_values[trial] = v[0]
                if trial == 0:
                    probe = cell_probe(sample[local], weights, pairs, q5)
        groups = {}
        for name in GROUPS:
            value = statistics(errors, estimates, masks[name]); stats = value.pop('statistics')
            if stats is not None:
                for field, array in stats.items():
                    if array is not None:
                        arrays[f'case{case}_{name}_{field}'] = array
                if name == 'all':
                    scale = np.max(np.diag(truth['real_covariance']))
                    assert np.all(abs(stats['mean_error']) <= 6*stats['mean_mcse']+1e-11*np.sqrt(scale))
                    assert np.all(abs(stats['mean_estimated_covariance']-truth['real_covariance']) <=
                                  6*stats['covariance_estimate_mean_mcse']+1e-11*scale)
                    assert np.all(abs(stats['error_second_moment']-truth['real_covariance']) <=
                                  6*stats['second_moment_mcse']+1e-11*scale)
                value.update(baseline01_real_mean_error=float(stats['mean_error'][0]),
                    baseline01_imag_mean_error=float(stats['mean_error'][b]),
                    baseline01_real_error_mse=float(stats['error_second_moment'][0, 0]),
                    baseline01_real_mean_estimated_variance=float(stats['mean_estimated_covariance'][0, 0]))
            else:
                value.update(baseline01_real_mean_error=None, baseline01_imag_mean_error=None,
                             baseline01_real_error_mse=None, baseline01_real_mean_estimated_variance=None)
            value['rejected_count'] = TRIALS-value['count']; groups[name] = value
            arrays[f'case{case}_{name}_selection_mask'] = masks[name]
        arrays[f'case{case}_baseline01_visibility'] = baseline_values
        arrays[f'case{case}_baseline01_observed_snr_joint_and_production'] = snr
        arrays[f'case{case}_true_visibility_covariance'] = truth['real_covariance']
        rows.append({'case': case, 'rho': rho, 'samples': SAMPLES, 'trials': TRIALS, 'seed': 144000+case,
            'known_quadrature_snr_validation_only': float(rho*np.sqrt(2*SAMPLES)/(1+rho)),
            'groups': groups, 'all_trial_means_mse_and_estimated_covariance_within_fixed_6mcse': True,
            'joint10_production10_baseline_mask_disagreements': int(np.count_nonzero(masks['joint_baseline10'] != masks['production_baseline10'])),
            'joint10_production10_triangle_mask_disagreements': int(np.count_nonzero(masks['joint_triangle10'] != masks['production_triangle10'])),
            'first_trial_cell047_probe': probe})
        print(json.dumps({'rho': rho, 'counts': {k: v['count'] for k, v in groups.items()}}), flush=True)
    result = {'stage': 144, 'state': 'complete', 'cases': rows, 'independent_trials_per_case': TRIALS,
        'selection_uses_observed_values_only': True, 'fixed_baseline': [0, 1], 'fixed_triangle': [0, 1, 2],
        'multiple_masks_share_trials': True, 'selected_population_unbiasedness_or_coverage_claimed': False,
        'unknown_covariance_or_image_likelihood_api_added': False, 'production_rml_changed': False,
        'physical_adc_vdif_processed': False, 'real_hardware_or_fft_independence_calibrated': False,
        'scope': 'Known iid zero-mean proper Gaussian voltages. All-trial controls against known covariance; selected subsets descriptive only. No rate fit, filter, quantization, masks, unknown gain/SEFD or image calibration.'}
    (out/'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    np.savez_compressed(out/'arrays.npz', **arrays)
    origins = {n: m.__file__ for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None)}
    (out/'runtime-private.json').write_text(json.dumps({'module_paths': origins, 'wall_s': time.monotonic()-began,
        'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}, indent=2)+'\n')
    assert sum(p.stat().st_size for p in out.iterdir()) < 16*1024**2
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    run(parser.parse_args().output)
