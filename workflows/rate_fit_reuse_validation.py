"""同pilot推定と独立雑音pilotのpowerを、既存rate/051 APIで比較する。"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
from vsora_correlator.rate import estimate_station_rates
from vsora_correlator.rate_graph import diagnose_rate_graph
from vsora_correlator.time_scatter import time_power_moments


TRIALS, CELLS, CADENCE = 256, 64, .008
PAIRS = np.array([[0, 1], [0, 2], [1, 2]])
RATES = np.array([0., 7., -11.])
AMPLITUDES = np.exp(1j*np.array([.3, -.7, 1.1]))
TIMES = (np.arange(CELLS)+.5)*CADENCE
EPOCH = float((TIMES[0]+TIMES[-1])/2)
TAU = TIMES-EPOCH
TRUE_BASELINE_RATES = RATES[PAIRS[:, 0]]-RATES[PAIRS[:, 1]]
EXPECTED_CENTER_MEAN = AMPLITUDES*np.exp(2j*np.pi*TRUE_BASELINE_RATES*EPOCH)


def pilot(condition, trial, role, sigma):
    """固定model平均を共有し、train/eval雑音の乱数roleを分ける。"""
    rng = np.random.default_rng(np.random.SeedSequence([147, condition, trial, role]))
    noise = sigma*(rng.normal(size=(CELLS, 1, 3))+1j*rng.normal(size=(CELLS, 1, 3)))
    mean = AMPLITUDES[None, None, :]*np.exp(2j*np.pi*TIMES[:, None, None]*TRUE_BASELINE_RATES)
    return {'visibilities': mean+noise, 'weights': np.full(noise.shape, 1/sigma**2),
            'times_s': TIMES.copy(), 'pairs': PAIRS.copy()}


def fingerprint(data):
    return {key: hashlib.sha256(value.tobytes()).hexdigest() for key, value in data.items()}


def corrected_power(data, station_rates, sigma):
    rates = np.asarray(station_rates)
    baseline = rates[PAIRS[:, 0]]-rates[PAIRS[:, 1]]
    z = data['visibilities'][:, 0]*np.exp(-2j*np.pi*TAU[:, None]*baseline)
    # data依存の回転には固定回転の不偏性を仮定しない。独立evalだけに制御を置く。
    return time_power_moments(z, np.full(z.shape, 2*sigma**2))


def statistics(values):
    x = np.asarray(values); n = len(x)
    if n == 0:
        return {'count': 0, 'state': 'empty', 'mean': None, 'mcse': None}
    return {'count': n, 'state': 'descriptive' if n > 1 else 'insufficient_trials',
            'mean': x.mean(axis=0).tolist(),
            'mcse': (x.std(axis=0, ddof=1)/np.sqrt(n)).tolist() if n > 1 else None}


def fixed_mean_control(values, expected):
    q = statistics(values)
    if q['count'] < 2:
        return {**q, 'control_state': 'unverified_insufficient_trials'}
    difference = np.asarray(q['mean'])-expected
    np.testing.assert_array_less(abs(difference), 6*np.asarray(q['mcse'])+1e-11)
    return {**q, 'control_state': 'within_fixed_6mcse'}


def run(output):
    out = Path(output)
    if out.exists():
        raise FileExistsError('choose a new rate reuse validation output')
    out.mkdir(parents=True); began = time.monotonic()
    arrays = {'pairs': PAIRS, 'time_cells_s': TIMES, 'known_center_mean_validation_only': EXPECTED_CENTER_MEAN}
    groups = []
    for condition, sigma in enumerate((.5, 1.)):
        rows = []; states = Counter(); accepted = []
        oracle = {role: {'mean': [], 'power': []} for role in ('train', 'evaluation')}
        fitted = {role: {'mean': [], 'power': []} for role in ('train', 'evaluation')}
        predictions = []; rate_errors = []
        for trial in range(TRIALS):
            training, evaluation = (pilot(condition, trial, role, sigma) for role in (0, 1))
            before = fingerprint(training)
            true_controls = {}
            for role, data in [('train', training), ('evaluation', evaluation)]:
                q = corrected_power(data, RATES, sigma)
                oracle[role]['mean'].append(q['mean']); oracle[role]['power'].append(q['mean_power'])
                true_controls[role] = q['mean_power']
            # 真値・評価data・生成定数をsolverの引数へ加えない。
            assert set(training) == {'visibilities', 'weights', 'times_s', 'pairs'}
            try:
                profile = estimate_station_rates(training, max_rate_hz=50.)
            except ValueError as exc:
                reason = str(exc)
                if not any(s in reason for s in ('detected rate graph is disconnected',
                                                 'baseline rate estimates inconsistent with station rates')):
                    raise
                graph = diagnose_rate_graph(training, max_rate_hz=50.)
                states[reason] += 1
                rows.append({'trial': trial, 'state': 'not_estimated', 'reason': reason,
                             'profile': None, 'failure_graph': graph,
                             'fitted_power': None, 'training_input_sha256': before})
                assert fingerprint(training) == before
                continue
            assert fingerprint(training) == before and profile['time_reference_s'] == EPOCH
            estimates = np.array(profile['station_rates_hz'])
            delta = estimates[PAIRS[:, 0]]-estimates[PAIRS[:, 1]]-TRUE_BASELINE_RATES
            direct = abs(np.mean(np.exp(-2j*np.pi*delta[:, None]*TAU), axis=1))**2
            dirichlet = (np.sinc(CELLS*delta*CADENCE)/np.sinc(delta*CADENCE))**2
            np.testing.assert_allclose(direct, dirichlet, rtol=1e-11, atol=1e-12)
            assert np.all(direct >= 0) and np.all(direct <= 1+1e-12)
            actual = {}
            for role, data in [('train', training), ('evaluation', evaluation)]:
                q = corrected_power(data, estimates, sigma)
                fitted[role]['mean'].append(q['mean']); fitted[role]['power'].append(q['mean_power'])
                actual[role] = q['mean_power'].tolist()
            predictions.append(direct); rate_errors.append((estimates-RATES)[1:]); accepted.append(trial)
            states['estimated'] += 1
            rows.append({'trial': trial, 'state': 'estimated', 'profile': profile,
                         'failure_graph': None, 'training_input_sha256': before,
                         'known_independent_eval_mean_power_prediction': direct.tolist(),
                         'fitted_power': actual})
        indices = np.array(accepted, int); prediction = np.asarray(predictions).reshape(-1, 3)
        controls = {}; comparisons = {}; counts = {}
        for role in ('train', 'evaluation'):
            mean = np.asarray(oracle[role]['mean']); power = np.asarray(oracle[role]['power'])
            error = mean-EXPECTED_CENTER_MEAN
            controls[role] = {'all_trial_complex_mean_error': fixed_mean_control(np.c_[error.real, error.imag], 0.),
                              'all_trial_noise_subtracted_mean_power': fixed_mean_control(power, 1.)}
            fp = np.asarray(fitted[role]['power']).reshape(-1, 3)
            residual = fp-prediction; paired = fp-power[indices]
            comparisons[role] = {'fitted_minus_oracle_paired_difference': statistics(paired),
                                 'fitted_minus_known_independent_eval_prediction':
                                 fixed_mean_control(residual, 0.) if role == 'evaluation' else statistics(residual)}
            counts[role] = {'all_oracle_power_negative': int(np.count_nonzero(power < 0)),
                            'all_oracle_power_above_one': int(np.count_nonzero(power > 1)),
                            'estimated_power_negative': int(np.count_nonzero(fp < 0)),
                            'estimated_power_above_one': int(np.count_nonzero(fp > 1)),
                            'fitted_minus_oracle_negative': int(np.count_nonzero(paired < 0)),
                            'fitted_minus_oracle_positive': int(np.count_nonzero(paired > 0))}
            for key, value in [('all_oracle_complex_mean', mean), ('all_oracle_mean_power', power),
                               ('estimated_complex_mean', np.asarray(fitted[role]['mean']).reshape(-1, 3)),
                               ('estimated_mean_power', fp), ('fit_minus_oracle', paired),
                               ('fit_minus_independent_prediction', residual)]:
                arrays[f'condition{condition}_{role}_{key}'] = value
        arrays[f'condition{condition}_accepted_trial_indices'] = indices
        arrays[f'condition{condition}_known_eval_power_prediction'] = prediction
        arrays[f'condition{condition}_estimated_rate_error_validation_only'] = np.asarray(rate_errors).reshape(-1, 2)
        group = {'condition': condition, 'quadrature_sigma': sigma, 'trials': TRIALS,
                 'states': dict(states), 'estimated_count': len(accepted),
                 'all_trial_oracle_controls': controls, 'accepted_paired_comparisons': comparisons,
                 'finite_value_counts': counts, 'trials_retained': rows,
                 'accepted_statistics_conditioned_on_training_selection': True,
                 'conditional_prediction_uses_truth_only_after_fitting': True}
        assert sum(states.values()) == TRIALS and len(rows) == TRIALS
        groups.append(group)
        print(json.dumps({'condition': condition, 'sigma': sigma, 'states': dict(states),
                          'paired_comparisons': comparisons}), flush=True)
    result = {'stage': 147, 'state': 'complete', 'groups': groups, 'trials_per_condition': TRIALS,
              'stations': 3, 'time_cells': CELLS, 'channels': 1, 'cadence_s': CADENCE,
              'seed_sequence_definition': '[147, condition_index, trial_index, role_0_train_or_1_evaluation]',
              'true_station_rates_hz_generation_and_validation_only': RATES.tolist(),
              'fixed_baseline_amplitudes_generation_and_validation_only_real': AMPLITUDES.real.tolist(),
              'fixed_baseline_amplitudes_generation_and_validation_only_imag': AMPLITUDES.imag.tolist(),
              'fit_inputs_only': ['visibilities', 'weights', 'times_s', 'pairs'],
              'max_rate_hz': 50., 'unchanged_detection_settings': {'min_snr': 8., 'min_peak_z': 8., 'max_reduced_chisq': 3.},
              'independent_train_eval_noise_is_model_assumption': True,
              'two_noise_levels_are_not_paired_experiments': True,
              'training_fit_power_statistics_descriptive_only': True,
              'profile_failures_replaced_with_zero_power': False,
              'source_environment_repetition_adds_independent_trials': False,
              'physical_iq_vdif_or_original131_processed': False, 'production_rml_changed': False,
              'unknown_real_lo_gain_sefd_or_confidence_calibrated': False,
              'scope': 'Known independent circular Gaussian visibility errors per cell/baseline. Actual constant-rate solver and graph/default gates, existing051 noise-subtracted mean power. Same-pilot reuse descriptive; independent-noise evaluation checked against known post-fit Dirichlet mean-power prediction. No voltage/FIR/quantization, empirical iid claim, unknown hardware calibration or image likelihood.'}
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
