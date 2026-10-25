"""導入済み相関/RML CLIで最終積分9条件の全配列・評価を照合する。"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
from vsora_formats.spectral import load_spectral
from vsora_imaging.closure import extract_closures
from vsora_imaging.assessment import assess_rml_result
from vsora_imaging.experiment import compare_relative
from vsora_imaging.rml import ClosureObjective
from vsora_simulator.sky import synthetic_sky
from vsora_observation.reference import reference_path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree(path):
    return {str(p.relative_to(path)): sha(p) for p in path.rglob('*') if p.is_file()}


def strip(value):
    if isinstance(value, dict): return {k: strip(v) for k, v in value.items() if k not in ('elapsed_s', 'input_sha256')}
    if isinstance(value, list): return [strip(v) for v in value]
    return value


def main():
    p = argparse.ArgumentParser(); p.add_argument('--reference', required=True); p.add_argument('--truth', required=True)
    p.add_argument('--prior-reference', required=True); p.add_argument('--output', required=True)
    args = p.parse_args(); checkout = Path(__file__).resolve().parents[1]
    assert not Path.cwd().resolve().is_relative_to(checkout) and 'PYTHONPATH' not in os.environ and not (Path.cwd()/'tools/run.py').exists()
    reference = Path(args.reference); source = json.loads((reference/'summary.json').read_text()); assert len(source['cases']) == 9
    output = Path(args.output); output.mkdir(parents=True, exist_ok=False); rows = []; arrays_count = images = 0; prior_verified = False
    prior_reference = json.loads(Path(args.prior_reference).read_text())
    for row in source['cases']:
        raw = Path(row['raw_directory']); profile = Path(row['profile'])
        assert {p.name: sha(p) for p in raw.iterdir() if p.is_file()} == row['input_sha256'] and sha(profile) == row['profile_sha256']
        root = output/row['case']; root.mkdir()
        command = [sys.executable, '-m', 'vsora_correlator', 'correlate-aligned', '--manifest', row['manifest'],
                   '--clock-model', str(raw/'clock.json'), '--output', str(root/'correlation'), '--integrations', '1',
                   '--start-offset-s', '.002', '--rate-profile', str(profile)]
        completed = subprocess.run(command, capture_output=True, text=True); (root/'correlation.log').write_text(completed.stdout+completed.stderr)
        assert completed.returncode == 0, completed.stderr
        spectrum = root/'correlation/shard-00000.npz'; data = load_spectral(spectrum)
        old = load_spectral(reference/row['case_directory']/'correlation/shard-00000.npz'); assert set(data) == set(old)
        for key in data:
            if key != 'metadata': np.testing.assert_array_equal(data[key], old[key]); arrays_count += 1
        array_identity = {k: {'dtype': v.dtype.str, 'shape': list(v.shape), 'sha256': hashlib.sha256(v.tobytes(order='C')).hexdigest()}
                          for k, v in data.items() if k != 'metadata'}
        closure = extract_closures(spectrum, root/'closures.npz', min_snr=10.)
        rml = [sys.executable, '-m', 'vsora_imaging.rml', '--input', str(spectrum), '--output', str(root/'rml')]
        for key, value in source['rml_settings'].items(): rml += ['--'+key.replace('_', '-'), str(value)]
        fitted = subprocess.run(rml, capture_output=True, text=True); (root/'rml.log').write_text(fitted.stdout+fitted.stderr)
        summary = metrics = image_sha = failure = None
        if row['science']['rml_failure_code'] is not None:
            assert fitted.returncode != 0 and 'no high SNR independent closure measurements' in fitted.stderr and not (root/'rml').exists()
            failure = 'no_high_snr_independent_closures'
        else:
            assert fitted.returncode == 0, fitted.stderr
            summary = json.loads((root/'rml/summary.json').read_text())
            recovered = np.load(root/'rml/relative-model.npy'); original = np.load(reference/row['case_directory']/'rml/relative-model.npy')
            np.testing.assert_array_equal(recovered, original); image_sha = sha(root/'rml/relative-model.npy'); images += 1
            observed = json.loads((raw/'observation.json').read_text()); assert observed['source']['model'] == 'unknown'
            evaluation = deepcopy(observed); evaluation['source'].update(model=row['generating']['model'], total_flux_jy=row['generating']['assumed_flux_jy'])
            truth = synthetic_sky(evaluation); np.testing.assert_array_equal(truth, np.load(args.truth))
            metrics, _, _, _ = compare_relative(truth, recovered, 16.)
            if not prior_verified:
                settings = {k: v for k, v in source['rml_settings'].items() if k not in ('starts', 'max_iterations', 'seed')}
                objective = ClosureObjective(data['uvw_lambda'], data['visibilities'], data['weights'], data['pairs'], **settings)
                prior = objective.prior.reshape(32, 32)
                np.testing.assert_array_equal(prior, np.load(Path(args.prior_reference).with_suffix('.npy')))
                prior_metrics, _, _, _ = compare_relative(truth, prior, 16.)
                assert prior_metrics == prior_reference['metrics']; prior_verified = True
            before = tree(root/'rml'); refused = subprocess.run(rml, capture_output=True, text=True)
            assert refused.returncode != 0 and 'FileExistsError' in refused.stderr and tree(root/'rml') == before
        assessment = assess_rml_result(summary, processing_state='complete' if summary is not None else 'incomplete', reference_metrics=metrics)
        science = {'correlation_arrays': array_identity, 'closures': closure, 'rml_failure_code': failure,
                   'rml_summary': strip(summary), 'assessment': assessment, 'reference_metrics': metrics, 'recovered_npy_sha256': image_sha}
        assert science == row['science']
        before = tree(root/'correlation'); refused = subprocess.run(command, capture_output=True, text=True)
        assert refused.returncode != 0 and 'FileExistsError' in refused.stderr and tree(root/'correlation') == before
        assert {p.name: sha(p) for p in raw.iterdir() if p.is_file()} == row['input_sha256'] and sha(profile) == row['profile_sha256']
        (root/'science.json').write_text(json.dumps(science, indent=2, allow_nan=False)+'\n')
        rows.append({'case': row['case'], 'all_scientific_json_identical': True, 'rml_failure_code': failure})
        print(json.dumps(rows[-1]), flush=True)
    modules = sorted(n for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None))
    assert all(Path(sys.modules[n].__file__).is_relative_to(Path(sys.prefix)) for n in modules)
    assert reference_path().is_relative_to(Path(sys.prefix)) and prior_verified
    record = {'state': 'complete', 'cases': rows, 'actual_native_correlation_runs': 9, 'actual_native_rml_attempts': 9,
              'correlation_arrays_compared': arrays_count, 'recovered_image_arrays_identical': images,
              'all_scientific_json_and_reference_metrics_identical': True, 'fixed_prior_array_and_metrics_verified': True,
              'all_input_and_profile_sha_unchanged': True, 'non_overwrite_and_bytes_preserved': True,
              'outside_checkout': True, 'runner_absent': True, 'pythonpath_absent': True,
              'project_modules': modules, 'all_project_modules_in_prefix': True, 'reference_asset_in_prefix': True,
              'comparison_scope': 'All correlation and image arrays, settings/counts/objective/convergence and full reference metrics; RML elapsed seconds and input archive digests excluded from science equality. Native branches retain their own provenance.'}
    (output/'verification.json').write_text(json.dumps(record, indent=2)+'\n'); print(json.dumps(record))


if __name__ == '__main__': main()
