"""checkout外から既存の導入CLI/APIで8原本と3画像を再処理する。"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
from vsora_formats.spectral import load_spectral, save_spectral
from vsora_correlator.rate_graph import diagnose_rate_graph
from vsora_correlator import aligned, closure_pipeline
from vsora_imaging.synthesis import merge_spectral
from vsora_imaging.rml import image_closure, ClosureObjective
from vsora_imaging.objective_evaluation import evaluate_closure_image
from vsora_imaging.experiment import compare_relative
from vsora_imaging.assessment import assess_rml_result
from vsora_imaging.closure import form_closures
from vsora_simulator.visibility import direct_visibility


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(data):
    return {k: {'dtype': v.dtype.str, 'shape': list(v.shape), 'sha256': hashlib.sha256(v.tobytes(order='C')).hexdigest()}
            for k, v in data.items() if k != 'metadata'}


def projection(path):
    data = load_spectral(path)
    keys = ('config', 'visibility_unit', 'clock_mapping_applied', 'phase_center_corrected', 'time_origin_utc',
            'rate_applied_hz', 'rate_applied_reference_s', 'rate_applied_slopes_hz_per_s', 'rate_profile_type')
    return {'arrays': identity(data), 'metadata': {k: data['metadata'][k] for k in keys}}


def stable(value):
    if isinstance(value, dict): return {k: stable(v) for k, v in value.items() if k not in ('elapsed_s', 'input_sha256')}
    if isinstance(value, list): return [stable(v) for v in value]
    return value


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--reference', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); checkout = Path(__file__).resolve().parents[1]
    assert not Path.cwd().resolve().is_relative_to(checkout) and 'PYTHONPATH' not in os.environ and not (Path.cwd()/'tools/run.py').exists()
    source_root = Path(args.reference); source = json.loads((source_root/'summary.json').read_text())
    raw_root = Path(source['reference_directory']); out = Path(args.output); out.mkdir(parents=True, exist_ok=False)
    inputs = {'estimated_rate': [], 'truth_rate_control': []}; arrays_checked = 0; cli_calls = 0

    def command(module, options, log):
        result = subprocess.run([sys.executable, '-m', module, *map(str, options)], capture_output=True, text=True)
        log.write_text(result.stdout+result.stderr)
        return result

    for shot in source['shots']:
        index = shot['snapshot']; raw = raw_root/f'shot-{index:02d}/input'; root = out/f'shot-{index:02d}'; root.mkdir()
        run = command('vsora_correlator.closure_pipeline', ['--manifest', raw/'manifest.json', '--clock-model', raw/'clock.json',
                      '--output', root/'estimated', '--pilot-integrations', '750', '--integration-s', '3', '--correlation-only'], root/'estimated-cli.log')
        cli_calls += 1
        pipeline = root/('estimated' if run.returncode == 0 else 'estimated.partial')
        summary = json.loads((pipeline/'pipeline.json').read_text())
        assert (run.returncode == 0) == (shot['estimated_failure'] is None)
        fit = summary.get('rate_estimate')
        scientific = {'state': summary['state'], 'completed_steps': summary['completed_steps'],
                      'graph': diagnose_rate_graph(load_spectral(pipeline/'pilot/shard-00000.npz')),
                      'rate_estimate': None if fit is None else {k:v for k,v in fit.items() if k != 'input_sha256'},
                      'closures': None, 'correlation_arrays': None, 'correlation_scientific_metadata': None}
        if run.returncode == 0:
            spectrum = pipeline/'correlation/shard-00000.npz'; inputs['estimated_rate'].append(spectrum)
            projected = projection(spectrum); scientific.update(correlation_arrays=projected['arrays'], correlation_scientific_metadata=projected['metadata'])
            arrays_checked += len(projected['arrays'])
        assert scientific == shot['estimated_science']
        run = command('vsora_correlator', ['correlate-aligned', '--manifest', source_root/f'shot-{index:02d}/truth-manifest.json',
                      '--clock-model', raw/'clock.json', '--output', root/'truth-correlation', '--integrations', '1',
                      '--start-offset-s', '.002', '--rate-profile', source_root/f'shot-{index:02d}/truth-rate-only.json'], root/'truth-cli.log')
        cli_calls += 1; assert run.returncode == 0, run.stderr
        spectrum = root/'truth-correlation/shard-00000.npz'; inputs['truth_rate_control'].append(spectrum)
        projected = projection(spectrum); assert projected == shot['truth_correlation']; arrays_checked += len(projected['arrays'])
        print(json.dumps({'installed_snapshot': index}), flush=True)
    truth = np.load(source_root/'truth.npy', allow_pickle=False); settings = source['settings']; truth_merge = None
    checked = []
    for branch_row in source['branches']:
        branch = branch_row['branch']; root = out/branch; root.mkdir()
        if branch_row['state'] != 'complete':
            assert branch == 'estimated_rate' and len(inputs[branch]) < 8
            continue
        if branch != 'ideal_model_true_rate_snr_control':
            merge_spectral(inputs[branch], root/'visibility.npz'); data = load_spectral(root/'visibility.npz')
            if branch == 'truth_rate_control': truth_merge = data
        else:
            data = {k: truth_merge[k].copy() for k in ('pairs', 'times_s', 'frequencies_hz', 'uvw_lambda', 'integration_s')}
            values = direct_visibility(truth_merge['uvw_lambda'], truth, 16.)
            valid = truth_merge['weights'] > 0
            ratio = np.zeros_like(truth_merge['weights'], dtype=float)
            np.divide(np.abs(truth_merge['visibilities']), np.abs(values), out=ratio, where=valid)
            weights = truth_merge['weights']*ratio**2
            data.update(visibilities=values, weights=weights)
            metadata = {k:deepcopy(truth_merge['metadata'][k]) for k in ('config', 'time_origin_utc')}
            metadata.update(visibility_unit='Jy', evaluation_only=True, weights_are_artificial_snr_transport=True,
                            control='Ideal sky on aligned supplied uv/time geometry; observed true-rate SNR transported; not radiometric calibration')
            save_spectral(root/'visibility.npz', data, metadata); data = load_spectral(root/'visibility.npz')
            np.testing.assert_allclose(np.abs(values)*np.sqrt(weights), np.abs(truth_merge['visibilities'])*np.sqrt(truth_merge['weights']), rtol=1e-12)
        summary = image_closure(root/'visibility.npz', root/'rml', **settings)
        image = np.load(root/'rml/relative-model.npy', allow_pickle=False)
        metrics, _, _, _ = compare_relative(truth, image, 16.)
        objective = ClosureObjective(data['uvw_lambda'], data['visibilities'], data['weights'], data['pairs'],
                                     **{k:v for k,v in settings.items() if k not in ('starts','max_iterations','seed')})
        candidates = {'truth': truth, 'prior': objective.prior.reshape(32,32), 'fitted': image}
        evaluations = {k:evaluate_closure_image(data['uvw_lambda'], data['visibilities'], data['weights'], data['pairs'], value,
                       **{k:v for k,v in settings.items() if k not in ('pixels','starts','max_iterations','seed')}) for k,value in candidates.items()}
        science = {'input_arrays': identity(data), 'rml_summary': stable(summary), 'reference_metrics': metrics,
                   'assessment': assess_rml_result(summary, reference_metrics=metrics), 'candidate_objectives': evaluations,
                   'image_sha256': sha(root/'rml/relative-model.npy')}
        assert science == branch_row['science']
        np.testing.assert_array_equal(image, np.load(source_root/branch/'rml/relative-model.npy', allow_pickle=False))
        arrays_checked += len(identity(data)); checked.append(branch)
        (root/'science.json').write_text(json.dumps(science, indent=2, allow_nan=False)+'\n')
    assert source['raw_input_sha256_newly_enrolled'] == {str(p.relative_to(raw_root)):sha(p) for p in sorted(raw_root.glob('shot-*/input/*')) if p.is_file()}
    modules = sorted(n for n,m in sys.modules.items() if n.startswith('vsora_') and getattr(m,'__file__',None))
    assert all(Path(sys.modules[n].__file__).is_relative_to(Path(sys.prefix)) for n in modules)
    record = {'state':'complete','actual_installed_raw_cli_calls':cli_calls,'all_scientific_json_and_image_bytes_identical':checked,
              'numerical_arrays_checked':arrays_checked,'input_files_sha_preserved':152,'outside_checkout':True,'runner_absent':True,
              'pythonpath_absent':True,'all_project_modules_in_prefix':True,'project_modules':modules,'source_workflows_not_imported':not any(n.startswith('workflows') for n in sys.modules)}
    (out/'verification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))


if __name__ == '__main__': main()
