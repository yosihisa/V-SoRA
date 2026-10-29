"""147の保存基線rateを固定し、同じpower表の採用群だけを比較する。"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
from vsora_correlator.time_scatter import time_power_moments


def load_prior_helper():
    path = Path(__file__).with_name('rate_fit_reuse_validation.py')
    spec = importlib.util.spec_from_file_location('prior147_helper', path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    # 新しいfit/graph呼出を禁止。元workflowのrunは呼ばない。
    def forbidden(*args, **kwargs):
        raise AssertionError('stage154 must reuse archived rates without refitting')
    helper.estimate_station_rates = helper.diagnose_rate_graph = forbidden
    return helper


def statistics(x):
    x = np.asarray(x); n = len(x)
    return {'count': n, 'state': 'empty' if n == 0 else 'descriptive',
            'mean': float(x.mean()) if n else None,
            'mcse': float(x.std(ddof=1)/np.sqrt(n)) if n > 1 else None}


def evaluation_control(x):
    q = statistics(x)
    if q['count'] < 2:
        return {**q, 'control_state': 'unverified_insufficient_trials'}
    assert abs(q['mean']) < 6*q['mcse']+1e-11
    return {**q, 'control_state': 'within_fixed_6mcse'}


def run(archive, output):
    prior = load_prior_helper()
    source = Path(archive)
    old = json.loads((source/'summary.json').read_text())
    assert old['stage'] == 147 and old['trials_per_condition'] == 256
    assert old['unchanged_detection_settings'] == {'min_snr': 8., 'min_peak_z': 8., 'max_reduced_chisq': 3.}
    original = np.load(source/'arrays.npz', allow_pickle=False)
    out = Path(output)
    if out.exists():
        raise FileExistsError('choose a new archived-rate postselection output')
    out.mkdir(parents=True); began = time.monotonic()
    arrays = {'pairs': prior.PAIRS, 'time_cells_s': prior.TIMES}
    groups = []
    fingerprint_count = 0
    for group in old['groups']:
        condition = group['condition']; sigma = group['quadrature_sigma']
        assert sigma == (.5, 1.)[condition]
        candidate = np.full((256, 3), np.nan)
        available = np.zeros((256, 3), bool)
        detected = np.zeros((256, 3), bool)
        prediction = np.full((256, 3), np.nan)
        powers = {role: np.full((256, 3), np.nan) for role in ('train', 'evaluation')}
        trial_rows = []
        for trial, row in enumerate(group['trials_retained']):
            assert row['trial'] == trial
            training, evaluation = (prior.pilot(condition, trial, role, sigma) for role in (0, 1))
            assert prior.fingerprint(training) == row['training_input_sha256']
            fingerprint_count += 1
            stored = row['profile'] if row['profile'] is not None else row['failure_graph']
            assert stored['time_reference_s'] == prior.EPOCH
            records = stored['baseline_estimates']
            assert [r['pair'] for r in records] == prior.PAIRS.tolist()
            rates = [record.get('rate_hz') for record in records]
            for b, record in enumerate(records):
                if rates[b] is None:
                    assert not record['accepted']
                    continue
                candidate[trial, b] = rates[b]
                available[trial, b] = True
                detected[trial, b] = record['accepted']
            mask = available[trial]
            delta = candidate[trial, mask]-prior.TRUE_BASELINE_RATES[mask]
            direct = abs(np.mean(np.exp(-2j*np.pi*delta[:, None]*prior.TAU), axis=1))**2
            formula = (np.sinc(prior.CELLS*delta*prior.CADENCE)/np.sinc(delta*prior.CADENCE))**2
            np.testing.assert_allclose(direct, formula, rtol=1e-11, atol=1e-12)
            prediction[trial, mask] = direct
            for role, data in [('train', training), ('evaluation', evaluation)]:
                # 元のoracle値を照合し、再構成した旧147の入力であることを確認。
                oracle = prior.corrected_power(data, prior.RATES, sigma)
                key = f'condition{condition}_{role}_all_oracle_'
                np.testing.assert_array_equal(oracle['mean'], original[key+'complex_mean'][trial])
                np.testing.assert_array_equal(oracle['mean_power'], original[key+'mean_power'][trial])
                if mask.any():
                    z = data['visibilities'][:, 0, mask]*np.exp(-2j*np.pi*prior.TAU[:, None]*candidate[trial, mask])
                    result = time_power_moments(z, np.full(z.shape, 2*sigma**2))
                    independent = abs(np.sum(z, axis=0)/prior.CELLS)**2-2*sigma**2/prior.CELLS
                    np.testing.assert_allclose(result['mean_power'], independent, rtol=1e-11, atol=1e-12)
                    powers[role][trial, mask] = result['mean_power']
            trial_rows.append({'trial': trial, 'original_station_state': row['state'],
                               'original_station_reason': row.get('reason'),
                               'reported_baseline_rates_hz': rates,
                               'detected_baselines': detected[trial].tolist(),
                               'baseline_reasons': [r.get('reason') for r in records]})
        assert not np.any(detected & ~available)
        rejected = available & ~detected
        masks = {'available': available, 'detected': detected, 'rejected': rejected}
        result_groups = {}
        for label, mask in masks.items():
            per_baseline = []
            for b in range(3):
                keep = mask[:, b]
                train = powers['train'][keep, b]; evaluation = powers['evaluation'][keep, b]
                expected = prediction[keep, b]
                per_baseline.append({'pair': prior.PAIRS[b].tolist(), 'trial_indices': np.flatnonzero(keep).tolist(),
                    'training_power': statistics(train), 'evaluation_power': statistics(evaluation),
                    'training_minus_known_evaluation_prediction': statistics(train-expected),
                    'evaluation_minus_known_prediction': evaluation_control(evaluation-expected),
                    'training_minus_evaluation_paired': statistics(train-evaluation),
                    'train_negative': int(np.count_nonzero(train < 0)),
                    'evaluation_negative': int(np.count_nonzero(evaluation < 0)),
                    'train_above_one': int(np.count_nonzero(train > 1)),
                    'evaluation_above_one': int(np.count_nonzero(evaluation > 1))})
            result_groups[label] = per_baseline
        for role in powers:
            for b in range(3):
                all_values = powers[role][available[:, b], b]
                parts = [powers[role][m[:, b], b] for m in (detected, rejected)]
                if len(all_values):
                    mixture = sum(len(x)*x.mean() for x in parts if len(x))/len(all_values)
                    np.testing.assert_allclose(all_values.mean(), mixture, rtol=1e-11, atol=1e-12)
        for name, values in [('reported_candidate_rates_hz', candidate), ('known_eval_power_prediction', prediction),
                             ('train_power', powers['train']), ('evaluation_power', powers['evaluation']),
                             *[(label+'_mask', mask) for label, mask in masks.items()]]:
            arrays[f'condition{condition}_{name}'] = values
        groups.append({'condition': condition, 'quadrature_sigma': sigma, 'original_trial_count': 256,
                       'not_available_count_by_baseline': (~available).sum(axis=0).tolist(),
                       'original_station_success_count': sum(r['original_station_state'] == 'estimated' for r in trial_rows),
                       'groups': result_groups, 'all_original_trial_rows': trial_rows,
                       'support_weighted_mean_partition_verified': True})
    original.close()
    summary = {'stage': 154, 'state': 'complete', 'groups': groups,
        'original147_training_fingerprints_verified': fingerprint_count,
        'original147_train_eval_oracle_rows_verified': fingerprint_count*2,
        'new_rate_fits': 0, 'new_independent_trials': 0, 'original147_trial_pairs_reused': 512,
        'original_seed_sequence': '[147, condition, trial, role0_train_or1_evaluation]',
        'same_candidate_rate_power_table_used_for_all_masks': True,
        'local_baseline_rates_are_not_consistent_station_profiles': True,
        'search_availability_and_station_solution_gates_removed': False,
        'gate_difference_or_training_residual_is_causal_estimator_bias': False,
        'MCSE_uses_original147_model_replicates_not_new_trials': True,
        'cited_archive_summary_sha256': hashlib.sha256((source/'summary.json').read_bytes()).hexdigest(),
        'cited_archive_arrays_sha256': hashlib.sha256((source/'arrays.npz').read_bytes()).hexdigest(),
        'scope': 'Archived baseline candidates and detection masks; exact old147 Gaussian visibility reconstruction and existing051 power. Gate-only postselection accounting, not ungated station estimation or physical coherence/confidence/image calibration.'}
    (out/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
    np.savez_compressed(out/'arrays.npz', **arrays)
    origins = {n: m.__file__ for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None)}
    (out/'runtime-private.json').write_text(json.dumps({'module_paths': origins,
        'wall_s': time.monotonic()-began, 'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}, indent=2)+'\n')
    print(json.dumps({'stage': 154, 'state': 'complete', 'fingerprints_verified': fingerprint_count,
                      'available_counts': [[x['training_power']['count'] for x in g['groups']['available']] for g in groups]}))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); run(args.archive, args.output)
