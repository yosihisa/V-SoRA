"""固定VDIF原本の未知LO取得と短積分相関を、画像化と分けて調べる。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import numpy as np
from vsora_correlator.rate_graph import diagnose_rate_graph
from vsora_formats.spectral import load_spectral
from vsora_imaging.closure import extract_closures, independent_closures


CASES = ('high_a', 'high_b', 'weak_a', 'weak_b')
DURATIONS = (.3, 1., 3.)
PILOT = 750
EXPECTED_FAILURES = {
    'detected rate graph is disconnected; use a longer/stronger pilot or fewer stations': 'rate_graph_disconnected',
    'baseline rate estimates inconsistent with station rates': 'rate_inconsistent',
}


def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def array_identity(values):
    return {k: {'dtype': v.dtype.str, 'shape': list(v.shape),
                'sha256': hashlib.sha256(v.tobytes(order='C')).hexdigest()}
            for k, v in values.items() if k != 'metadata'}


def verify_inputs(raw_root, reference):
    """公開済み131の全入力SHAを先に照合し、天空真値を観測入力へ入れない。"""
    rows = reference['cases']
    if [r['case'] for r in rows] != list(CASES): raise ValueError('fixed four raw cases required')
    for row in rows:
        raw = Path(raw_root)/row['case']/'input'
        actual = {p.name: sha(p) for p in sorted(raw.iterdir()) if p.is_file()}
        if len(actual) != 19 or actual != row['raw_input_file_sha256']:
            raise ValueError('published raw input SHA mismatch')
        observed = json.loads((raw/'observation.json').read_text())
        if (observed['source']['model'] != 'unknown' or 'total_flux_jy' in observed['source']
                or observed['noise']['enabled'] is not True):
            raise ValueError('unknown sky without flux and declared raw noise required')
    return rows


def check_resources(path):
    memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    if shutil.disk_usage(path).free < 4*1024**3 or int(memory['MemAvailable'].split()[0])*1024 < 4*1024**3:
        raise ValueError('at least 4 GiB free disk and available memory required')


def normalize_metadata(metadata):
    # archive/profile SHAは保存場所の異なる来歴。各環境内で別途対応を確認する。
    return {k: v for k, v in metadata.items() if k != 'rate_only_profile_sha256'}


def strip_input_sha(value):
    if isinstance(value, dict): return {k: strip_input_sha(v) for k, v in value.items() if k != 'input_sha256'}
    if isinstance(value, list): return [strip_input_sha(v) for v in value]
    return value


def spectral_projection(path):
    data = load_spectral(path)
    return {'arrays': array_identity(data), 'metadata': normalize_metadata(data['metadata'])}


def independent_counts(archive):
    """全Closure数と、共分散を考慮した独立制約のrankを区別する。"""
    rows = []
    for index in np.ndindex(archive['baseline_variance'].shape[:-1]):
        row = {'cell': list(index)}
        for kind in ('phase', 'logamp'):
            selected, covariance = independent_closures(archive[kind+'_matrix'], archive[kind+'_valid'][index],
                                                        archive['baseline_variance'][index])
            row[kind] = {'rank': len(selected), 'selected': selected.tolist(),
                         'covariance': array_identity({'covariance': covariance})['covariance']}
        rows.append(row)
    return {'cells': rows, 'phase_rank': sum(r['phase']['rank'] for r in rows),
            'logamp_rank': sum(r['logamp']['rank'] for r in rows)}


def truth_evaluation(estimate, generating, pairs, duration):
    """推定完了後の評価だけ。一定rate差のsincはcoherenceの実測ではない。"""
    if estimate is None: return None
    measured = np.asarray(estimate['station_rates_hz'], dtype=float)
    truth = np.asarray(generating['station_rates_hz'], dtype=float)
    if (measured.shape != truth.shape or measured.ndim != 1
            or not np.isfinite(truth).all() or not np.isfinite(measured).all()):
        raise ValueError('matching finite station truth required for post-estimation evaluation')
    residual = measured-truth
    delta = residual[pairs[:, 0]]-residual[pairs[:, 1]]
    return {'maximum_station_rate_error_hz': float(np.max(np.abs(residual))),
            'station_rate_errors_hz': residual.tolist(),
            'calculated_minimum_constant_rate_boxcar_retention': float(np.min(np.abs(np.sinc(duration*delta)))),
            'retention_is_measured_coherence': False, 'truth_supplied_to_estimator': False}


def classify_result(root, returncode, stderr):
    """既知の科学的停止だけ受理し、その他の実装失敗を隠さない。"""
    path = root/'pipeline'
    if returncode == 0:
        summary = json.loads((path/'pipeline.json').read_text())
        if summary['state'] != 'complete': raise ValueError('successful process must have complete pipeline')
        return path, summary, None
    matches = [code for message, code in EXPECTED_FAILURES.items() if 'ValueError: '+message+'\n' in stderr]
    if len(matches) != 1: raise RuntimeError('unexpected pipeline failure: '+stderr[-2000:])
    path = root/'pipeline.partial'; summary = json.loads((path/'pipeline.json').read_text())
    if summary['state'] != 'incomplete' or summary['error_type'] != 'ValueError':
        raise ValueError('scientific failure requires explicit incomplete ValueError record')
    return path, summary, matches[0]


def science_projection(root, pipeline, summary, failure, generating, duration):
    pilot = spectral_projection(pipeline/'pilot/shard-00000.npz')
    estimate = summary.get('rate_estimate')
    # 完了summaryの入出力来歴以外を全て保持する。pilot/相関summaryも含む。
    excluded = {'input_manifest_sha256', 'input_clock_sha256', 'input_observation_sha256',
                'input_vdif', 'input_identity'}
    science = {'pipeline': strip_input_sha({k: v for k, v in summary.items() if k not in excluded}),
               'scientific_failure_code': failure, 'pilot': pilot,
               'graph': diagnose_rate_graph(load_spectral(pipeline/'pilot/shard-00000.npz')),
               'correlation': None, 'closures': None, 'closure_archive': None,
               'independent_closures': None, 'truth_evaluation': None}
    if summary['state'] == 'complete':
        spectrum = pipeline/'correlation/shard-00000.npz'
        science['correlation'] = spectral_projection(spectrum)
        science['closures'] = extract_closures(spectrum, root/'closures.npz', min_snr=10.)
        with np.load(root/'closures.npz', allow_pickle=False) as saved:
            arrays = {k: saved[k] for k in saved.files if k != 'metadata_json'}
            metadata = json.loads(str(saved['metadata_json']))
        science['closure_archive'] = {'arrays': array_identity(arrays), 'metadata': strip_input_sha(metadata)}
        science['independent_closures'] = independent_counts(arrays)
        science['truth_evaluation'] = truth_evaluation(estimate, generating, arrays['pairs'], duration)
        # 適用profileと保存相関の来歴は環境ごとに照合。
        if load_spectral(spectrum)['metadata']['rate_only_profile_sha256'] != sha(pipeline/'rate-only.json'):
            raise ValueError('applied rate profile provenance mismatch')
    return science


def run(raw_root, reference_path, output, *, installed=False, expected=None):
    raw_root = Path(raw_root).resolve(); reference_path = Path(reference_path).resolve(); out = Path(output).resolve()
    reference = json.loads(reference_path.read_text()); inputs = verify_inputs(raw_root, reference)
    if out.exists(): raise FileExistsError('choose new study output')
    check_resources(out.parent); out.mkdir(parents=True, exist_ok=False)
    checkout = Path(__file__).resolve().parents[1]; rows = []; timing = []; previous_pilots = {}
    for source in inputs:
        raw = raw_root/source['case']/'input'
        for duration in DURATIONS:
            case = f"{source['case']}_t{duration:g}"; root = out/case; root.mkdir()
            worker = [sys.executable]
            if not installed: worker += [str(checkout/'tools/run.py')]
            else: worker += ['-m']
            worker += ['vsora_correlator.closure_pipeline', '--manifest', str(raw/'manifest.json'),
                       '--clock-model', str(raw/'clock.json'), '--output', str(root/'pipeline'),
                       '--pilot-integrations', str(PILOT), '--integration-s', str(duration), '--correlation-only']
            start = time.monotonic(); completed = subprocess.run(worker, capture_output=True, text=True, timeout=180)
            timing.append({'case': case, 'elapsed_s': time.monotonic()-start})
            (root/'pipeline-cli.log').write_text(completed.stdout+completed.stderr)
            pipeline, summary, failure = classify_result(root, completed.returncode, completed.stderr)
            science = science_projection(root, pipeline, summary, failure, source['generating'], duration)
            # 同じ原本で最終積分だけを変えてもpilotと取得解は同一。
            acquisition = {'pilot': science['pilot'], 'graph': science['graph'],
                           'rate_estimate': science['pipeline'].get('rate_estimate'),
                           'rate_consistency': science['pipeline'].get('rate_consistency')}
            if source['case'] in previous_pilots:
                if previous_pilots[source['case']] != acquisition: raise ValueError('same raw pilot changed across final durations')
            previous_pilots[source['case']] = acquisition
            science_row = {'case': case, 'raw_case': source['case'], 'integration_s': duration, 'science': science}
            if expected is not None and expected['cases'][len(rows)] != science_row:
                raise ValueError('source and installed science mismatch: '+case)
            write_json(root/'science.json', science)
            before = {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file()}
            repeat = subprocess.run(worker, capture_output=True, text=True, timeout=180)
            if repeat.returncode == 0 or 'FileExistsError' not in repeat.stderr:
                raise ValueError('existing pipeline must reject overwrite')
            if before != {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file()}:
                raise ValueError('rejected pipeline overwrite changed files')
            rows.append(science_row); write_json(out/'progress.json', rows)
            print(json.dumps({'case': case, 'state': summary['state'], 'failure': failure,
                              'graph': science['graph']['state'], 'edges': science['graph']['accepted_baselines'],
                              'closures': science['closures'], 'independent': None if science['independent_closures'] is None else
                              {k: science['independent_closures'][k] for k in ('phase_rank','logamp_rank')},
                              'truth_evaluation': science['truth_evaluation']}), flush=True)
            if sum(p.stat().st_size for p in out.rglob('*') if p.is_file()) > 512*1024**2:
                raise ValueError('study output exceeds fixed 512 MiB budget')
    verify_inputs(raw_root, reference)
    origins = {n: m.__file__ for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None)}
    if installed:
        if not all(Path(v).resolve().is_relative_to(Path(sys.prefix)) for v in origins.values()):
            raise ValueError('installed project module outside prefix')
    else:
        for n, v in origins.items():
            name = n.split('.')[0]; allowed = list(checkout.glob(f'apps/*/src/{name}'))+list(checkout.glob(f'packages/*/src/{name}'))
            if len(allowed) != 1 or not Path(v).resolve().is_relative_to(allowed[0]): raise ValueError('wrong source module origin')
    write_json(out/'runtime-private.json', {'project_origins': origins, 'raw_root': str(raw_root), 'prefix': sys.prefix})
    write_json(out/'measurements.json', {'cases': timing, 'module_count': len(origins), 'output_bytes': sum(p.stat().st_size for p in out.rglob('*') if p.is_file())})
    result = {'stage': 132, 'state': 'complete', 'reference131_sha256': sha(reference_path), 'cases': rows,
              'settings': {'pilot_integrations': PILOT, 'pilot_integration_s': .004, 'pilot_span_s': 3.,
                           'start_offset_s': .002, 'durations_s': list(DURATIONS), 'max_baseline_rate_hz': 100.,
                           'closure_min_snr': 10., 'rate_model': 'constant', 'require_rate_consistency': False},
              'input_files_sha_preserved': 76, 'same_raw_pilots_identical': True,
              'nonoverwrite_cases': len(rows), 'images_executed': False,
              'limits': 'Four fixed single-epoch simulated VDIF records; durations and pilots overlap. Joint noise/gain/LO seeds, assumed SEFD and source, exact supplied clocks/scales. No zero-sky, false-alarm calibration, low-SNR likelihood, image, real receiver or full-night/GPU validation.'}
    if expected is not None and result != expected: raise ValueError('all science JSON mismatch')
    write_json(out/'summary.json', result); return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--raw-root', required=True); p.add_argument('--reference131', required=True)
    p.add_argument('--output', required=True); a = p.parse_args(); run(a.raw_root, a.reference131, a.output)
