"""旧基線候補をreplayし、局LS計算後のχ²棄却だけを観察する。"""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import sys
import time
from unittest.mock import patch

import numpy as np
from vsora_correlator import rate
from vsora_correlator.time_scatter import time_power_moments

RTOL, ATOL = 1e-11, 1e-12


def prior_helper():
    spec = importlib.util.spec_from_file_location('prior147', Path(__file__).with_name('rate_fit_reuse_validation.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    def forbidden(*args, **kwargs):
        raise AssertionError('only archived baseline candidates may be used')
    module.estimate_station_rates = module.diagnose_rate_graph = forbidden
    return module


def independent_normal(records):
    """3局の2未知量。一般solverを使わず2x2逆式で計算する。"""
    accepted = [r for r in records if r['accepted']]
    incidence = np.array([[float(i == 1)-float(j == 1), float(i == 2)-float(j == 2)]
                          for i, j in [r['pair'] for r in accepted]]).reshape(-1, 2)
    sigma = np.array([r['rate_sigma_hz'] for r in accepted])
    measured = np.array([r['rate_hz'] for r in accepted])
    lhs = incidence/sigma[:, None]; rhs = measured/sigma
    if len(accepted) < 2:
        return None, None, lhs, rhs
    aa = np.sum(lhs[:, 0]**2); bb = np.sum(lhs[:, 0]*lhs[:, 1]); cc = np.sum(lhs[:, 1]**2)
    dd = np.sum(lhs[:, 0]*rhs); ee = np.sum(lhs[:, 1]*rhs); determinant = aa*cc-bb*bb
    assert determinant > 0
    solution = np.array([(cc*dd-bb*ee)/determinant, (aa*ee-bb*dd)/determinant])
    residual = lhs @ solution-rhs; degrees = len(accepted)-2
    reduced = float(np.sum(residual**2)/degrees) if degrees else None
    return solution, reduced, lhs, rhs


def statistics(values, control=False):
    x = np.asarray(values); n = len(x)
    result = {'count': n, 'mean': x.mean(axis=0).tolist() if n else None,
              'mcse': (x.std(axis=0, ddof=1)/np.sqrt(n)).tolist() if n > 1 else None,
              'state': 'descriptive' if n > 1 else 'empty_or_insufficient'}
    if control:
        result['control_state'] = 'unverified_insufficient_trials'
        if n > 1:
            assert np.all(abs(x.mean(axis=0)) < 6*x.std(axis=0, ddof=1)/np.sqrt(n)+1e-11)
            result['control_state'] = 'within_fixed_6mcse'
    return result


def run(archive, output):
    out = Path(output)
    if out.exists():
        raise FileExistsError('choose a new station chisq replay output')
    source = Path(archive); old = json.loads((source/'summary.json').read_text())
    assert old['stage'] == 147 and old['trials_per_condition'] == 256
    assert old['unchanged_detection_settings'] == {'min_snr': 8., 'min_peak_z': 8., 'max_reduced_chisq': 3.}
    out.mkdir(parents=True); began = time.monotonic(); prior = prior_helper()
    arrays = {'pairs': prior.PAIRS, 'time_cells_s': prior.TIMES}; groups = []; fingerprints = 0
    observed_candidates = 0; successful_archive_powers = 0
    original_lstsq = np.linalg.lstsq
    with np.load(source/'arrays.npz', allow_pickle=False) as original:
        for group in old['groups']:
            condition = group['condition']; sigma = group['quadrature_sigma']
            candidate = np.full((256, 3), np.nan); chisq = np.full(256, np.nan)
            connected = np.zeros(256, bool); accepted = connected.copy()
            prediction = np.full((256, 3), np.nan)
            powers = {role: np.full((256, 3), np.nan) for role in ('train', 'evaluation')}
            rows = []; success_index = 0
            for trial, row in enumerate(group['trials_retained']):
                assert row['trial'] == trial
                training, evaluation = (prior.pilot(condition, trial, role, sigma) for role in (0, 1))
                before = prior.fingerprint(training); assert before == row['training_input_sha256']; fingerprints += 1
                stored = row['profile'] if row['profile'] is not None else row['failure_graph']
                records = stored['baseline_estimates']; assert [r['pair'] for r in records] == prior.PAIRS.tolist()
                solution, reduced, lhs, rhs = independent_normal(records)
                captures = []
                def replay(v, w, t, pairs, dt, max_rate, min_snr, min_peak):
                    assert max_rate == 50. and min_snr == min_peak == 8.
                    np.testing.assert_array_equal(v, training['visibilities'])
                    np.testing.assert_array_equal(w, training['weights'])
                    np.testing.assert_array_equal(t, prior.TIMES)
                    np.testing.assert_array_equal(pairs, prior.PAIRS)
                    return stored['time_reference_s'], deepcopy(records)
                def observe(a, b, rcond=None):
                    np.testing.assert_array_equal(a, lhs); np.testing.assert_array_equal(b, rhs)
                    result = original_lstsq(a, b, rcond=rcond); captures.append(result[0].copy()); return result
                profile = None; failure = None
                with patch.object(rate, '_baseline_rate_records', replay), patch.object(rate.np.linalg, 'lstsq', observe):
                    try:
                        profile = rate.estimate_station_rates(training, max_rate_hz=50.)
                    except ValueError as exc:
                        failure = str(exc)
                        assert any(s in failure for s in ('detected rate graph is disconnected', 'baseline rate estimates inconsistent'))
                assert prior.fingerprint(training) == before
                assert (profile is not None) == (row['profile'] is not None)
                assert failure == row.get('reason')
                record = {'trial': trial, 'original_state': row['state'], 'original_reason': row.get('reason'),
                          'accepted_baseline_mask': [r['accepted'] for r in records],
                          'station_candidate_before_chisq': None, 'reduced_chisq': None,
                          'production_profile_accepted': profile is not None}
                if solution is None:
                    assert not captures and profile is None
                    record['state'] = 'graph_disconnected_candidate_null'; rows.append(record); continue
                assert len(captures) == 1
                np.testing.assert_allclose(captures[0], solution, rtol=RTOL, atol=ATOL)
                estimates = np.r_[0., captures[0]]; candidate[trial] = estimates
                connected[trial] = True; accepted[trial] = profile is not None; observed_candidates += 1
                if reduced is not None:
                    chisq[trial] = reduced
                    # actual側と独立逆式のχ²を別の残差表現で照合する。
                    actual_reduced = float(np.sum((lhs @ captures[0]-rhs)**2)/(len(lhs)-2))
                    np.testing.assert_allclose(actual_reduced, reduced, rtol=RTOL, atol=ATOL)
                assert (reduced is None or reduced <= 3.) == (profile is not None)
                if profile is not None:
                    np.testing.assert_allclose(profile['station_rates_hz'], row['profile']['station_rates_hz'], rtol=RTOL, atol=ATOL)
                    assert profile['baseline_estimates'] == records
                    if reduced is None:
                        assert profile['reduced_rate_chisq'] is None
                    else:
                        np.testing.assert_allclose(profile['reduced_rate_chisq'], reduced, rtol=RTOL, atol=ATOL)
                delta = estimates[prior.PAIRS[:, 0]]-estimates[prior.PAIRS[:, 1]]-prior.TRUE_BASELINE_RATES
                expected = abs(np.mean(np.exp(-2j*np.pi*delta[:, None]*prior.TAU), axis=1))**2
                formula = (np.sinc(prior.CELLS*delta*prior.CADENCE)/np.sinc(delta*prior.CADENCE))**2
                np.testing.assert_allclose(expected, formula, rtol=RTOL, atol=ATOL); prediction[trial] = expected
                for role, data in [('train', training), ('evaluation', evaluation)]:
                    baseline = estimates[prior.PAIRS[:, 0]]-estimates[prior.PAIRS[:, 1]]
                    z = data['visibilities'][:, 0]*np.exp(-2j*np.pi*prior.TAU[:, None]*baseline)
                    result = time_power_moments(z, np.full(z.shape, 2*sigma**2))
                    direct = abs(z.mean(axis=0))**2-2*sigma**2/prior.CELLS
                    np.testing.assert_allclose(result['mean_power'], direct, rtol=RTOL, atol=ATOL)
                    powers[role][trial] = result['mean_power']
                    if profile is not None:
                        np.testing.assert_allclose(result['mean_power'], original[f'condition{condition}_{role}_estimated_mean_power'][success_index], rtol=RTOL, atol=ATOL)
                        successful_archive_powers += 1
                if profile is not None:
                    assert original[f'condition{condition}_accepted_trial_indices'][success_index] == trial
                    success_index += 1
                record.update(state='accepted' if profile is not None else 'chisq_rejected_candidate_only',
                              station_candidate_before_chisq=estimates.tolist(), reduced_chisq=reduced)
                rows.append(record)
            rejected = connected & ~accepted
            masks = {'connected': connected, 'accepted': accepted, 'chisq_rejected': rejected}
            summaries = {}
            for label, mask in masks.items():
                summaries[label] = {'trial_indices': np.flatnonzero(mask).tolist(),
                    'training_minus_known_eval_prediction': statistics(powers['train'][mask]-prediction[mask]),
                    'evaluation_minus_known_prediction': statistics(powers['evaluation'][mask]-prediction[mask], control=True),
                    'training_minus_evaluation_paired': statistics(powers['train'][mask]-powers['evaluation'][mask])}
            for role, values in powers.items():
                mixture = sum(mask.sum()*values[mask].mean(axis=0) for mask in [accepted, rejected] if mask.any())/connected.sum()
                np.testing.assert_allclose(values[connected].mean(axis=0), mixture, rtol=RTOL, atol=ATOL)
                arrays[f'condition{condition}_{role}_station_candidate_power'] = values
                arrays[f'condition{condition}_{role}_power_minus_prediction'] = values-prediction
            arrays.update({f'condition{condition}_station_candidate_rates_hz': candidate,
                           f'condition{condition}_reduced_chisq_or_nan_no_degrees': chisq,
                           f'condition{condition}_known_eval_power_prediction': prediction,
                           **{f'condition{condition}_{label}_mask': mask for label, mask in masks.items()}})
            groups.append({'condition': condition, 'quadrature_sigma': sigma, 'original_trial_count': 256,
                           'connected_count': int(connected.sum()), 'production_success_count': int(accepted.sum()),
                           'chisq_rejected_count': int(rejected.sum()), 'graph_disconnected_null_count': int((~connected).sum()),
                           'power_negative_counts_train_eval': [int(np.sum(powers[role][connected] < 0)) for role in powers],
                           'power_above_one_counts_train_eval': [int(np.sum(powers[role][connected] > 1)) for role in powers],
                           'groups': summaries, 'all_original_trials': rows})
    summary = {'stage': 163, 'state': 'complete', 'groups': groups, 'original147_trial_pairs_reused': 512,
        'training_fingerprints_verified': fingerprints, 'station_LS_candidates_observed': observed_candidates,
        'original147_successful_power_rows_verified': successful_archive_powers,
        'actual_station_solver_replays': 512, 'new_baseline_nonlinear_fits': 0, 'new_independent_trials': 0,
        'baseline_records_replayed_not_refitted': True, 'actual_LS_result_observed_without_modification': True,
        'default_gate_thresholds_unchanged': {'min_snr': 8., 'min_peak_z': 8., 'max_reduced_chisq': 3.},
        'rejected_candidate_is_production_profile': False, 'disconnected_nulls_replaced_with_zero': False,
        'full_estimation_bias_and_gate_causal_effect_identified': False,
        'MCSE_uses_original147_model_replicates_not_new_trials': True,
        'scope': 'Archived detected baselines fixed; actual station LS and default final chisq gate replayed. Conditional connected-domain candidate accounting only. Graph/search/detection selection remains; rejected candidate is not an accepted production profile. No physical IQ/VDIF/FIR, unknown hardware inference, image likelihood, confidence or causal full-pipeline bias calibration.'}
    (out/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
    np.savez_compressed(out/'arrays.npz', **arrays)
    origins = {n: m.__file__ for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None)}
    (out/'runtime-private.json').write_text(json.dumps({'module_paths': origins, 'wall_s': time.monotonic()-began,
        'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}, indent=2)+'\n')
    assert sum(f.stat().st_size for f in out.iterdir()) < 64*1024**2
    print(json.dumps({'stage': 163, 'state': 'complete', 'observed_station_candidates': observed_candidates,
                     'counts': [[g[k] for k in ['connected_count', 'production_success_count', 'chisq_rejected_count', 'graph_disconnected_null_count']] for g in groups]}))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--archive', required=True)
    parser.add_argument('--output', required=True); args = parser.parse_args(); run(args.archive, args.output)
