"""保存済みの短積分相関を既存32格子RMLへ渡し、三つの判定を分ける。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import numpy as np
from vsora_formats.spectral import load_spectral, save_spectral
from vsora_imaging.assessment import assess_rml_result
from vsora_imaging.experiment import compare_relative
from vsora_imaging.objective_evaluation import evaluate_closure_image
from vsora_imaging.rml import ClosureObjective

SETTINGS = dict(pixels=32, pixel_arcsec=16., min_snr=10., prior_fwhm_arcsec=240.,
                entropy=.01, tsv=.0001, centroid=.1, starts=3, max_iterations=2000, seed=21)
FIELDS = ('visibilities', 'weights', 'pairs', 'uvw_lambda', 'times_s', 'frequencies_hz', 'integration_s')
NO_CONSTRAINTS = 'no high SNR independent closure measurements'


def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def write_json(path, value): Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def identities(data):
    return {k: {'dtype': data[k].dtype.str, 'shape': list(data[k].shape),
                'sha256': hashlib.sha256(data[k].tobytes(order='C')).hexdigest()} for k in FIELDS}


def fitter_data(data):
    """科学配列をそのまま残し、表示以外の観測metadataをfitterから除く。"""
    source = data['metadata']['config']['source']
    if source['model'] != 'unknown' or 'total_flux_jy' in source:
        raise ValueError('unknown observer sky without generating flux required')
    result = {k: np.asarray(data[k]).copy() for k in FIELDS}
    config = {'source': {k: source[k] for k in ('model', 'ra_deg', 'dec_deg')},
              'observation': {'frequency_hz': data['metadata']['config']['observation']['frequency_hz']},
              'image': {'pixels': 32, 'pixel_arcsec': 16.}}
    result['metadata'] = {'config': config, 'visibility_unit': data['metadata']['visibility_unit'],
                          'generating_truth_supplied_to_fitter': False}
    return result


def stable(value):
    if isinstance(value, dict): return {k: stable(v) for k, v in value.items() if k not in ('elapsed_s', 'input_sha256')}
    if isinstance(value, list): return [stable(v) for v in value]
    return value


def validate_selection(summary):
    selected = summary['selected_start']; runs = summary['runs']
    if (type(selected) is not int or not runs or not np.isfinite([r['objective'] for r in runs]).all()
            or selected != int(np.argmin([r['objective'] for r in runs]))):
        raise ValueError('selected run must minimize observed training objective')
    return selected


def score(data, image, summary, truth):
    validate_selection(summary)
    objective = ClosureObjective(data['uvw_lambda'], data['visibilities'], data['weights'], data['pairs'],
                                 **{k:v for k,v in SETTINGS.items() if k not in ('starts','max_iterations','seed')})
    prior = objective.prior.reshape(32,32)
    metrics, _, _, _ = compare_relative(truth, image, 16.)
    prior_metrics, _, _, _ = compare_relative(truth, prior, 16.)
    options = {k:v for k,v in SETTINGS.items() if k not in ('pixels','starts','max_iterations','seed')}
    evaluations = {name: evaluate_closure_image(data['uvw_lambda'], data['visibilities'], data['weights'],
                   data['pairs'], value, **options) for name,value in [('fit',image),('prior',prior),('truth',truth)]}
    np.testing.assert_allclose(evaluations['fit']['metrics']['data_loss'], summary['data_loss'], rtol=1e-7, atol=1e-8)
    assert objective.count == summary['independent_closure_count']
    return {'rml_summary': stable(summary), 'assessment': assess_rml_result(summary, reference_metrics=metrics),
            'reference_metrics': metrics, 'prior_reference_metrics': prior_metrics,
            'candidate_objectives': evaluations, 'truth_used_for_fit_selection': False}


def run(reference, raw_root, reference131, output, *, installed=False, expected=None):
    reference = Path(reference).resolve(); raw_root = Path(raw_root).resolve(); reference131 = Path(reference131).resolve()
    out = Path(output).resolve(); checkout = Path(__file__).resolve().parents[1]
    if out.exists(): raise FileExistsError('choose new image study output')
    memory = dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
    if shutil.disk_usage(out.parent).free<4*1024**3 or int(memory['MemAvailable'].split()[0])*1024<4*1024**3:
        raise ValueError('at least 4 GiB free disk and available memory required')
    # 既存131/132記録から原本と全相関数値を照合する。
    original = json.loads((reference/'summary.json').read_text()); raw_record = json.loads(reference131.read_text())
    public132 = reference131.parent.parent/'stage132/reference.json'
    if original != json.loads(public132.read_text()): raise ValueError('saved stage132 science differs from published record')
    assert original['stage']==132 and len(original['cases'])==12 and original['reference131_sha256']==sha(reference131)
    raw_hashes = {str(Path(row['case'])/'input'/n): h for row in raw_record['cases'] for n,h in row['raw_input_file_sha256'].items()}
    assert all(sha(raw_root/n)==h for n,h in raw_hashes.items())
    out.mkdir(parents=True); rows = []; loaded = {}; inputs = {}; times = []
    for row in original['cases']:
        case = row['case']; root = out/case; root.mkdir()
        if row['science']['pipeline']['state'] != 'complete':
            raise ValueError('this fixed study expects the twelve completed stage132 correlations')
        source = reference/case/'pipeline/correlation/shard-00000.npz'; inputs[case] = sha(source)
        observed = load_spectral(source)
        assert identities(observed)=={k:row['science']['correlation']['arrays'][k] for k in FIELDS}
        data = fitter_data(observed); assert identities(data)==identities(observed); loaded[case] = data
        spectrum = root/'fitter.npz'; save_spectral(spectrum,{k:data[k] for k in FIELDS},data['metadata'])
        assert identities(load_spectral(spectrum))==identities(observed)
        command = [sys.executable]
        command += ['-m'] if installed else [str(checkout/'tools/run.py')]
        command += ['vsora_imaging.rml','--input',str(spectrum),'--output',str(root/'rml')]
        for key,value in SETTINGS.items(): command += ['--'+key.replace('_','-'), str(value)]
        started = time.monotonic(); result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        times.append({'case':case,'elapsed_s':time.monotonic()-started}); (root/'rml-cli.log').write_text(result.stdout+result.stderr)
        failure = None
        if result.returncode:
            if 'ValueError: '+NO_CONSTRAINTS+'\n' not in result.stderr: raise RuntimeError(result.stderr[-2000:])
            failure = 'no_high_snr_independent_closures'; assert not (root/'rml').exists()
        else:
            before = {p.name:sha(p) for p in (root/'rml').iterdir() if p.is_file()}
            repeated = subprocess.run(command,capture_output=True,text=True,timeout=30)
            assert repeated.returncode!=0 and 'FileExistsError' in repeated.stderr
            assert before=={p.name:sha(p) for p in (root/'rml').iterdir() if p.is_file()}
        rows.append({'case':case,'raw_case':row['raw_case'],'integration_s':row['integration_s'],
                     'source_correlation_sha256':inputs[case], 'fitter_arrays':identities(data),
                     'fitter_archive_sha256':sha(spectrum),'failure_code':failure})
        write_json(out/'progress.json',{'state':'fitting','conditions_completed':len(rows),'expected':12})
        print(json.dumps({'case':case,'image_returned':failure is None,'failure':failure}),flush=True)
        if sum(p.stat().st_size for p in out.rglob('*') if p.is_file())>64*1024**2: raise ValueError('64 MiB study limit exceeded')
    # 最適化とrun選択を全件終えてから天空真値へアクセスする。
    truth_hashes = {row['case']:row['truth_npy_sha256'] for row in raw_record['cases']}
    truths = {}
    for case,digest in truth_hashes.items():
        path = raw_root/case/'truth.npy'; assert sha(path)==digest
        truths[case] = np.load(path,allow_pickle=False)
        np.testing.assert_array_equal(truths[case],truths[next(iter(truths))])
    for row in rows:
        root = out/row['case']
        if row['failure_code'] is not None:
            row['science'] = {'rml_summary':None,'reference_metrics':None,'prior_reference_metrics':None,
                              'assessment':assess_rml_result(None,processing_state='incomplete'),
                              'candidate_objectives':None,'truth_used_for_fit_selection':False}
        else:
            truth = truths[row['raw_case']]; image = np.load(root/'rml/relative-model.npy',allow_pickle=False)
            summary = json.loads((root/'rml/summary.json').read_text())
            row['science'] = score(loaded[row['case']],image,summary,truth)
            row['science']['image_npy_sha256'] = sha(root/'rml/relative-model.npy')
        write_json(root/'science.json',row['science'])
        print(json.dumps({'case':row['case'],'numerical':row['science']['assessment']['numerical']['state'],
                          'nrmse':None if row['science']['reference_metrics'] is None else row['science']['reference_metrics']['registered_nrmse']}),flush=True)
    assert all(sha(reference/case/'pipeline/correlation/shard-00000.npz')==h for case,h in inputs.items())
    assert all(sha(raw_root/n)==h for n,h in raw_hashes.items())
    assert all(sha(raw_root/case/'truth.npy')==h for case,h in truth_hashes.items())
    origins = {n:m.__file__ for n,m in sys.modules.items() if n.startswith('vsora_') and getattr(m,'__file__',None)}
    write_json(out/'runtime-private.json',{'project_origins':origins})
    write_json(out/'measurements.json',{'cases':times,'scope':'Owned RML CLI including imports; no new correlation/real receiver/GPU benchmark'})
    result = {'stage':133,'state':'complete','settings':SETTINGS,'cases':rows,'input_correlation_sha256':inputs,
              'public_stage132_reference_sha256':sha(public132),'all_four_truth_arrays_identical':True,
              'truth_npy_sha256':truth_hashes,'raw_files_sha_preserved':76,'truth_read_after_all_fits':True,
              'new_raw_or_correlation':False,'limits':'Four fixed single-epoch simulated raw records; overlapping final durations and 3s pilot. Existing high-SNR closure model/local optimizer. Shape, convergence and processing separate; no independent success trials, low-SNR likelihood or actual Cas A certification.'}
    if expected is not None and expected!=result: raise ValueError('source/native science mismatch')
    write_json(out/'summary.json',result)
    write_json(out/'progress.json',{'state':'complete','conditions_completed':12})
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference',required=True);p.add_argument('--raw-root',required=True)
    p.add_argument('--reference131',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.reference,a.raw_root,a.reference131,a.output)
