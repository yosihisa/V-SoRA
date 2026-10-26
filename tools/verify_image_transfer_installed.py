"""runnerのないcheckout外で87候補と共通マスクを独立に照合する。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
from vsora_formats.spectral import load_spectral
from vsora_imaging.objective_evaluation import evaluate_closure_image


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    checkout = Path(__file__).resolve().parents[1]
    assert not Path.cwd().resolve().is_relative_to(checkout) and 'PYTHONPATH' not in os.environ
    assert not (Path.cwd()/'tools/run.py').exists()
    source = json.loads((Path(args.reference)/'summary.json').read_text())
    assert source['evaluation_count'] == 87 and len(source['common_mask_pairs']) == 27
    out = Path(args.output); out.mkdir(parents=True, exist_ok=False)
    checked = []; unavailable = []

    def check(row):
        data = load_spectral(row['spectrum']); image = np.load(row['image'], allow_pickle=False)
        expected = row['evaluation']
        assert sha(row['spectrum']) == expected['input_sha256'] and sha(row['image']) == expected['candidate_sha256']
        try:
            result = evaluate_closure_image(data['uvw_lambda'], data['visibilities'], data['weights'], data['pairs'], image, **row['settings'])
        except ValueError as error:
            assert expected['state'] == 'not_evaluable' and expected['reason'] == str(error)
            unavailable.append(row['id']); return
        result.update(input_sha256=sha(row['spectrum']), candidate_sha256=sha(row['image']))
        assert result == expected
        target = out/(row['id']+'.json')
        command = [sys.executable, '-m', 'vsora_imaging.objective_evaluation', '--input', row['spectrum'],
                   '--image', row['image'], '--output', str(target)]
        for key, value in row['settings'].items(): command += ['--'+key.replace('_', '-'), str(value)]
        actual = subprocess.run(command, capture_output=True, text=True, check=True)
        assert json.loads(actual.stdout) == json.loads(target.read_text()) == expected
        before = target.read_bytes(); repeat = subprocess.run(command, capture_output=True, text=True)
        assert repeat.returncode != 0 and 'FileExistsError' in repeat.stderr and target.read_bytes() == before
        assert sha(row['spectrum']) == expected['input_sha256'] and sha(row['image']) == expected['candidate_sha256']
        checked.append(row['id'])

    for row in source['full_evaluations']: check(row)
    for pair in source['common_mask_pairs']:
        training = load_spectral(pair['training_spectrum']); evaluation = load_spectral(pair['evaluation_spectrum'])
        assert sha(pair['training_spectrum']) == pair['training_input_sha256']
        assert sha(pair['evaluation_spectrum']) == pair['evaluation_input_sha256']
        threshold = pair['candidate']['settings']['min_snr']
        keep = np.abs(training['visibilities'])*np.sqrt(training['weights']) >= threshold
        weights = evaluation['weights'].copy(); weights[~keep] = 0
        masked = load_spectral(pair['candidate']['spectrum'])
        np.testing.assert_array_equal(masked['weights'], weights)
        for name in ('visibilities', 'pairs', 'times_s', 'frequencies_hz', 'uvw_lambda'):
            np.testing.assert_array_equal(masked[name], evaluation[name])
        assert masked['metadata']['evaluation_only'] is True
        assert set(masked['metadata']) <= {'config', 'visibility_unit', 'time_origin_utc', 'evaluation_only', 'mask_policy', 'min_snr', 'training_sha256', 'evaluation_sha256'}
        assert masked['metadata']['training_sha256'] == pair['training_input_sha256']
        assert masked['metadata']['evaluation_sha256'] == pair['evaluation_input_sha256']
        selected = np.abs(evaluation['visibilities'])*np.sqrt(evaluation['weights']) >= threshold
        assert pair['intersection_selected_baseline_cells'] == int((keep & selected).sum())
        assert pair['training_selected_baseline_cells'] == int(keep.sum())
        assert pair['evaluation_selected_baseline_cells'] == int(selected.sum())
        check(pair['candidate']); check(pair['truth'])
    modules = sorted(n for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None))
    assert all(Path(sys.modules[n].__file__).is_relative_to(Path(sys.prefix)) for n in modules)
    assert len(checked) + len(unavailable) == 87
    record = {'state': 'complete', 'checked_api_and_native_cli': len(checked), 'unavailable': unavailable,
              'all_science_json_identical': True, 'independently_checked_common_masks': 27,
              'no_overwrite_and_input_sha_preserved': True, 'outside_checkout': True,
              'runner_absent': True, 'pythonpath_absent': True, 'project_modules': modules,
              'all_project_modules_in_prefix': True, 'optimizer_executed': False}
    (out/'verification.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record))


if __name__ == '__main__': main()
