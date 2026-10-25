"""導入版graph API/CLIと既存推定器を、checkout外で全条件照合する。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
from vsora_correlator.rate_graph import diagnose_rate_graph
from vsora_correlator.rate import estimate_station_rates
from vsora_formats.spectral import load_spectral


def main():
    p = argparse.ArgumentParser(); p.add_argument('--reference', required=True); p.add_argument('--output', required=True)
    a = p.parse_args(); checkout = Path(__file__).resolve().parents[1]
    assert not Path.cwd().resolve().is_relative_to(checkout) and 'PYTHONPATH' not in os.environ
    assert not (Path.cwd()/'tools/run.py').exists()
    reference = Path(a.reference); source = json.loads((reference/'summary.json').read_text())
    assert len(source['cases']) == 6; output = Path(a.output); output.mkdir(parents=True, exist_ok=False)
    controls = 0
    def check_estimator(data, expected):
        if expected['state'] == 'estimated': assert estimate_station_rates(data) == expected['result']
        else:
            try: estimate_station_rates(data)
            except ValueError as exc: assert str(exc) == expected['reason']
            else: raise AssertionError('expected rejection lost')
    for row in source['cases']:
        path = reference/row['case']/'pilot-prefix.npz'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['prefix_npz_sha256']
        data = load_spectral(path)
        assert diagnose_rate_graph(data) == row['diagnostic']; check_estimator(data, row['estimator_contract'])
        for control in row['independent_baseline_gaussian_noise_controls']:
            rng = np.random.default_rng(control['seed']); scale = np.zeros_like(data['weights'])
            np.divide(1., np.sqrt(data['weights']), out=scale, where=data['weights'] > 0)
            noise = dict(data); noise['visibilities'] = scale*(rng.normal(size=scale.shape) + 1j*rng.normal(size=scale.shape))
            assert diagnose_rate_graph(noise) == control['diagnostic']; check_estimator(noise, control['estimator_contract']); controls += 1
        dest = output/f"{row['case']}.json"
        cmd = [sys.executable, '-m', 'vsora_correlator.rate_graph', '--input', str(path), '--output', str(dest)]
        result = subprocess.run(cmd, capture_output=True, text=True); assert result.returncode == 0, result.stderr
        assert json.loads(dest.read_text()) == json.loads(result.stdout) == row['diagnostic']
        before = dest.read_bytes(); repeat = subprocess.run(cmd, capture_output=True, text=True)
        assert repeat.returncode != 0 and 'FileExistsError' in repeat.stderr and dest.read_bytes() == before
    modules = sorted(n for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None))
    assert all(Path(sys.modules[n].__file__).is_relative_to(Path(sys.prefix)) for n in modules)
    record = {'state': 'complete', 'source_installed_whole_graph_json_identical_cases': 6,
              'all_noise_control_graph_json_identical': controls, 'all_estimator_results_and_exceptions_identical': True,
              'native_cli_cases': 6, 'all_cli_json_identical': True, 'non_overwrite_and_bytes_preserved': True,
              'outside_checkout': True, 'pythonpath_absent': True, 'runner_absent': True,
              'project_modules': modules, 'all_project_modules_in_prefix': True}
    (output/'verification.json').write_text(json.dumps(record, indent=2)+'\n'); print(json.dumps(record))


if __name__ == '__main__': main()
