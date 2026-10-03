"""Installed diagnostics and physical linear pipeline outside checkout."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np


def run(source_run, output):
    from vsora_correlator import rate_uncertainty
    from vsora_formats.spectral import load_spectral
    assert Path(rate_uncertainty.__file__).is_relative_to(Path(sys.prefix))
    source = Path(source_run).resolve(); out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy(); env.pop('PYTHONPATH', None)
    env.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-uncertainty-installed-') as cwd:
        command = [str(Path(sys.prefix)/'bin/vsora-rate-uncertainty'),
            '--profile', str(source/'strong/rate-linear.json'), '--start-offset-s', '.002',
            '--integration-s', '3', '--output', str(out/'diagnostic.json')]
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
        (out/'diagnostic.log').write_text(result.stdout+result.stderr)
        assert result.returncode == 0
        diagnostic = json.loads((out/'diagnostic.json').read_text())
        original = json.loads((source/'strong/rate-linear.json').read_text())
        expected = rate_uncertainty.linear_rate_uncertainty(original, original['station_ids'],
            original['time_origin_utc'], .002, 3.002)
        assert all(diagnostic[k] == v for k, v in expected.items())
        repeat = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
        assert repeat.returncode != 0 and 'FileExistsError' in repeat.stderr
        invalid = command.copy(); invalid[invalid.index('--integration-s')+1] = '3.1'
        invalid[-1] = str(out/'invalid.json')
        rejection = subprocess.run(invalid, cwd=cwd, env=env, capture_output=True, text=True)
        assert rejection.returncode != 0 and not (out/'invalid.json').exists()
        archive = source.parent/'stage035-drift/strong'
        result = subprocess.run([str(Path(sys.prefix)/'bin/vsora-closure-session'),
            '--manifest', str(archive/'manifest.json'), '--clock-model', str(archive/'clock.json'),
            '--pilot-integrations', '1500', '--integration-s', '3', '--rate-model', 'linear',
            '--correlation-only', '--output', str(out/'pipeline')], cwd=cwd, env=env, capture_output=True, text=True)
        (out/'pipeline.log').write_text(result.stdout+result.stderr)
        assert result.returncode == 0
        summary = json.loads((out/'pipeline/summary.json').read_text())
        assert summary['rate_estimate']['integration_uncertainty'] == expected
        a = load_spectral(source/'strong/correlation/shard-00000.npz')
        b = load_spectral(out/'pipeline/correlation/shard-00000.npz'); differences = {}
        for key, value in a.items():
            if isinstance(value, np.ndarray):
                np.testing.assert_array_equal(value, b[key])
                if np.issubdtype(value.dtype, np.inexact): differences[key] = float(abs(value-b[key]).max())
    record = {'installed_imports': True, 'entrypoints_outside_checkout': True,
        'diagnostic': diagnostic, 'overwrite_rejected': True, 'invalid_window_rejected': True,
        'physical_pipeline_state': summary['state'], 'maximum_absolute_source_array_differences': differences,
        'scope': 'Previously generated point-source VDIF; conditional uncertainty diagnostic, unchanged numerical correlation. No hardware coherence measurement or Cas A image validation.'}
    (out/'summary.json').write_text(json.dumps(record, indent=2)+'\n'); return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--source-run', required=True); parser.add_argument('--output', required=True)
    print(json.dumps(run(**vars(parser.parse_args())), indent=2))
