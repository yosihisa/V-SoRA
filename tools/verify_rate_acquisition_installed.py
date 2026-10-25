"""checkout外の導入済み相関CLIで同じ9条件の全数値を再実行する。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from vsora_formats.spectral import load_spectral
from vsora_correlator.rate_graph import diagnose_rate_graph
from vsora_imaging.closure import extract_closures


def tree(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--reference', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); checkout = Path(__file__).resolve().parents[1]
    assert not Path.cwd().resolve().is_relative_to(checkout) and 'PYTHONPATH' not in os.environ and not (Path.cwd()/'tools/run.py').exists()
    reference = Path(args.reference); source = json.loads((reference/'summary.json').read_text()); assert len(source['cases']) == 9
    output = Path(args.output); output.mkdir(parents=True, exist_ok=False); rows = []; array_count = 0
    for row in source['cases']:
        raw = reference/row['input_directory']
        assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.iterdir() if p.is_file()} == row['input_sha256']
        root = output/row['case']; root.mkdir(); native = root/'pipeline'
        cmd = [sys.executable, '-m', 'vsora_correlator.closure_pipeline', '--manifest', str(raw/'manifest.json'),
               '--clock-model', str(raw/'clock.json'), '--output', str(native), '--pilot-integrations', str(row['pilot_integrations']),
               '--integration-s', '.3', '--correlation-only']
        run = subprocess.run(cmd, capture_output=True, text=True); (root/'cli.log').write_text(run.stdout+run.stderr)
        expected = row['science']
        if expected['state'] == 'complete':
            assert run.returncode == 0, run.stderr
            pipeline = native; summary = json.loads((pipeline/'pipeline.json').read_text())
            closure = extract_closures(pipeline/'correlation/shard-00000.npz', root/'closures.npz', min_snr=10.)
        else:
            assert run.returncode != 0
            reason = 'detected rate graph is disconnected' if row['scientific_failure_code'] == 'rate_graph_disconnected' else 'baseline rate estimates inconsistent'
            assert reason in run.stderr
            pipeline = native.with_name('pipeline.partial'); summary = json.loads((pipeline/'pipeline.json').read_text()); closure = None
        graph = diagnose_rate_graph(load_spectral(pipeline/'pilot/shard-00000.npz'))
        fit = None if summary.get('rate_estimate') is None else {k: v for k, v in summary['rate_estimate'].items() if k != 'input_sha256'}
        arrays = None; metadata = None
        if summary['state'] == 'complete':
            data = load_spectral(pipeline/'correlation/shard-00000.npz')
            arrays = {k: {'dtype': v.dtype.str, 'shape': list(v.shape), 'sha256': hashlib.sha256(v.tobytes(order='C')).hexdigest()}
                      for k, v in data.items() if k != 'metadata'}
            metadata = {k: data['metadata'][k] for k in ('config', 'visibility_unit', 'clock_mapping_applied',
                'phase_center_corrected', 'time_origin_utc', 'rate_applied_hz', 'rate_applied_reference_s',
                'rate_applied_slopes_hz_per_s', 'rate_profile_type')}
            array_count += len(arrays)
            # digestだけでなく、保存された全配列の値をsource原本と直接照合する。
            import numpy as np
            original = load_spectral(reference/row['case_directory']/'pipeline/correlation/shard-00000.npz')
            assert set(data) == set(original)
            for k in data:
                if k != 'metadata': np.testing.assert_array_equal(data[k], original[k])
        science = {'state': summary['state'], 'completed_steps': summary['completed_steps'], 'graph': graph,
                   'rate_estimate': fit, 'closures': closure, 'correlation_arrays': arrays, 'correlation_scientific_metadata': metadata}
        assert science == expected
        (root/'science.json').write_text(json.dumps(science, indent=2, allow_nan=False)+'\n')
        before = tree(pipeline); repeat = subprocess.run(cmd, capture_output=True, text=True)
        assert repeat.returncode != 0 and 'FileExistsError' in repeat.stderr and tree(pipeline) == before
        assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.iterdir() if p.is_file()} == row['input_sha256']
        rows.append({'case': row['case'], 'state': science['state'], 'all_science_json_identical': True})
        print(json.dumps(rows[-1]), flush=True)
    modules = sorted(n for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None))
    assert all(Path(sys.modules[n].__file__).is_relative_to(Path(sys.prefix)) for n in modules)
    record = {'state': 'complete', 'cases': rows, 'actual_native_cli_runs': 9, 'corrected_arrays_compared': array_count,
              'all_array_values_dtype_shape_and_sha_identical': True, 'all_scientific_json_identical': True,
              'non_overwrite_verified_for_all_cases': True, 'all_input_sha_unchanged': True,
              'outside_checkout': True, 'runner_absent': True, 'pythonpath_absent': True,
              'project_modules': modules, 'all_project_modules_in_prefix': True,
              'archive_byte_equality_claimed': False,
              'comparison_scope': 'Every saved numerical correlation array and graph/rate/closure JSON; selected scientific metadata including config, applied rates and epochs. Operational absolute output paths and their archive/profile provenance digests differ and are excluded from science equality; each branch preserves its own hashes.'}
    (output/'verification.json').write_text(json.dumps(record, indent=2)+'\n'); print(json.dumps(record))


if __name__ == '__main__': main()
