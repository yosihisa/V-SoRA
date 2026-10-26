"""checkout外で導入済み候補画像APIとnative CLI全27を照合する。"""
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


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(); p.add_argument('--reference', required=True); p.add_argument('--output', required=True)
    a = p.parse_args(); checkout = Path(__file__).resolve().parents[1]
    assert not Path.cwd().resolve().is_relative_to(checkout) and 'PYTHONPATH' not in os.environ and not (Path.cwd()/'tools/run.py').exists()
    source = json.loads((Path(a.reference)/'summary.json').read_text()); assert source['candidate_count'] == 27
    out = Path(a.output); out.mkdir(parents=True, exist_ok=False); checked = []
    for row in source['candidates']:
        path = Path(row['spectrum']); image = Path(row['image']); expected = row['evaluation']
        assert sha(path) == expected['input_sha256'] and sha(image) == expected['candidate_sha256']
        data = load_spectral(path); candidate = np.load(image, allow_pickle=False)
        result = evaluate_closure_image(data['uvw_lambda'], data['visibilities'], data['weights'], data['pairs'], candidate, **row['settings'])
        result.update(input_sha256=sha(path), candidate_sha256=sha(image)); assert result == expected
        target = out/f"{row['candidate_id']}.json"
        command = [sys.executable, '-m', 'vsora_imaging.objective_evaluation', '--input', str(path), '--image', str(image), '--output', str(target)]
        for key, value in row['settings'].items(): command += ['--'+key.replace('_', '-'), str(value)]
        completed = subprocess.run(command, capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr
        assert json.loads(target.read_text()) == json.loads(completed.stdout) == expected
        before = target.read_bytes(); refused = subprocess.run(command, capture_output=True, text=True)
        assert refused.returncode != 0 and 'FileExistsError' in refused.stderr and target.read_bytes() == before
        assert sha(path) == expected['input_sha256'] and sha(image) == expected['candidate_sha256']
        checked.append(row['candidate_id'])
    modules = sorted(n for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None))
    assert all(Path(sys.modules[n].__file__).is_relative_to(Path(sys.prefix)) for n in modules)
    record = {'state': 'complete', 'all_direct_api_and_native_cli_json_identical': checked,
              'candidate_count': len(checked), 'no_overwrite_and_bytes_preserved': True,
              'all_input_and_candidate_sha_unchanged': True, 'outside_checkout': True,
              'runner_absent': True, 'pythonpath_absent': True, 'project_modules': modules,
              'all_project_modules_in_prefix': True, 'optimizer_run': False}
    (out/'verification.json').write_text(json.dumps(record, indent=2)+'\n'); print(json.dumps(record))


if __name__ == '__main__': main()
