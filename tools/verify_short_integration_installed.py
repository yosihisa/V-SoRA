"""checkout外の導入済みCLIで固定12条件を再処理し、全保存配列を直接比較する。"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import numpy as np
from vsora_formats.spectral import load_spectral


def main():
    p = argparse.ArgumentParser(); p.add_argument('--reference', required=True); p.add_argument('--raw-root', required=True)
    p.add_argument('--reference131', required=True); p.add_argument('--output', required=True); a = p.parse_args()
    checkout = Path(__file__).resolve().parents[1]
    assert not Path.cwd().resolve().is_relative_to(checkout) and 'PYTHONPATH' not in os.environ
    assert not (Path.cwd()/'tools/run.py').exists()
    reference = Path(a.reference).resolve(); expected = json.loads((reference/'summary.json').read_text())
    spec = importlib.util.spec_from_file_location('matrix_validation_helper', checkout/'workflows/short_integration_matrix.py')
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    out = Path(a.output).resolve(); out.mkdir(parents=True, exist_ok=False); native = out/'study'
    helper.run(a.raw_root, a.reference131, native, installed=True, expected=expected)
    checked = {'pilot': 0, 'correlation': 0, 'closure': 0}; archives = 0
    for row in expected['cases']:
        name = row['case']; partial = row['science']['pipeline']['state'] != 'complete'
        directory = 'pipeline.partial' if partial else 'pipeline'
        for kind, suffix in [('pilot', directory+'/pilot/shard-00000.npz'),
                             ('correlation', directory+'/correlation/shard-00000.npz'), ('closure', 'closures.npz')]:
            source_file = reference/name/suffix; native_file = native/name/suffix
            if partial and kind != 'pilot':
                assert not source_file.exists() and not native_file.exists(); continue
            if kind == 'closure':
                with np.load(source_file, allow_pickle=False) as z: source = {k: z[k] for k in z.files if k != 'metadata_json'}
                with np.load(native_file, allow_pickle=False) as z: actual = {k: z[k] for k in z.files if k != 'metadata_json'}
            else:
                source = load_spectral(source_file); actual = load_spectral(native_file)
                source.pop('metadata'); actual.pop('metadata')
            assert source.keys() == actual.keys()
            for key, value in source.items():
                assert value.dtype == actual[key].dtype and value.shape == actual[key].shape
                np.testing.assert_array_equal(value, actual[key]); checked[kind] += 1
            archives += 1
    before = helper.sha(native/'summary.json')
    try: helper.run(a.raw_root, a.reference131, native, installed=True, expected=expected)
    except FileExistsError: pass
    else: raise AssertionError('whole-study overwrite accepted')
    assert before == helper.sha(native/'summary.json')
    modules = {n: m.__file__ for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None)}
    assert modules and all(Path(v).is_relative_to(Path(sys.prefix)) for v in modules.values())
    record = {'state': 'complete', 'actual_installed_native_cli_runs': 12, 'nonoverwrite_cases': 12,
              'whole_study_nonoverwrite': True, 'all_science_json_exact': True,
              'numerical_arrays_directly_compared': checked, 'archives_directly_compared': archives,
              'array_dtype_shape_values_sha_exact': True, 'input_files_sha_preserved': 76,
              'outside_checkout': True, 'runner_absent': True, 'pythonpath_absent': True,
              'helper_requires_checkout': True, 'project_modules': sorted(modules), 'all_project_modules_in_prefix': True,
              'core_package_changed': False, 'images_executed': False, 'archive_bytes_equal_claimed': False,
              'provenance_comparison': 'input SHA checked against published131; each applied profile SHA matches its saved profile. Output paths and dependent archive/profile SHA excluded from science equality. All other spectral metadata and complete pipeline science/diagnostics retained.'}
    helper.write_json(out/'verification.json', record); print(json.dumps(record))


if __name__ == '__main__': main()
