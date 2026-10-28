"""固定VDIFの末尾不足・非上書き・別出力での再実行を有限workerで確認する。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import runpy
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def tree(path):
    return {str(p.relative_to(path)): digest(p) for p in sorted(Path(path).rglob('*')) if p.is_file()}


def worker(a):
    """実APIまたは実CLIを実行し、失敗時にも非公開の実行証拠を残す。"""
    from vsora_correlator.input_identity import InputIdentity
    began = time.monotonic()
    identity = InputIdentity(a.manifest, a.clock_model)
    initial = identity.public_identity
    error = None
    try:
        if a.entry == 'api':
            from vsora_correlator.aligned import correlate_aligned
            correlate_aligned(a.manifest, a.clock_model, a.target, 1, a.start_offset_s)
        else:
            sys.argv = ['vsora-correlator', 'correlate-aligned', '--manifest', a.manifest,
                        '--clock-model', a.clock_model, '--output', a.target,
                        '--integrations', '1', '--start-offset-s', str(a.start_offset_s)]
            runpy.run_module('vsora_correlator', run_name='__main__', alter_sys=True)
    except Exception as exc:
        error = type(exc).__name__
        raise
    finally:
        identity.assert_current(a.manifest, a.clock_model)
        assert identity.public_identity == initial
        modules = {n: m.__file__ for n, m in sys.modules.items()
                   if n.startswith('vsora_') and getattr(m, '__file__', None)}
        write_json(a.runtime, {'error_type': error, 'identity': initial,
                   'identity_diagnostics': identity.diagnostics,
                   'api_or_cli_and_identity_elapsed_s': time.monotonic()-began,
                   'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                   'module_paths': modules})


def spectral_equal(first, second):
    import numpy as np
    from vsora_formats.spectral import load_spectral
    x = load_spectral(first); y = load_spectral(second)
    assert set(x) == set(y) and x['metadata'] == y['metadata']
    arrays = {}
    for key, value in x.items():
        if isinstance(value, np.ndarray):
            assert value.dtype == y[key].dtype and value.shape == y[key].shape
            np.testing.assert_array_equal(value, y[key])
            arrays[key] = {'dtype': value.dtype.str, 'shape': list(value.shape),
                           'sha256': hashlib.sha256(value.tobytes(order='C')).hexdigest()}
    return {'arrays': arrays, 'metadata': x['metadata']}


def run(a):
    out = Path(a.output).resolve()
    if a.mode == 'installed':
        assert not Path.cwd().resolve().is_relative_to(ROOT)
        assert not (Path.cwd()/'tools/run.py').exists() and 'PYTHONPATH' not in os.environ
    record = json.loads(Path(a.record131).read_text())
    raw = Path(a.raw_reference).resolve()
    def raw_check():
        names = [(raw/row['case']/'input'/name, sha)
                 for row in record['cases'] for name, sha in row['raw_input_file_sha256'].items()]
        assert len(names) == 76 and all(digest(p) == sha for p, sha in names)
    raw_check()
    out.mkdir(parents=True, exist_ok=False)
    base = raw/'high_a/input'; reference = Path(a.reference138).resolve()
    manifest = base/'manifest.json'; clock = base/'clock.json'
    expected_summary = json.loads((reference/'summary.json').read_text())
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    env.pop('PYTHONPATH', None)
    rows = []; timings = []
    source_roots = {d.name: d for parent in ('apps', 'packages') for d in (ROOT/parent).glob('*/src/vsora_*')}
    for entry in ('api', 'cli'):
        folder = out/entry; folder.mkdir()
        failed = folder/'failed'; partial = folder/'failed.partial'; recovered = folder/'recovered'
        def call(label, target, start, expected_error):
            private = folder/(label+'-runtime-private.json')
            command = [sys.executable]+([str(ROOT/'tools/run.py'), 'workflows.finite_recovery_validation']
                       if a.mode == 'source' else [str(Path(__file__).resolve())])
            command += ['--worker', '--entry', entry, '--manifest', str(manifest), '--clock-model', str(clock),
                        '--target', str(target), '--start-offset-s', str(start), '--runtime', str(private)]
            began = time.monotonic()
            result = subprocess.run(command, cwd=Path.cwd(), env=env, capture_output=True, text=True, timeout=120)
            wall = time.monotonic()-began
            (folder/(label+'.log')).write_text(result.stdout+result.stderr)
            runtime = json.loads(private.read_text())
            assert runtime['error_type'] == expected_error
            assert (result.returncode == 0) == (expected_error is None)
            if expected_error:
                assert expected_error in result.stderr
            origins = runtime.pop('module_paths'); assert origins
            assert all(Path(v).resolve().is_relative_to(source_roots[n.split('.')[0]]
                       if a.mode == 'source' else Path(sys.prefix)) for n, v in origins.items())
            timings.append({'entry': entry, 'action': label, 'worker_wall_s': wall,
                            'module_count': len(origins), 'origins_verified': True,
                            **{k: v for k, v in runtime.items() if k not in ('identity', 'identity_diagnostics')}})
            print(json.dumps({'mode': a.mode, 'entry': entry, 'action': label,
                              'error_type': expected_error, 'wall_s': wall}), flush=True)
            return runtime
        eof = call('eof', failed, 3.038, 'ValueError')
        assert not failed.exists() and partial.is_dir()
        failure = json.loads((partial/'failure.json').read_text())
        assert failure == {'state': 'incomplete', 'error_type': 'ValueError'}
        assert set(tree(partial)) == {'failure.json'}
        failed_bytes = tree(partial)
        same = call('partial-refused', failed, .002, 'FileExistsError')
        assert tree(partial) == failed_bytes and not failed.exists()
        success = call('new-output', recovered, .002, None)
        assert not (folder/'recovered.partial').exists() and partial.is_dir()
        summary = json.loads((recovered/'summary.json').read_text()); assert summary == expected_summary
        science = spectral_equal(recovered/'shard-00000.npz', reference/'shard-00000.npz')
        complete_bytes = tree(recovered)
        refused = call('complete-refused', recovered, .002, 'FileExistsError')
        assert tree(recovered) == complete_bytes and tree(partial) == failed_bytes
        assert eof['identity'] == same['identity'] == success['identity'] == refused['identity']
        rows.append({'entry': entry, 'input_identity': eof['identity'],
                     'failed_request_s': [3.038, 3.042], 'failure': failure,
                     'failure_files': failed_bytes, 'partial_preserved': True,
                     'same_partial_refused': True, 'complete_refused': True,
                     'complete_preserved': True, 'new_output_summary': summary,
                     'new_output_science': science,
                     'success_output_bytes': sum(p.stat().st_size for p in recovered.iterdir()),
                     'failure_output_bytes': sum(p.stat().st_size for p in partial.iterdir()),
                     'failure_actual_decoded_frame_count': None})
    raw_check()
    result = {'stage': 139, 'state': 'complete', 'entries': rows, 'actual_workers': 8,
              'raw_input_files_sha_preserved': 76, 'automatic_checkpoint_resume_implemented': False,
              'real_observation_or_full_night_performance_verified': False,
              'new_product_code_or_images': False}
    write_json(out/'reference.json', result)
    write_json(out/'measurements.json', {'mode': a.mode, 'workers': timings,
               'wall_scope': 'Parent subprocess start through exit, including Python/imports, fresh input SHA/stat and operation; one pass, no cache control.',
               'rss_scope': 'Linux RUSAGE_SELF lifetime peak in each independent worker; not incremental correlator memory.',
               'failure_read_range_measured': False})
    total = sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    assert total < 16*1024**2
    write_json(out/'verification.json', {'mode': a.mode, 'state': 'complete', 'actual_workers': 8,
               'origins_all_verified': True, 'source_or_installed_science_matches138': True,
               'raw_files_sha_preserved': 76, 'output_bytes_before_verification': total,
               'native_outside_checkout_no_runner_pythonpath': a.mode == 'installed'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--entry', choices=['api', 'cli'])
    parser.add_argument('--manifest'); parser.add_argument('--clock-model'); parser.add_argument('--target')
    parser.add_argument('--start-offset-s', type=float); parser.add_argument('--runtime')
    parser.add_argument('--mode', choices=['source', 'installed'], default='source')
    parser.add_argument('--raw-reference'); parser.add_argument('--record131')
    parser.add_argument('--reference138'); parser.add_argument('--output')
    args = parser.parse_args()
    if args.worker:
        worker(args)
    else:
        run(args)
