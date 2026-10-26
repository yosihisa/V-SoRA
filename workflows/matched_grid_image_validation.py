"""生成天空を復元格子へ一致させる、無雑音・人工SNRの最小対照。"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from vsora_formats.spectral import load_spectral,save_spectral
from vsora_imaging.closure import form_closures,independent_closures
from vsora_imaging.rml import image_closure
from vsora_simulator.visibility import direct_visibility
from workflows.closure_residual_diagnostics import common_baseline_mask,diagnose_image
from workflows.image_control_validation import idealize_visibility
from workflows.image_grid_validation import embed_on_32
from workflows.temporal_image_validation import SETTINGS,NUMERIC_FIELDS,split_times,partition_input,score_fit,sha,training_arrays_identity,module_origins


def quantize_truth8(image):
    """各点fluxを最近傍64秒角中心へ加算。tieは正方向、外側正fluxは拒否。"""
    q=np.asarray(image)
    if (q.shape!=(32,32) or not np.issubdtype(q.dtype,np.number) or np.iscomplexobj(q)
            or not np.isfinite(q).all() or np.any(q<0)):
        raise ValueError('finite nonnegative real 32x32 generating image required')
    q=q.astype(float)
    with np.errstate(over='ignore'):total=float(q.sum())
    if not np.isfinite(total) or total<=0:raise ValueError('finite positive generating flux required')
    y,x=np.nonzero(q>0);yy=np.floor((y-16)*16./64.+4+.5).astype(int);xx=np.floor((x-16)*16./64.+4+.5).astype(int)
    if np.any((yy<0)|(yy>=8)|(xx<0)|(xx>=8)):raise ValueError('positive generating flux would leave the 8-pixel grid')
    coarse=np.zeros((8,8));np.add.at(coarse,(yy,xx),q[y,x]);np.testing.assert_allclose(coarse.sum(),total,rtol=1e-14,atol=0.)
    return coarse


def point_sum_visibility(uvw,image):
    """独立な点源ごとの複素和。coreのDFT行列・座標生成を使わない。"""
    values=np.zeros(np.asarray(uvw).shape[:-1],complex);angle=np.pi/(180*3600)
    for y,x in zip(*np.nonzero(image),strict=True):
        l=(x-4)*64.*angle;m=(y-4)*64.*angle;n=np.sqrt(1-(l*l+m*m))-1
        values+=image[y,x]*np.exp(-2j*np.pi*(uvw[...,0]*l+uvw[...,1]*m+uvw[...,2]*n))
    return values


def transport_diagnostic(old,new):
    a=form_closures(old['visibilities'],old['weights'],old['pairs'],10.);b=form_closures(new['visibilities'],new['weights'],new['pairs'],10.)
    for key in ['baseline_valid','phase_valid','logamp_valid']:np.testing.assert_array_equal(a[key],b[key])
    snr_a=abs(old['visibilities'])*np.sqrt(old['weights']);snr_b=abs(new['visibilities'])*np.sqrt(new['weights']);np.testing.assert_allclose(snr_a,snr_b,rtol=1e-12,atol=0.)
    np.testing.assert_allclose(a['baseline_variance'],b['baseline_variance'],rtol=1e-12,atol=0.)
    positive=snr_a>0;variance=a['baseline_variance']>0;rows=[];arrays={};counts={'phase':0,'logamp':0}
    for t in range(snr_a.shape[0]):
        for f in range(snr_a.shape[1]):
            for kind in ['phase','logamp']:
                i,c=independent_closures(a[kind+'_matrix'],a[kind+'_valid'][t,f],a['baseline_variance'][t,f]);j,d=independent_closures(b[kind+'_matrix'],b[kind+'_valid'][t,f],b['baseline_variance'][t,f]);assert len(i)==len(j);counts[kind]+=len(i)
                prefix=f't{t:03d}_f{f:03d}_{kind}';arrays[prefix+'_old_indices']=i;arrays[prefix+'_new_indices']=j;arrays[prefix+'_old_covariance']=c;arrays[prefix+'_new_covariance']=d
                rows.append({'time_index':t,'frequency_index':f,'kind':kind,'independent_count':len(i),'indices_identical':bool(np.array_equal(i,j))})
    arrays.update(old_snr=snr_a,new_snr=snr_b,old_baseline_variance=a['baseline_variance'],new_baseline_variance=b['baseline_variance'])
    return {'baseline_masks_identical':True,'all_closure_valid_masks_identical':True,'valid_baseline_cells':int(a['baseline_valid'].sum()),'independent_counts':counts,
            'maximum_relative_snr_difference':float(np.max(abs(snr_b[positive]/snr_a[positive]-1))) if positive.any() else 0.,
            'maximum_relative_variance_difference':float(np.max(abs(b['baseline_variance'][variance]/a['baseline_variance'][variance]-1))) if variance.any() else 0.,
            'basis_indices_all_identical':all(v['indices_identical'] for v in rows),'cells_and_components':rows,
            'basis_identity_required':False,'rank_and_mask_identity_required':True,'physical_noise_calibration_measured':False},arrays


def make_control(repository,reference,output):
    r=Path(repository).resolve();ref=Path(reference).resolve();out=Path(output);out.mkdir(parents=True,exist_ok=False);enrolled=json.loads((r/'validation/runs/stage125/reference.json').read_text())
    names=['estimated_rate','truth_rate_control','ideal_model_true_rate_snr_control'];loaded=[];inputs={}
    for name in names:
        path=ref/name/'visibility.npz';digest=enrolled['input_files_sha256'][name+'/visibility.npz'];assert sha(path)==digest;inputs[name+'/visibility.npz']=digest;loaded.append(load_spectral(path))
    truth_path=ref/'truth.npy';assert sha(truth_path)==enrolled['input_files_sha256']['truth.npy'];inputs['truth.npy']=sha(truth_path);truth8=quantize_truth8(np.load(truth_path,allow_pickle=False));np.save(out/'truth8.npy',truth8);truth32=embed_on_32(truth8);np.save(out/'embedded-truth.npy',truth32)
    common=common_baseline_mask(loaded);assert common.sum()==283;np.save(out/'common-baseline-mask.npy',common);assert sha(out/'common-baseline-mask.npy')==enrolled['common_baseline_mask_sha256']
    old={**loaded[2],'weights':np.where(common,loaded[2]['weights'],0.)};model=direct_visibility(old['uvw_lambda'],truth8,64.);oracle=point_sum_visibility(old['uvw_lambda'],truth8);np.testing.assert_allclose(model,oracle,rtol=1e-12,atol=1e-10)
    if np.any(abs(model)<1e-14):raise ValueError('matched model at numerical zero; do not rescue by changing fixed sky')
    values,weights=idealize_visibility(old['visibilities'],old['weights'],model);new=partition_input(old,np.ones(8,bool));new['visibilities']=values;new['weights']=weights
    new['metadata'].update(evaluation_only=True,weights_are_artificial_snr_transport=True,control='noiseless quantized point sky on the same 8-pixel fitter grid; original sky changed')
    transfer,arrays=transport_diagnostic(old,new);assert transfer['independent_counts']=={'phase':117,'logamp':93};np.savez_compressed(out/'transport-detail.npz',**arrays)
    save_spectral(out/'control.npz',{k:new[k] for k in NUMERIC_FIELDS},new['metadata']);assert training_arrays_identity(load_spectral(out/'control.npz'))==training_arrays_identity(new)
    record={'input_files_sha256':inputs,'coarse_truth_sha256':sha(out/'truth8.npy'),'embedded_truth_sha256':sha(out/'embedded-truth.npy'),'control_archive_sha256':sha(out/'control.npz'),
            'transport_detail_sha256':sha(out/'transport-detail.npz'),'common_mask_sha256':sha(out/'common-baseline-mask.npy'),'transport':transfer,'coarse_truth_flux':float(truth8.sum()),
            'coarse_positive_pixels':int(np.count_nonzero(truth8)),'maximum_independent_point_sum_difference':float(np.max(abs(model-oracle))),
            'quantization':'nearest 64-arcsec point centers; ties toward positive coordinate; no clipping or dropped positive flux','same_physical_sky_as_original':False,'actual_observation_validated':False}
    (out/'generation.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n');return new,truth8,truth32,record


def score_matched(data,keep,image,summary,truth8,truth32):
    science,embedded=score_fit(data,keep,image,summary,truth32);oracle={};comparisons={}
    for support,mask in {'training':keep,'unused':~keep,'all':np.ones_like(keep)}.items():
        d,_=diagnose_image(partition_input(data,mask),truth8,pixel_arcsec=64.);oracle[support]=d
        if d['independent_count']:
            assert d['data_loss']<1e-20
            np.testing.assert_allclose(d['data_loss'],science['evaluation'][support]['truth']['data_loss'],rtol=1e-8,atol=1e-20)
            fit=science['evaluation'][support]['fit']['public_api']['metrics'];known=d['public_api']['metrics'];comparisons[support]={'oracle8_objective_minus_fitted_objective':known['objective']-fit['objective'],
                'oracle8_data_loss':known['data_loss'],'fitted_data_loss':fit['data_loss'],'same_grid_regularizer_compared':True}
        else:comparisons[support]=None
    science.update(coarse_oracle_evaluation=oracle,same_grid_objective_comparison=comparisons,embedded_32_regularizer_used_for_fitted_oracle_comparison=False)
    return science,embedded


def run(repository,reference,output):
    out=Path(output).resolve();data,truth8,truth32,generation=make_control(repository,reference,out);rows=[];splits=split_times(8)
    for label,mask in splits.items():
        directory=out/label;directory.mkdir();fitter=partition_input(data,mask);spectrum=directory/'training.npz';save_spectral(spectrum,{k:fitter[k] for k in NUMERIC_FIELDS},fitter['metadata']);summary=image_closure(spectrum,directory/'rml',**SETTINGS)
        rows.append({'split':label,'training_times':np.flatnonzero(mask).tolist(),'unused_times':np.flatnonzero(~mask).tolist(),'training_archive_sha256':sha(spectrum),'training_numeric_arrays':training_arrays_identity(fitter)})
        print(json.dumps({'split':label,'fit_complete':True,'selected_start':summary['selected_start']}),flush=True)
    for row in rows:
        directory=out/row['split'];image=np.load(directory/'rml/relative-model.npy',allow_pickle=False);summary=json.loads((directory/'rml/summary.json').read_text());science,embedded=score_matched(data,splits[row['split']],image,summary,truth8,truth32);np.save(directory/'embedded-model.npy',embedded)
        science.update(image_npy_sha256=sha(directory/'rml/relative-model.npy'),embedded_image_sha256=sha(directory/'embedded-model.npy'));row['science']=science;(directory/'science.json').write_text(json.dumps(science,indent=2,allow_nan=False)+'\n')
        print(json.dumps({'split':row['split'],'converged':science['selected_run_converged'],'train':science['evaluation']['training']['fit']['data_loss'],'unused':science['evaluation']['unused']['fit']['data_loss'],'nrmse':science['reference_metrics']['registered_nrmse']}),flush=True)
    assert all(sha(Path(reference)/n)==h for n,h in generation['input_files_sha256'].items());(out/'runtime-origins.json').write_text(json.dumps(module_origins(),indent=2)+'\n')
    result={'stage':127,'state':'complete','generation':generation,'cases':rows,'settings':SETTINGS,'fixed_new_fits':3,'starts_each':3,'residual_evaluations':27,'additional_coarse_oracle_evaluations':9,
            'limits':'Changed noiseless quantized sky on exactly the fitter point grid, artificially preserving a prior observation SNR/mask. Conditional time split, not original sky or independent raw/noise. Fixed old optimizer and hyperparameters; truth used in generator and post-evaluation, never in fitter input or run selection. Not low-SNR likelihood or real observation success.'}
    (out/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repository',required=True);p.add_argument('--reference',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.repository,a.reference,a.output)
