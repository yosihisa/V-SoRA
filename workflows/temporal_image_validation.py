"""固定8時刻の学習と未使用評価を、既存RMLのまま分ける。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from vsora_formats.spectral import load_spectral,save_spectral
from vsora_imaging.rml import image_closure
from vsora_imaging.experiment import compare_relative
from vsora_simulator.visibility import direct_visibility
from workflows.closure_residual_diagnostics import common_baseline_mask,diagnose_image
from workflows.image_grid_validation import embed_on_32
from workflows.integration_image_validation import stable_rml_summary
from workflows.rate_acquisition_validation import arrays_identity

SETTINGS={'pixels':8,'pixel_arcsec':64.,'min_snr':10.,'prior_fwhm_arcsec':240.,'entropy':.01,'tsv':.0001,'centroid':.1,'starts':3,'max_iterations':2000,'seed':21}
NUMERIC_FIELDS=('visibilities','weights','pairs','uvw_lambda','times_s','frequencies_hz','integration_s')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def split_times(n):
    if isinstance(n,bool) or not isinstance(n,int) or n<2:raise ValueError('at least two integer time slots required')
    even=np.arange(n)%2==0
    return {'even_training':even,'odd_training':~even,'all_training':np.ones(n,bool)}


def partition_input(data,keep):
    """学習外visibilityを渡さず、表示用設定だけの新しい入力を作る。"""
    mask=np.asarray(keep);v=np.asarray(data['visibilities']);w=np.asarray(data['weights'])
    if mask.dtype!=bool or mask.shape!=(v.shape[0],) or v.ndim!=3 or w.shape!=v.shape:
        raise ValueError('boolean mask matching spectral time axis required')
    result={k:np.asarray(data[k]).copy() for k in NUMERIC_FIELDS}
    result['visibilities'][~mask]=1+0j;result['weights'][~mask]=0.
    original=data['metadata']['config']
    config={'source':{'model':'unknown','ra_deg':original['source']['ra_deg'],'dec_deg':original['source']['dec_deg']},
            'observation':{'frequency_hz':original['observation']['frequency_hz']},'image':{'pixels':8,'pixel_arcsec':64.}}
    result['metadata']={'visibility_unit':data['metadata']['visibility_unit'],'config':config,'training_time_indices':np.flatnonzero(mask).tolist(),
                        'unused_visibility_replaced_with_constant':True,'generating_truth_supplied_to_fitter':False}
    return result


def training_arrays_identity(data):
    return arrays_identity({k:data[k] for k in NUMERIC_FIELDS})


def prior_image():
    axis=(np.arange(8)-4)*64.;y,x=np.meshgrid(axis,axis,indexing='ij');q=np.maximum(np.exp(-4*np.log(2)*(x*x+y*y)/240.**2),1e-12);return q/q.sum()


def score_fit(data,keep,image,summary,truth):
    """fit終了後にだけ真値を使い、固定の全候補と全支持を評価する。"""
    supports={'training':keep,'unused':~keep,'all':np.ones_like(keep)};costs={}
    for name,mask in supports.items():
        evaluation=partition_input(data,mask);costs[name]={}
        for candidate,q,pixel in [('fit',image,64.),('prior',prior_image(),64.),('truth',truth,16.)]:
            diagnostic,_=diagnose_image(evaluation,q,pixel_arcsec=pixel)
            costs[name][candidate]=diagnostic
    np.testing.assert_allclose(costs['training']['fit']['data_loss'],summary['data_loss'],rtol=1e-9,atol=1e-10)
    assert costs['training']['fit']['independent_count']==summary['independent_closure_count']
    for candidate in ['fit','prior','truth']:
        a,b,c=(costs[k][candidate] for k in ['training','unused','all'])
        assert a['independent_count']+b['independent_count']==c['independent_count']
        chi=a['chi2_approx']+(b['chi2_approx'] if b['chi2_approx'] is not None else 0.)
        np.testing.assert_allclose(chi,c['chi2_approx'],rtol=1e-12,atol=1e-10)
    embedded=embed_on_32(image)
    a=direct_visibility(data['uvw_lambda'],image,64.);b=direct_visibility(data['uvw_lambda'],embedded,16.)
    np.testing.assert_allclose(a,b,rtol=1e-12,atol=1e-14)
    metrics,_,_,_=compare_relative(truth,embedded,16.)
    selected=summary['selected_start'];assert selected==int(np.argmin([x['objective'] for x in summary['runs']]))
    return {'rml_summary':stable_rml_summary(summary),'selected_start':selected,'selected_run_converged':bool(summary['runs'][selected]['optimizer_success']),
            'all_runs_converged':all(x['optimizer_success'] for x in summary['runs']),'evaluation':costs,'reference_metrics':metrics,
            'maximum_embedding_model_difference':float(np.max(np.abs(a-b))),'truth_used_for_selection':False,'independent_noise_trials_claimed':False},embedded


def module_origins():return {n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('vsora_') and getattr(m,'__file__',None)}


def run(repository,reference,output):
    r=Path(repository).resolve();ref=Path(reference).resolve();out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    enrolled=json.loads((r/'validation/runs/stage125/reference.json').read_text());names=['estimated_rate','truth_rate_control','ideal_model_true_rate_snr_control'];loaded=[];inputs={}
    for name in names:
        path=ref/name/'visibility.npz';expected=enrolled['input_files_sha256'][name+'/visibility.npz'];assert sha(path)==expected;inputs[name+'/visibility.npz']=expected;loaded.append(load_spectral(path))
    assert all(len(d['times_s'])==8 for d in loaded);common=common_baseline_mask(loaded);assert int(common.sum())==283;np.save(out/'common-baseline-mask.npy',common);assert sha(out/'common-baseline-mask.npy')==enrolled['common_baseline_mask_sha256']
    splits=split_times(8);rows=[];data_by_branch={}
    for name,original in zip(names,loaded,strict=True):
        data={**original,'weights':np.where(common,original['weights'],0.)};data_by_branch[name]=data
        for label,mask in splits.items():
            directory=out/name/label;directory.mkdir(parents=True);fitter=partition_input(data,mask);spectrum=directory/'training.npz'
            save_spectral(spectrum,{k:fitter[k] for k in NUMERIC_FIELDS},fitter['metadata']);assert training_arrays_identity(load_spectral(spectrum))==training_arrays_identity(fitter)
            summary=image_closure(spectrum,directory/'rml',**SETTINGS)
            rows.append({'branch':name,'split':label,'training_times':np.flatnonzero(mask).tolist(),'unused_times':np.flatnonzero(~mask).tolist(),
                         'original_input_sha256':inputs[name+'/visibility.npz'],'training_archive_sha256':sha(spectrum),'training_numeric_arrays':training_arrays_identity(fitter)})
            (out/'progress.json').write_text(json.dumps({'state':'fitting','fits_completed':len(rows),'expected':9},indent=2)+'\n')
            print(json.dumps({'branch':name,'split':label,'fit_complete':True,'selected_start':summary['selected_start']}),flush=True)
    # 正解画像は全fitが終わってから読み込む。fitterのarchiveに形状・gain・LOを含めない。
    assert len(rows)==9;truth_path=ref/'truth.npy';assert sha(truth_path)==enrolled['input_files_sha256']['truth.npy'];inputs['truth.npy']=sha(truth_path);truth=np.load(truth_path,allow_pickle=False)
    for row in rows:
        directory=out/row['branch']/row['split'];image=np.load(directory/'rml/relative-model.npy',allow_pickle=False);summary=json.loads((directory/'rml/summary.json').read_text())
        science,embedded=score_fit(data_by_branch[row['branch']],splits[row['split']],image,summary,truth);np.save(directory/'embedded-model.npy',embedded)
        science.update(image_npy_sha256=sha(directory/'rml/relative-model.npy'),embedded_image_sha256=sha(directory/'embedded-model.npy'));row['science']=science
        (directory/'science.json').write_text(json.dumps(science,indent=2,allow_nan=False)+'\n')
        print(json.dumps({'branch':row['branch'],'split':row['split'],'converged':science['selected_run_converged'],'train':science['evaluation']['training']['fit']['data_loss'],'unused':science['evaluation']['unused']['fit']['data_loss'],'nrmse':science['reference_metrics']['registered_nrmse']}),flush=True)
    assert all(sha(ref/n)==h for n,h in inputs.items());(out/'runtime-origins.json').write_text(json.dumps(module_origins(),indent=2)+'\n')
    result={'stage':126,'state':'complete','cases':rows,'fixed_new_fits':9,'starts_each':3,'settings':SETTINGS,'common_valid_baselines':283,'input_files_sha256':inputs,
            'original_axes_and_arrays_unchanged':True,'truth_read_after_all_fits':True,'heldout_values_used_for_fit_selection':False,
            'limits':'Conditional time split of the same saved observation. Common mask and upstream LO/weights can share information across times. Not independent end-to-end blind trials, noise-only intervention, low-SNR likelihood or real observation validation. Eight-pixel point grid fixed before fit; no default change.'}
    (out/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repository',required=True);p.add_argument('--reference',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.repository,a.reference,a.output)
