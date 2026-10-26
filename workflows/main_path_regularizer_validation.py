"""固定罰則を、模擬電圧由来の3つの保存相関へ全時刻で移送する。"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from vsora_formats.spectral import load_spectral
from vsora_imaging.rml import image_closure
from workflows.regularizer_image_validation import PRESETS,KNOWN_FAILURE,initial_reference,score_regularizer_setting
from workflows.temporal_image_validation import SETTINGS,sha,module_origins
from workflows.closure_residual_diagnostics import diagnose_image
from workflows.matched_grid_image_validation import quantize_truth8

BRANCHES=['estimated_rate','truth_rate_control','ideal_model_true_rate_snr_control']


def read_main_reference(repository,reference,truth_path):
    r=Path(repository).resolve();ref=Path(reference).resolve();old=json.loads((r/'validation/runs/stage126/reference.json').read_text());base=[v for v in old['cases'] if v['split']=='all_training'];assert len(base)==3
    enrolled=json.loads((r/'validation/runs/stage125/reference.json').read_text());expected={};loaded={}
    for row in base:
        name=row['branch']+'/all_training/training.npz';assert sha(ref/name)==row['training_archive_sha256'];expected[name]=row['training_archive_sha256'];loaded[row['branch']]=load_spectral(ref/name)
    assert sha(truth_path)==enrolled['input_files_sha256']['truth.npy'];expected['fine_truth_npy']=sha(truth_path)
    original_loss={b:next(v['diagnostic']['data_loss'] for v in enrolled['cases'] if v['branch']==b and v['support']=='common_baselines' and v['candidate']=='truth') for b in BRANCHES}
    return loaded,base,expected,original_loss


def score_main_case(data,image,summary,truth32,quantized8,settings,expected_fine_loss):
    keep=np.ones(len(data['times_s']),bool);science,embedded=score_regularizer_setting(data,keep,image,summary,quantized8,truth32,settings)
    for support in science['evaluation']:
        science['evaluation'][support]['quantized_reference8']=science['evaluation'][support].pop('oracle8')
        assert science['evaluation']['unused']['fit']['state']=='insufficient_constraints'
    fine,_=diagnose_image(data,truth32,pixel_arcsec=16.,entropy=0.,tsv=0.,centroid=0.)
    np.testing.assert_allclose(fine['data_loss'],expected_fine_loss,rtol=1e-12,atol=1e-12)
    # 格子が違う正解のregularizerは、fit8のFとの比較へ持ち込まない。
    fine_only={k:v for k,v in fine.items() if k in ['state','independent_counts','independent_count','chi2_approx','data_loss','component_chi2_approx','baseline_valid_count','cells','cells_with_constraints','basis_indices_sha256','basis_and_covariance_sha256']}
    fine_only.update(pixel_arcsec=16.,grid_pixels=32,regularizer_compared_across_grids=False,data_loss_absolute_difference_to125=abs(fine['data_loss']-expected_fine_loss))
    science.update(fine_generating_reference_residual=fine_only,quantized_reference8_is_generating_sky=False,new_unused_prediction_evaluated=False,all_eight_times_used_for_fit=True)
    return science,embedded


def run(repository,reference,truth_path,output):
    ref=Path(reference).resolve();out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False);loaded,baseline,inputs,fine_loss=read_main_reference(repository,ref,truth_path);rows=[];initials={}
    for preset,coefficients in PRESETS.items():
        settings={**SETTINGS,**coefficients}
        for branch in BRANCHES:
            directory=out/preset/branch;directory.mkdir(parents=True);data=loaded[branch];initial=initial_reference(data,settings)
            if branch in initials:
                for k,v in initial.items():np.testing.assert_array_equal(v,initials[branch][k])
            else:initials[branch]=initial
            np.savez_compressed(directory/'initial-reference.npz',**initial);spectrum=ref/branch/'all_training/training.npz';row={'preset':preset,'branch':branch,'settings':settings,'training_archive_sha256':sha(spectrum),'initial_reference_sha256':sha(directory/'initial-reference.npz'),'input_unit':data['metadata']['visibility_unit']}
            try:
                image_closure(spectrum,directory/'rml',**settings);row.update(state='fit_complete',fit_failure_code=None)
            except ValueError as exc:
                if str(exc)!=KNOWN_FAILURE:raise
                row.update(state='known_fit_failure',fit_failure_code='model_visibility_numerical_zero');(directory/'failure.json').write_text(json.dumps({'code':row['fit_failure_code'],'message':KNOWN_FAILURE},indent=2)+'\n')
            rows.append(row);print(json.dumps({'preset':preset,'branch':branch,'state':row['state']}),flush=True)
    # truth配列と量子化参照は全fit後の後評価だけ。元の生成天空はfine32のまま。
    truth32=np.load(truth_path,allow_pickle=False);quantized8=quantize_truth8(truth32)
    for row in rows:
        directory=out/row['preset']/row['branch']
        if row['state']=='fit_complete':
            image=np.load(directory/'rml/relative-model.npy',allow_pickle=False);summary=json.loads((directory/'rml/summary.json').read_text());science,embedded=score_main_case(loaded[row['branch']],image,summary,truth32,quantized8,row['settings'],fine_loss[row['branch']]);np.save(directory/'embedded-model.npy',embedded);science.update(image_npy_sha256=sha(directory/'rml/relative-model.npy'),embedded_image_sha256=sha(directory/'embedded-model.npy'));row['science']=science
            print(json.dumps({'preset':row['preset'],'branch':row['branch'],'converged':science['selected_run_converged'],'data_loss':science['evaluation']['all']['fit']['data_loss'],'nrmse':science['reference_metrics']['registered_nrmse']}),flush=True)
        else:row['science']=None
        (directory/'science.json').write_text(json.dumps(row,indent=2,allow_nan=False)+'\n')
    assert all(sha(truth_path if n=='fine_truth_npy' else ref/n)==h for n,h in inputs.items());(out/'runtime-origins.json').write_text(json.dumps(module_origins(),indent=2)+'\n')
    result={'stage':129,'state':'complete','cases':rows,'cited126_cases':baseline,'cited126_fits':3,'input_files_sha256':inputs,'fixed_new_fit_attempts':9,'starts_each':3,'initial_references_equal_across_presets':True,
            'initial_reference_kind':'constructor prior and unchanged initialization formula, not optimizer trace','fine_reference_loss_from125':fine_loss,'truth_array_loaded_after_all_fits':True,
            'new_unused_prediction_evaluated':False,'defaults_changed':False,'hyperparameters_selected_using_truth_or_unused_data':False,
            'limits':'Full-time transfer of ALL three predeclared settings to saved simulated-voltage estimated-LO/true-LO and artificial ideal controls. Original generating sky remains fine32, fitter8; quantized8 is a reference, not an exact oracle. No independent raw/noise generation, new holdout performance, calibrated Jy/astrometry, default recommendation or actual observation validation.'}
    (out/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repository',required=True);p.add_argument('--reference',required=True);p.add_argument('--truth',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.repository,a.reference,a.truth,a.output)
