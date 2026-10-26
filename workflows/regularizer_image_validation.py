"""同じ格子・同じ入力で、固定した画像罰則の成分を比較する。"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scipy.special import softmax
from vsora_formats.spectral import load_spectral
from vsora_imaging.rml import image_closure,ClosureObjective
from vsora_imaging.experiment import compare_relative
from vsora_simulator.visibility import direct_visibility
from workflows.temporal_image_validation import SETTINGS,split_times,partition_input,sha,training_arrays_identity,module_origins
from workflows.closure_residual_diagnostics import diagnose_image
from workflows.image_grid_validation import embed_on_32
from workflows.integration_image_validation import stable_rml_summary

PRESETS={'centroid_removed':{'entropy':.01,'tsv':.0001,'centroid':0.},
         'morphology_priors_removed':{'entropy':0.,'tsv':0.,'centroid':.1},
         'data_only':{'entropy':0.,'tsv':0.,'centroid':0.}}
KNOWN_FAILURE='model visibility at numerical zero; change initial image'


def initial_reference(data,settings):
    cost={k:v for k,v in settings.items() if k not in ['starts','max_iterations','seed']};o=ClosureObjective(data['uvw_lambda'],data['visibilities'],data['weights'],data['pairs'],**cost);rng=np.random.default_rng(settings['seed']);z=[];q=[]
    for start in range(settings['starts']):
        x=np.log(o.prior)+(0 if start==0 else rng.normal(0,.5,o.prior.size));z.append(x);q.append(softmax(x))
    return {'prior':o.prior,'log_parameters':np.asarray(z),'initial_normalized_image':np.asarray(q)}


def read_reference(repository,reference):
    r=Path(repository).resolve();ref=Path(reference).resolve();enrolled=json.loads((r/'validation/runs/stage127/reference.json').read_text());g=enrolled['generation'];expected={'control.npz':g['control_archive_sha256'],'truth8.npy':g['coarse_truth_sha256'],'embedded-truth.npy':g['embedded_truth_sha256']}
    for row in enrolled['cases']:expected[row['split']+'/training.npz']=row['training_archive_sha256']
    assert all(sha(ref/n)==h for n,h in expected.items());data=load_spectral(ref/'control.npz');splits=split_times(8)
    for row in enrolled['cases']:
        a=load_spectral(ref/row['split']/'training.npz');b=partition_input(data,splits[row['split']]);assert training_arrays_identity(a)==training_arrays_identity(b) and a['metadata']==b['metadata']
    return data,enrolled,expected


def score_regularizer_setting(data,keep,image,summary,truth8,truth32,settings):
    assert summary['settings']==settings;cost={k:v for k,v in settings.items() if k not in ['pixels','starts','max_iterations','seed']};evaluation={}
    # priorは係数によらない。実constructorのpriorを後評価にも使う。
    prior=initial_reference(data,settings)['prior'].reshape(8,8)
    for support,mask in {'training':keep,'unused':~keep,'all':np.ones_like(keep)}.items():
        d=partition_input(data,mask);evaluation[support]={}
        for candidate,q in [('fit',image),('prior',prior),('oracle8',truth8)]:
            diagnostic,_=diagnose_image(d,q,**cost);evaluation[support][candidate]=diagnostic
    own=evaluation['training']['fit']['public_api']['metrics'];np.testing.assert_allclose(own['data_loss'],summary['data_loss'],rtol=1e-9,atol=1e-10)
    np.testing.assert_allclose(own['objective'],summary['objective']-summary['parameter_sum_penalty'],rtol=1e-9,atol=1e-10)
    assert evaluation['training']['fit']['independent_count']==summary['independent_closure_count']
    for candidate in ['fit','prior','oracle8']:
        a,b,c=(evaluation[s][candidate] for s in ['training','unused','all']);assert a['independent_count']+b['independent_count']==c['independent_count'];np.testing.assert_allclose(a['chi2_approx']+(b['chi2_approx'] if b['chi2_approx'] is not None else 0.),c['chi2_approx'],rtol=1e-12,atol=1e-10)
    selected=summary['selected_start'];assert selected==int(np.argmin([v['objective'] for v in summary['runs']]));embedded=embed_on_32(image);a=direct_visibility(data['uvw_lambda'],image,64.);b=direct_visibility(data['uvw_lambda'],embedded,16.);np.testing.assert_allclose(a,b,rtol=1e-12,atol=1e-14)
    metrics,_,_,_=compare_relative(truth32,embedded,16.)
    return {'rml_summary':stable_rml_summary(summary),'own_settings':settings,'selected_start':selected,'selected_run_converged':bool(summary['runs'][selected]['optimizer_success']),
            'evaluation':evaluation,'reference_metrics':metrics,'maximum_embedding_model_difference':float(np.max(abs(a-b))),'unit_flux_objective_excludes_parameter_sum_penalty':True,
            'truth_or_unused_values_used_for_selection':False,'actual_observation_validated':False},embedded


def run(repository,reference,output):
    ref=Path(reference).resolve();out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False);data,old,inputs=read_reference(repository,ref);splits=split_times(8);rows=[];initials={}
    for preset,coefficients in PRESETS.items():
        settings={**SETTINGS,**coefficients}
        for label,mask in splits.items():
            directory=out/preset/label;directory.mkdir(parents=True);spectrum=ref/label/'training.npz';d=load_spectral(spectrum);initial=initial_reference(d,settings)
            if label in initials:
                for k,v in initial.items():np.testing.assert_array_equal(v,initials[label][k])
            else:initials[label]=initial
            np.savez_compressed(directory/'initial-reference.npz',**initial)
            row={'preset':preset,'split':label,'settings':settings,'training_times':np.flatnonzero(mask).tolist(),'unused_times':np.flatnonzero(~mask).tolist(),'training_archive_sha256':sha(spectrum),'initial_reference_sha256':sha(directory/'initial-reference.npz')}
            try:
                summary=image_closure(spectrum,directory/'rml',**settings);row.update(state='fit_complete',fit_failure_code=None)
            except ValueError as exc:
                if str(exc)!=KNOWN_FAILURE:raise
                row.update(state='known_fit_failure',fit_failure_code='model_visibility_numerical_zero');(directory/'failure.json').write_text(json.dumps({'code':row['fit_failure_code'],'message':KNOWN_FAILURE},indent=2)+'\n')
            rows.append(row);print(json.dumps({'preset':preset,'split':label,'state':row['state']}),flush=True)
    # 既存の生成データだけを使い、truthはfitの引数やrun選択へ渡さない。
    truth8=np.load(ref/'truth8.npy',allow_pickle=False);truth32=np.load(ref/'embedded-truth.npy',allow_pickle=False)
    for row in rows:
        directory=out/row['preset']/row['split']
        if row['state']=='fit_complete':
            image=np.load(directory/'rml/relative-model.npy',allow_pickle=False);summary=json.loads((directory/'rml/summary.json').read_text());science,embedded=score_regularizer_setting(data,splits[row['split']],image,summary,truth8,truth32,row['settings']);np.save(directory/'embedded-model.npy',embedded);science.update(image_npy_sha256=sha(directory/'rml/relative-model.npy'),embedded_image_sha256=sha(directory/'embedded-model.npy'));row['science']=science
            print(json.dumps({'preset':row['preset'],'split':row['split'],'converged':science['selected_run_converged'],'train':science['evaluation']['training']['fit']['data_loss'],'unused':science['evaluation']['unused']['fit']['data_loss'],'nrmse':science['reference_metrics']['registered_nrmse']}),flush=True)
        else:row['science']=None
        (directory/'science.json').write_text(json.dumps(row,indent=2,allow_nan=False)+'\n')
    baseline=[{'split':v['split'],'science':v['science']} for v in old['cases']];assert len(rows)==9;assert all(sha(ref/n)==h for n,h in inputs.items());(out/'runtime-origins.json').write_text(json.dumps(module_origins(),indent=2)+'\n')
    result={'stage':128,'state':'complete','cases':rows,'input_files_sha256':inputs,'fixed_new_fit_attempts':9,'starts_each':3,'cited127_fits':3,'cited127_cases':baseline,
            'initial_references_equal_across_presets':True,'initial_reference_kind':'computed from unchanged constructor prior and initialization formula; not an optimizer trace',
            'defaults_changed':False,'hyperparameters_selected_using_truth_or_unused_data':False,
            'limits':'Fixed component ablation on one changed noiseless point sky with artificial SNR weights. Same initial formula and stopping settings; objective scale and local stopping behavior can change. No ranking of total objectives across different coefficients, independent noise trials, default recommendation or real observation validation.'}
    (out/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repository',required=True);p.add_argument('--reference',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.repository,a.reference,a.output)
