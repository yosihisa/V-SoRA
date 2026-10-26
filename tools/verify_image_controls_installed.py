"""導入済みRMLとoracle相関CLIで評価用の画像対照を照合する。"""
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
from vsora_simulator.sky import synthetic_sky
from vsora_simulator.visibility import direct_visibility
from vsora_imaging.closure import form_closures, extract_closures
from vsora_imaging.experiment import compare_relative
from vsora_imaging.assessment import assess_rml_result
from vsora_observation.reference import reference_path


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree(path): return {str(p.relative_to(path)): sha(p) for p in path.rglob('*') if p.is_file()}


def strip(value):
    if isinstance(value, dict): return {k: strip(v) for k, v in value.items() if k not in ('elapsed_s', 'input_sha256')}
    if isinstance(value, list): return [strip(v) for v in value]
    return value


def main():
    p = argparse.ArgumentParser(); p.add_argument('--reference', required=True); p.add_argument('--output', required=True)
    args = p.parse_args(); checkout = Path(__file__).resolve().parents[1]
    assert not Path.cwd().resolve().is_relative_to(checkout) and 'PYTHONPATH' not in os.environ and not (Path.cwd()/'tools/run.py').exists()
    reference = Path(args.reference); source = json.loads((reference/'summary.json').read_text()); assert len(source['cases']) == 9
    out = Path(args.output); out.mkdir(parents=True, exist_ok=False); rows = []; image_count = oracle_count = ideal_count = arrays_count = 0
    for row in source['cases']:
        root = out/row['case']; root.mkdir(); raw = Path(row['raw_directory']); original_profile = Path(row['original_profile'])
        assert row['input_sha256'] == {p.name: sha(p) for p in raw.iterdir() if p.is_file()} and sha(original_profile) == row['original_profile_sha256']
        assert sha(row['base_spectrum']) == row['base_spectrum_sha256'] and sha(row['used_profile']) == row['used_profile_sha256']
        observed = load_spectral(row['base_spectrum']); evaluation = deepcopy(observed['metadata']['config'])
        assert evaluation['source']['model'] == 'unknown'
        evaluation['source'].update(model=row['generating']['model'], total_flux_jy=row['generating']['assumed_flux_jy'])
        truth = synthetic_sky(evaluation); command = None; spectrum = Path(row['spectrum'])
        if row['branch'] == 'truth_rate_control':
            profile = json.loads(Path(row['used_profile']).read_text())
            assert profile['evaluation_only'] and not profile['estimated_from_data'] and profile['station_rates_hz'] == row['generating']['station_rates_hz']
            assert not {'station_covariance_hz2', 'baseline_estimates', 'reduced_rate_chisq'} & set(profile)
            command = [sys.executable, '-m', 'vsora_correlator', 'correlate-aligned', '--manifest', row['manifest'],
                       '--clock-model', str(raw/'clock.json'), '--output', str(root/'correlation'), '--integrations', '1',
                       '--start-offset-s', '.002', '--rate-profile', row['used_profile']]
            result = subprocess.run(command, capture_output=True, text=True); (root/'correlation.log').write_text(result.stdout+result.stderr)
            assert result.returncode == 0, result.stderr
            spectrum = root/'correlation/shard-00000.npz'; oracle_count += 1
        data = load_spectral(spectrum); expected_data = load_spectral(row['spectrum']); assert set(data) == set(expected_data)
        for key in data:
            if key != 'metadata': np.testing.assert_array_equal(data[key], expected_data[key]); arrays_count += 1
        if row['branch'] == 'ideal_model_observed_snr_control':
            model = direct_visibility(observed['uvw_lambda'], truth, 16.)
            np.testing.assert_array_equal(data['visibilities'], model)
            # sourceの比の二乗とは別に、先にSNRを作ってから重みを再構成する。
            snr = np.abs(observed['visibilities'])*np.sqrt(observed['weights']); expected_w = np.zeros_like(snr)
            valid = observed['weights'] > 0
            expected_w[valid] = (snr[valid]/np.abs(model[valid]))**2
            np.testing.assert_allclose(data['weights'], expected_w, rtol=1e-12, atol=0.)
            a = form_closures(observed['visibilities'], observed['weights'], observed['pairs'], 10.)
            b = form_closures(data['visibilities'], data['weights'], data['pairs'], 10.)
            for key in ('baseline_valid', 'phase_valid', 'logamp_valid'): np.testing.assert_array_equal(a[key], b[key])
            np.testing.assert_allclose(a['baseline_variance'], b['baseline_variance'], rtol=1e-12, atol=0.)
            assert data['metadata']['evaluation_only'] and data['metadata']['visibility_unit'] == 'Jy'
            assert not {'clock_mapping_applied', 'rate_applied_hz', 'diagnostic_power_unit'} & set(data['metadata'])
            ideal_count += 1
        closure = extract_closures(spectrum, root/'closures.npz', min_snr=10.)
        rml = [sys.executable, '-m', 'vsora_imaging.rml', '--input', str(spectrum), '--output', str(root/'rml')]
        for key, value in source['rml_settings'].items(): rml += ['--'+key.replace('_', '-'), str(value)]
        result = subprocess.run(rml, capture_output=True, text=True); (root/'rml.log').write_text(result.stdout+result.stderr)
        failure = summary = metrics = image_sha = None
        if row['science']['rml_failure_code'] is not None:
            assert result.returncode != 0 and 'no high SNR independent closure measurements' in result.stderr and not (root/'rml').exists()
            failure = 'no_high_snr_independent_closures'
        else:
            assert result.returncode == 0, result.stderr
            summary = json.loads((root/'rml/summary.json').read_text()); image = np.load(root/'rml/relative-model.npy')
            original = np.load(reference/row['case']/'rml/relative-model.npy'); np.testing.assert_array_equal(image, original)
            image_sha = sha(root/'rml/relative-model.npy'); metrics, _, _, _ = compare_relative(truth, image, 16.); image_count += 1
            before = tree(root/'rml'); repeat = subprocess.run(rml, capture_output=True, text=True)
            assert repeat.returncode != 0 and 'FileExistsError' in repeat.stderr and tree(root/'rml') == before
        arrays = {k: {'dtype': v.dtype.str, 'shape': list(v.shape), 'sha256': hashlib.sha256(v.tobytes(order='C')).hexdigest()}
                  for k, v in data.items() if k != 'metadata'}
        science = {'correlation_arrays': arrays, 'closures': closure, 'rml_failure_code': failure, 'rml_summary': strip(summary),
                   'assessment': assess_rml_result(summary, processing_state='complete' if summary is not None else 'incomplete', reference_metrics=metrics),
                   'reference_metrics': metrics, 'image_npy_sha256': image_sha,
                   'observed_snr_masks_and_approx_variance_preserved': True if row['branch'] == 'ideal_model_observed_snr_control' else None}
        assert science == row['science']; (root/'science.json').write_text(json.dumps(science, indent=2, allow_nan=False)+'\n')
        if command:
            before = tree(root/'correlation'); repeat = subprocess.run(command, capture_output=True, text=True)
            assert repeat.returncode != 0 and 'FileExistsError' in repeat.stderr and tree(root/'correlation') == before
        assert row['input_sha256'] == {p.name: sha(p) for p in raw.iterdir() if p.is_file()} and sha(original_profile) == row['original_profile_sha256']
        rows.append({'case': row['case'], 'all_scientific_json_identical': True, 'truth_information_used': row['truth_information_used']}); print(json.dumps(rows[-1]), flush=True)
    modules = sorted(n for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None))
    assert all(Path(sys.modules[n].__file__).is_relative_to(Path(sys.prefix)) for n in modules) and reference_path().is_relative_to(Path(sys.prefix))
    record = {'state': 'complete', 'cases': rows, 'actual_native_oracle_correlations': oracle_count, 'actual_native_rml_attempts': 9,
              'compared_numerical_arrays': arrays_count, 'compared_image_arrays': image_count,
              'ideal_models_independently_reconstructed_and_snr_variance_masks_verified': ideal_count,
              'all_scientific_json_and_full_metrics_identical': True, 'all_input_original_profile_and_base_array_sha_unchanged': True,
              'no_overwrite_and_bytes_preserved': True, 'evaluation_control_labels_verified': True,
              'outside_checkout': True, 'runner_absent': True, 'pythonpath_absent': True,
              'project_modules': modules, 'all_project_modules_in_prefix': True, 'reference_asset_in_prefix': True,
              'scope': 'Three new truth-rate correlations, nine native RML attempts; estimated/ideal inputs are frozen source files verified by SHA and independent ideal-model reconstruction. Truth controls are not unknown-observation solutions. Timing and input archive provenance digests excluded from science equality.'}
    (out/'verification.json').write_text(json.dumps(record, indent=2)+'\n'); print(json.dumps(record))


if __name__ == '__main__': main()
