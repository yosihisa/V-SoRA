"""同じ保存pilotのprefixで、LO検出基線と失敗を比較する。"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np
from vsora_correlator.rate import estimate_station_rates
from vsora_correlator.rate_graph import diagnose_rate_graph
from vsora_formats.spectral import load_spectral, save_spectral


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def prefix(data, count):
    result = {k: data[k][:count].copy() for k in ('visibilities', 'weights', 'times_s', 'uvw_lambda', 'integration_s')}
    result.update(pairs=data['pairs'].copy(), frequencies_hz=data['frequencies_hz'].copy())
    return result


def estimator_contract(data, previous):
    try:
        expected = previous(data)
    except ValueError as old_error:
        try: estimate_station_rates(data)
        except ValueError as new_error:
            assert str(old_error) == str(new_error)
            return {'state': 'rejected', 'exception_type': 'ValueError', 'reason': str(new_error)}
        raise AssertionError('previously rejected input was unexpectedly accepted')
    result = estimate_station_rates(data); assert result == expected
    return {'state': 'estimated', 'all_previous_result_fields_identical': True, 'result': result}


def run(reference, previous_rate_module, output):
    reference = Path(reference); output = Path(output); output.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('rate_previous_validation', previous_rate_module)
    previous = importlib.util.module_from_spec(spec); spec.loader.exec_module(previous)
    rows = []; summary = json.loads((reference/'summary.json').read_text())
    for sefd in (1000, 10000):
        parent = reference/f'sefd-{sefd}'
        pipeline = parent/'integration-0.3'/('pipeline' if sefd == 1000 else 'pipeline.partial')
        source = pipeline/'pilot/shard-00000.npz'; before = sha(source); data = load_spectral(source)
        generating = next(row['generating'] for row in summary['rows'] if row['assumed_sefd_jy'] == sefd)
        rates = np.asarray(generating['station_rates_hz'])
        assert len(data['times_s']) == 250
        for index, count in enumerate((75, 125, 250)):
            case = f'sefd{sefd}_pilot{count}'; case_root = output/case; case_root.mkdir()
            subset = prefix(data, count); before_arrays = {k: v.copy() for k, v in subset.items()}
            diagnostic = diagnose_rate_graph(subset)
            contract = estimator_contract(subset, previous.estimate_station_rates)
            record_errors = []
            for record in diagnostic['baseline_estimates']:
                if 'rate_hz' in record:
                    i, j = record['pair']
                    record_errors.append({'pair': [i, j], 'accepted': record['accepted'],
                                          'absolute_rate_error_hz': float(abs(record['rate_hz'] - (rates[i] - rates[j])))})
            controls = []
            for repeat in range(16):
                seed = 111000 + (0 if sefd == 1000 else 1000) + index*16 + repeat
                rng = np.random.default_rng(seed); noise = dict(subset)
                scale = np.zeros_like(subset['weights']); np.divide(1., np.sqrt(subset['weights']), out=scale, where=subset['weights'] > 0)
                noise['visibilities'] = scale*(rng.normal(size=scale.shape) + 1j*rng.normal(size=scale.shape))
                control = diagnose_rate_graph(noise)
                old_control = estimator_contract(noise, previous.estimate_station_rates)
                controls.append({'repeat': repeat, 'seed': seed, 'diagnostic': control, 'estimator_contract': old_control})
            for k in subset: np.testing.assert_array_equal(subset[k], before_arrays[k])
            save_spectral(case_root/'pilot-prefix.npz', subset, data['metadata'])
            row = {'case': case, 'assumed_sefd_jy': sefd, 'source_stage': 109, 'source_pilot_sha256': before,
                   'prefix_npz_sha256': sha(case_root/'pilot-prefix.npz'), 'prefix_integrations': count,
                   'diagnostic': diagnostic, 'estimator_contract': contract, 'evaluated_baseline_rate_errors': record_errors,
                   'independent_baseline_gaussian_noise_controls': controls,
                   'truth_used_by_diagnostic_or_estimator': False}
            (case_root/'result.json').write_text(json.dumps(row, indent=2, allow_nan=False)+'\n'); rows.append(row)
            assert sha(source) == before
            print(json.dumps({'case': case, 'state': diagnostic['state'], 'components': diagnostic['components'],
                              'accepted_baselines': diagnostic['accepted_baselines'], 'estimator_state': contract['state']}), flush=True)
    result = {'type': 'same_pilot_prefix_rate_graph_validation', 'cases': rows,
              'previous_rate_module_sha256': sha(previous_rate_module),
              'all_previous_estimator_results_and_exceptions_identical': True, 'fixed_null_controls': 96,
              'thresholds': {'min_coherent_snr': 8., 'min_noise_peak_z': 8., 'max_baseline_rate_hz': 100.},
              'limits': 'Nested prefixes of two fixed VDIF pilots, not independent observation repetitions. Noise controls assume independent real/imaginary baseline/channel/time errors with supplied quadrature weights; actual FFT/source noise is not calibrated. No lowered thresholds, new long VDIF, corrected correlation or images. Truth used only for post-hoc rate errors.'}
    (output/'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--reference', required=True)
    p.add_argument('--previous-rate-module', required=True); p.add_argument('--output', required=True)
    a = p.parse_args(); run(a.reference, a.previous_rate_module, a.output)
