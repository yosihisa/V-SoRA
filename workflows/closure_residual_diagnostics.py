"""保存済み画像入力のClosure残差を、再相関・再fitせずに分解する。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflows.rate_acquisition_validation import arrays_identity
from vsora_formats.spectral import load_spectral,save_spectral
from vsora_imaging.closure import form_closures,independent_closures,wrap_phase
from vsora_imaging.objective_evaluation import evaluate_closure_image
from vsora_simulator.visibility import direct_visibility

SETTINGS={'pixel_arcsec':16.,'min_snr':10.,'prior_fwhm_arcsec':240.,'entropy':.01,'tsv':.0001,'centroid':.1}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def common_baseline_mask(datasets,min_snr=10.):
    if not datasets:raise ValueError('at least one spectral dataset required')
    first=datasets[0];masks=[]
    for d in datasets:
        for name in ['pairs','times_s','frequencies_hz','uvw_lambda']:
            if not np.array_equal(d[name],first[name]):raise ValueError('common support requires identical spectral axes and geometry')
        masks.append(form_closures(d['visibilities'],d['weights'],d['pairs'],min_snr)['baseline_valid'])
    return np.logical_and.reduce(masks)


def diagnose_image(data,image,**settings):
    options={**SETTINGS,**settings};q=np.asarray(image)
    if (q.ndim!=2 or q.shape[0]!=q.shape[1] or not 8<=len(q)<=64 or np.iscomplexobj(q)
            or not np.issubdtype(q.dtype,np.number) or not np.isfinite(q).all() or np.any(q<0) or not np.isfinite(q.sum()) or q.sum()<=0):
        raise ValueError('finite nonnegative positive-sum square 8..64 image required')
    q=q.astype(float)/q.sum();values=np.asarray(data['visibilities']);weights=np.asarray(data['weights']);uvw=np.asarray(data['uvw_lambda'])
    if values.ndim!=3 or uvw.shape!=(*values.shape,3) or np.iscomplexobj(uvw) or not np.isfinite(uvw).all() or np.iscomplexobj(weights):
        raise ValueError('real finite matching spectral geometry and weights required')
    c=form_closures(values,weights,data['pairs'],options['min_snr']);model=direct_visibility(uvw,q,options['pixel_arcsec'])
    if np.any(np.abs(model)<1e-14):raise ValueError('model visibility at numerical zero; change initial image')
    arrays={'model_visibilities':model,'baseline_valid':c['baseline_valid'],'independent_used_baseline_mask':np.zeros_like(c['baseline_valid'])};cells=[];counts={'phase':0,'logamp':0};energy={'phase':0.,'logamp':0.};fingerprint=hashlib.sha256();indices_fingerprint=hashlib.sha256()
    for t in range(values.shape[0]):
        for f in range(values.shape[1]):
            cell={'time_index':t,'frequency_index':f};cell_count=0;cell_energy=0.
            for kind in ['phase','logamp']:
                indices,cov=independent_closures(c[kind+'_matrix'],c[kind+'_valid'][t,f],c['baseline_variance'][t,f])
                matrix=c[kind+'_matrix'][indices];prefix=f't{t:03d}_f{f:03d}_{kind}'
                arrays[prefix+'_indices']=indices;arrays[prefix+'_matrix']=matrix;arrays[prefix+'_covariance']=cov
                marker=f'{t}:{f}:{kind}'.encode();indices_fingerprint.update(marker+indices.tobytes());fingerprint.update(marker+indices.tobytes()+matrix.tobytes()+cov.tobytes())
                if not len(indices):
                    arrays[prefix+'_residual']=np.empty(0);arrays[prefix+'_whitened']=np.empty(0)
                    cell[kind]={'state':'no_constraints','independent_count':0,'chi2_approx':None,'maximum_absolute_residual':None}
                    continue
                arrays['independent_used_baseline_mask'][t,f] |= np.any(matrix!=0,axis=0)
                predicted=matrix @ (np.angle(model[t,f]) if kind=='phase' else np.log(np.abs(model[t,f])))
                residual=predicted-c[kind][t,f,indices]
                if kind=='phase':residual=wrap_phase(residual)
                whitened=np.linalg.solve(np.linalg.cholesky(cov),residual);chi=float(whitened @ whitened)
                if not np.isfinite(chi):raise ValueError('nonfinite closure residual energy')
                arrays[prefix+'_residual']=residual;arrays[prefix+'_whitened']=whitened
                cell[kind]={'state':'available','independent_count':len(indices),'chi2_approx':chi,'maximum_absolute_residual':float(np.max(np.abs(residual)))}
                counts[kind]+=len(indices);energy[kind]+=chi;cell_count+=len(indices);cell_energy+=chi
            cell.update(state='available' if cell_count else 'no_constraints',independent_count=cell_count,chi2_approx=cell_energy if cell_count else None,local_data_loss=.5*cell_energy/cell_count if cell_count else None);cells.append(cell)
    total=sum(counts.values());total_energy=sum(energy.values()) if total else None
    summary={'schema_version':1,'type':'fixed_image_closure_residual_diagnostic','state':'complete' if total else 'insufficient_constraints',
        'independent_counts':counts,'independent_count':total,'chi2_approx':total_energy,'data_loss':.5*total_energy/total if total else None,
        'component_chi2_approx':{k:energy[k] if counts[k] else None for k in counts},'baseline_valid_count':int(c['baseline_valid'].sum()),'independent_used_baseline_count':int(arrays['independent_used_baseline_mask'].sum()),
        'all_cell_count':len(cells),'cells_with_constraints':sum(x['state']=='available' for x in cells),'cells':cells,
        'basis_and_covariance_sha256':fingerprint.hexdigest(),'basis_indices_sha256':indices_fingerprint.hexdigest(),'settings':options,
        'optimizer_executed':False,'p_value_computed':False,'low_snr_likelihood_validated':False,'actual_observation_validated':False}
    if total:
        api=evaluate_closure_image(uvw,values,weights,data['pairs'],image,**options);m=api['metrics']
        assert m['independent_closure_count']==total and m['independent_closure_counts']==counts
        np.testing.assert_allclose(summary['data_loss'],m['data_loss'],rtol=1e-9,atol=1e-10)
        np.testing.assert_allclose(total_energy/total,m['closure_chisq_per_measurement'],rtol=1e-9,atol=1e-10)
        weighted=sum(x['independent_count']*x['local_data_loss'] for x in cells if x['state']=='available')/total
        np.testing.assert_allclose(weighted,summary['data_loss'],rtol=1e-12,atol=1e-13)
        summary.update(public_api=api,public_data_loss_absolute_difference=abs(summary['data_loss']-m['data_loss']))
    else:summary.update(public_api=None,public_data_loss_absolute_difference=None)
    return summary,arrays


def run(repository,reference,output):
    root=Path(repository).resolve();ref=Path(reference).resolve();out=Path(output);out.mkdir(parents=True,exist_ok=False)
    origins={name:str(Path(__import__(name).__file__).resolve()) for name in ['vsora_imaging','vsora_formats','vsora_simulator','vsora_observation']}
    (out/'runtime-origins.json').write_text(json.dumps(origins,indent=2)+'\n')
    old=json.loads((root/'validation/runs/stage118/reference.json').read_text());later=json.loads((root/'validation/runs/stage119/reference.json').read_text())
    earlier=json.loads((root/'validation/runs/stage113/reference.json').read_text());truth_path=ref/'truth.npy';assert sha(truth_path)==earlier['truth_npy_sha256'];truth=np.load(truth_path,allow_pickle=False)
    branches=old['branches'];loaded=[];inputs={'truth.npy':sha(truth_path)}
    for branch in branches:
        name=branch['branch'];spectrum=ref/name/'visibility.npz';fit=ref/name/'rml/relative-model.npy'
        digest=next(x['input_sha256'] for x in later['cases'] if x['branch']==name and x['pixels']==32)
        assert sha(spectrum)==digest and sha(fit)==branch['science']['image_sha256']
        d=load_spectral(spectrum);assert arrays_identity(d)==branch['science']['input_arrays'];loaded.append(d)
        inputs[name+'/visibility.npz']=digest;inputs[name+'/rml/relative-model.npy']=sha(fit)
    common=common_baseline_mask(loaded);np.save(out/'common-baseline-mask.npy',common)
    axis=(np.arange(32)-16)*16.;yy,xx=np.meshgrid(axis,axis,indexing='ij');prior=np.maximum(np.exp(-4*np.log(2)*(xx*xx+yy*yy)/240.**2),1e-12);prior/=prior.sum()
    records=[]
    for branch,data in zip(branches,loaded,strict=True):
        name=branch['branch'];fit=np.load(ref/name/'rml/relative-model.npy',allow_pickle=False)
        for support in ['original','common_baselines']:
            diagnostic_data={**data,'weights':data['weights'].copy() if support=='original' else np.where(common,data['weights'],0.)}
            baseline_valid=form_closures(diagnostic_data['visibilities'],diagnostic_data['weights'],data['pairs'],10.)['baseline_valid']
            if support=='common_baselines':np.testing.assert_array_equal(baseline_valid,common)
            support_dir=out/name/support;support_dir.mkdir(parents=True)
            derived=support_dir/'diagnostic-input.npz'
            save_spectral(derived,{k:v for k,v in diagnostic_data.items() if k!='metadata'},{**data['metadata'],'diagnostic_support':support,'diagnostic_source_archive_sha256':inputs[name+'/visibility.npz']})
            assert arrays_identity(load_spectral(derived))==arrays_identity(diagnostic_data)
            for candidate,image in [('truth',truth),('prior',prior),('own_fitted',fit)]:
                directory=out/name/support/candidate;directory.mkdir(parents=True)
                np.save(directory/'candidate.npy',image)
                diagnostic,arrays=diagnose_image(diagnostic_data,image)
                if support=='original':
                    public=branch['science']['candidate_objectives'][{'own_fitted':'fitted'}.get(candidate,candidate)]['metrics']
                    for key in ['data_loss','closure_chisq_per_measurement']:
                        np.testing.assert_allclose(diagnostic['public_api']['metrics'][key],public[key],rtol=1e-12,atol=1e-12)
                used=arrays['independent_used_baseline_mask']
                geometric_m=np.linalg.norm(data['uvw_lambda'],axis=-1)*299792458./data['frequencies_hz'][None,:,None]
                projected_lambda=np.linalg.norm(data['uvw_lambda'][...,:2],axis=-1)
                diagnostic['used_geometry']={'maximum_baseline_m':float(geometric_m[used].max()) if used.any() else None,
                    'maximum_projected_uv_lambda':float(projected_lambda[used].max()) if used.any() else None,
                    'interpretation':'baseline geometry participating in selected independent rows, not a measured angular resolution'}
                np.savez_compressed(directory/'detail.npz',**arrays)
                record={'branch':name,'support':support,'candidate':candidate,'input_sha256':inputs[name+'/visibility.npz'],
                    'diagnostic_input_sha256':sha(derived),'candidate_npy_sha256':sha(directory/'candidate.npy'),
                    'candidate_array_sha256':hashlib.sha256(np.ascontiguousarray(image).tobytes()).hexdigest(),'detail_sha256':sha(directory/'detail.npz'),
                    'diagnostic':diagnostic,'metadata':{'visibility_unit':data['metadata']['visibility_unit'],'truth_information':branch['truth_information'],
                        'weights_are_artificial_snr_transport':bool(data['metadata'].get('weights_are_artificial_snr_transport',False))}}
                (directory/'diagnostic.json').write_text(json.dumps(record,indent=2)+'\n');records.append(record)
                print(json.dumps({'branch':name,'support':support,'candidate':candidate,'loss':diagnostic['data_loss']}),flush=True)
    # 同じbranch/supportの基底は候補画像で変わらない。共通支持のcountもbranch間で一致。
    for branch in branches:
        for support in ['original','common_baselines']:
            subset=[x['diagnostic'] for x in records if x['branch']==branch['branch'] and x['support']==support]
            assert len({x['basis_and_covariance_sha256'] for x in subset})==1
    counts=[x['diagnostic']['independent_counts'] for x in records if x['support']=='common_baselines' and x['candidate']=='truth'];assert all(x==counts[0] for x in counts)
    for name,digest in inputs.items():assert sha(ref/name)==digest
    result={'stage':125,'state':'complete','cases':records,'case_count':18,'input_files_sha256':inputs,
        'common_baseline_mask_sha256':sha(out/'common-baseline-mask.npy'),'common_valid_baselines':int(common.sum()),'same_axes_and_geometry_verified':True,
        'common_support_counts_identical':True,'common_basis_indices_identical':len({x['diagnostic']['basis_indices_sha256'] for x in records if x['support']=='common_baselines'})==1,
        'new_correlation_or_image_fit_executed':False,'p_value_computed':False,'actual_observation_validated':False,
        'limits':'Fixed observed high-SNR baseline-independent covariance approximation. SNR selection and weights come from the same data. Common baseline support preserves branch covariance and QR-selected basis; phase wrapping can make basis changes material. Whitened coordinates are not compared by row number. No chi-square distribution, coverage, causal physical explanation or real observation success certified.'}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repository',required=True);p.add_argument('--reference',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.repository,a.reference,a.output)
