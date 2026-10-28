"""保存pilotの固定parity分割でrate学習と未使用cellの受動診断を比較する。"""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
from vsora_correlator.rate import estimate_rate_shard, validate_rate_profile
from vsora_correlator.rate_graph import diagnose_rate_graph
from vsora_correlator.time_scatter import diagnose_time_file
from vsora_formats.spectral import load_spectral, save_spectral


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('saved_pilot_enrollment', Path(__file__).with_name('saved_pilot_time_validation.py'))
enrollment = importlib.util.module_from_spec(spec); spec.loader.exec_module(enrollment)
CLI_WRAPPER = '''import json,pathlib,runpy,sys
module=sys.argv[1];destination=pathlib.Path(sys.argv[2]);sys.argv=[module,*sys.argv[3:]]
try:runpy.run_module(module,run_name='__main__',alter_sys=True)
finally:
 origins={n:m.__file__ for n,m in sys.modules.items() if n.startswith('vsora_') and getattr(m,'__file__',None)}
 assert origins and all(pathlib.Path(v).resolve().is_relative_to(pathlib.Path(sys.prefix)) for v in origins.values())
 destination.write_text(json.dumps(origins,indent=2))
'''


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False)+'\n')


def subset(data, indices):
    nt = len(data['times_s'])
    return {k: deepcopy(v) if k == 'metadata' else (v[indices].copy() if v.ndim and v.shape[0] == nt else v.copy())
            for k, v in data.items()}


def interval(data):
    integration = data['integration_s']
    if integration.ndim == 2:
        assert np.allclose(integration, integration[:, :1], rtol=0, atol=1e-12)
        integration = integration[:, 0]
    return float(data['times_s'][0]-integration[0]/2), float(data['times_s'][-1]+integration[-1]/2)


def run(reference, record132, output, mode='source'):
    out = Path(output).resolve(); reference = Path(reference).resolve()
    if out.exists():
        raise FileExistsError('choose a new pilot holdout output')
    if mode == 'installed':
        assert not Path.cwd().resolve().is_relative_to(ROOT)
        assert not (Path.cwd()/'tools/run.py').exists() and 'PYTHONPATH' not in os.environ
    inputs, canonical = enrollment.enroll(reference, Path(record132).resolve())
    out.mkdir(parents=True); rows = []; measurements = []
    cli_count = diagnostic_calls = coverage_refusals = edge_refusals = 0
    def native(module, args, folder, label):
        nonlocal cli_count
        start = time.monotonic()
        result = subprocess.run([sys.executable, '-c', CLI_WRAPPER, module,
                                 str(folder/(label+'-modules-private.json')), *args],
                                capture_output=True, text=True, timeout=180)
        (folder/(label+'.log')).write_text(result.stdout+result.stderr)
        measurements.append({'action': label, 'case': str(folder.relative_to(out)), 'wall_s': time.monotonic()-start})
        cli_count += 1
        return result
    for name, (pilot, old_profile) in canonical.items():
        original = load_spectral(pilot); assert len(original['times_s']) == 750
        for parity in (0, 1):
            folder = out/name/f'train-parity-{parity}'; folder.mkdir(parents=True)
            train = np.arange(parity, 750, 2); full_holdout = np.arange(1-parity, 750, 2)
            held = full_holdout[:-1] if parity == 0 else full_holdout[1:]
            assert len(train) == 375 and len(held) == 374 and not set(train).intersection(held)
            indices = {'training': train, 'heldout': held, 'untrimmed_heldout': full_holdout}
            partitions = {}; derived = {}
            for role, positions in indices.items():
                path = folder/(role+'.npz'); data = subset(original, positions)
                save_spectral(path, {k: v for k, v in data.items() if k != 'metadata'}, data['metadata'])
                reread = load_spectral(path)
                for key, value in data.items():
                    if isinstance(value, np.ndarray):
                        np.testing.assert_array_equal(value, reread[key])
                assert data['metadata'] == reread['metadata']
                partitions[role] = path
                derived[role] = {'original_time_indices': positions.tolist(), 'archive_sha256': sha(path),
                                 'numeric_arrays': enrollment.identity(reread), 'time_interval_s': list(interval(data))}
            profile_path = folder/'rate.json'; profile = None; failure = None; graph = None
            started = time.monotonic()
            if mode == 'installed':
                call = native('vsora_correlator.rate', ['--input', str(partitions['training']), '--output', str(profile_path),
                              '--max-rate-hz', '50.0'], folder, 'estimate-rate')
                if call.returncode == 0:
                    profile = json.loads(profile_path.read_text())
                else:
                    allowed = ['detected rate graph is disconnected', 'baseline rate estimates inconsistent']
                    reason = next((s for s in allowed if s in call.stderr), None)
                    if reason is None:
                        raise RuntimeError('unexpected native rate estimation failure')
                    failure = reason
            else:
                try:
                    profile = estimate_rate_shard(partitions['training'], max_rate_hz=50.)
                except ValueError as exc:
                    allowed = ['detected rate graph is disconnected', 'baseline rate estimates inconsistent']
                    failure = next((s for s in allowed if s in str(exc)), None)
                    if failure is None:
                        raise
                if profile is not None:
                    write_json(profile_path, profile)
                measurements.append({'case': str(folder.relative_to(out)), 'action': 'estimate-rate', 'wall_s': time.monotonic()-started})
            if profile is None:
                assert not profile_path.exists()
                graph = diagnose_rate_graph(load_spectral(partitions['training']), max_rate_hz=50.)
                write_json(folder/'rate-failure.json', {'state': 'not_estimated', 'reason': failure, 'graph': graph})
            else:
                assert profile['input_sha256'] == sha(partitions['training'])
                assert np.isclose(profile['sample_cadence_s'], .008) and np.isclose(profile['temporal_nyquist_hz'], 62.5)
                meta = original['metadata']; station_ids = [s['id'] for s in meta['config']['stations']]
                for role in ('training', 'heldout'):
                    validate_rate_profile(profile, station_ids, meta['time_origin_utc'], *derived[role]['time_interval_s'])
                try:
                    validate_rate_profile(profile, station_ids, meta['time_origin_utc'], *derived['untrimmed_heldout']['time_interval_s'])
                except ValueError as exc:
                    assert 'extrapolation requires explicit permission' in str(exc); coverage_refusals += 1
                else:
                    raise AssertionError('untrimmed edge unexpectedly covered')
            series = []
            for role in ('training', 'heldout'):
                values = {}
                for rotation in ('unrotated', 'training_rate'):
                    if rotation == 'training_rate' and profile is None:
                        series.append({'role': role, 'rotation': rotation, 'state': 'blocked_by_rate_failure', 'diagnostic': None})
                        continue
                    path = folder/(role+'-'+rotation+'.json'); supplied = profile_path if rotation == 'training_rate' else None
                    began = time.monotonic()
                    if mode == 'installed':
                        args = ['--input', str(partitions[role]), '--output', str(path), '--channel-index', '4']
                        if supplied is not None:
                            args += ['--rate-profile', str(supplied)]
                        call = native('vsora_correlator.time_scatter', args, folder, role+'-'+rotation)
                        if call.returncode:
                            raise RuntimeError('unexpected native time diagnostic failure')
                        diagnostic = json.loads(path.read_text())
                    else:
                        diagnostic = diagnose_time_file(partitions[role], path, 4, supplied)
                        measurements.append({'case': str(folder.relative_to(out)), 'action': role+'-'+rotation, 'wall_s': time.monotonic()-began})
                    diagnostic_calls += 1
                    assert diagnostic['input_sha256'] == sha(partitions[role])
                    assert diagnostic['rate_profile_sha256'] == (sha(profile_path) if supplied is not None else None)
                    assert not diagnostic['hardware_coherence_measured'] and not diagnostic['rate_profile_fit_dependence_calibrated']
                    values[rotation] = diagnostic
                    series.append({'role': role, 'rotation': rotation, 'state': diagnostic['state'], 'diagnostic': diagnostic})
                if profile is not None and values['unrotated']['state'] == 'conditional_estimate':
                    assert values['training_rate']['state'] == 'conditional_estimate'
                    x = values['unrotated']['baselines']; y = values['training_rate']['baselines']
                    scale = max(abs(v['raw_time_power']) for v in x)
                    for key in ('noise_subtracted_time_power', 'estimated_cell_noise_variance_mean', 'estimated_noise_variance_of_mean'):
                        np.testing.assert_allclose([v[key] for v in x], [v[key] for v in y], rtol=2e-12, atol=1e-11*scale)
            if name == 'high_a' and parity == 0 and profile is not None:
                rejected = folder/'untrimmed-refused.json'
                if mode == 'installed':
                    call = native('vsora_correlator.time_scatter', ['--input', str(partitions['untrimmed_heldout']),
                                  '--output', str(rejected), '--channel-index', '4', '--rate-profile', str(profile_path)], folder, 'untrimmed-refused')
                    assert call.returncode != 0 and 'extrapolation requires explicit permission' in call.stderr
                else:
                    try:
                        diagnose_time_file(partitions['untrimmed_heldout'], rejected, 4, profile_path)
                    except ValueError as exc:
                        assert 'extrapolation requires explicit permission' in str(exc)
                    else:
                        raise AssertionError('untrimmed time-file diagnostic was accepted')
                assert not rejected.exists(); edge_refusals += 1
            rows.append({'raw_case': name, 'training_parity': parity, 'source_pilot_sha256': sha(pilot),
                'original_full_profile_sha256_identity_only': sha(old_profile), 'derived': derived,
                'rate_state': 'estimated' if profile is not None else 'not_estimated', 'rate_profile': profile,
                'failure_reason': failure, 'failure_graph': graph, 'series': series})
            print(json.dumps({'raw_case': name, 'parity': parity, 'rate_estimated': profile is not None,
                              'actual_diagnostic_calls': diagnostic_calls}), flush=True)
    assert all(sha(reference/n) == digest for n, digest in inputs.items())
    result = {'stage': 143, 'state': 'complete', 'folds': rows, 'planned_series': 32,
        'actual_diagnostic_calls': diagnostic_calls, 'rate_estimation_attempts': 8,
        'successful_rate_profiles': sum(v['rate_state'] == 'estimated' for v in rows),
        'coverage_validator_refusals': coverage_refusals, 'actual_time_file_edge_refusals': edge_refusals,
        'input_pilot_and_profile_sha256': inputs, 'record132_sha256': sha(record132),
        'training_and_heldout_same_raw': True, 'independent_raw_or_coverage_claimed': False,
        'fit_dependence_calibrated': False, 'truth_lo_sky_gain_used': False, 'production_rml_changed': False,
        'scope': 'Fixed parity heldout cells, one endpoint excluded a priori for existing profile coverage; same raw, clocks/gains and periodic/filter dependencies. DC-only conditional power comparison, no independent-real-data calibration or image improvement.'}
    write_json(out/'summary.json', result)
    write_json(out/'measurements.json', {'mode': mode, 'operations': measurements, 'actual_native_cli_calls': cli_count})
    origins = {n: m.__file__ for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None)}
    write_json(out/'runtime-private.json', {'module_paths': origins})
    assert sum(p.stat().st_size for p in out.rglob('*') if p.is_file()) < 128*1024**2
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--reference', required=True)
    parser.add_argument('--record132', required=True); parser.add_argument('--output', required=True)
    parser.add_argument('--mode', choices=['source', 'installed'], default='source')
    run(**vars(parser.parse_args()))
