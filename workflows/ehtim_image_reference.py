"""w=0・人工weightの一条件で、nativeと外部RMLの実optimizerを対比較する。"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
from scipy.optimize import minimize
from scipy.special import softmax

# 検証workflowの再利用だけ。core sourceの探索pathは追加しない。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workflows.ehtim_conventions_validation import image_transfer, reference_observation_class, spectral_channels
from workflows.integration_image_validation import stable_rml_summary
from vsora_formats.spectral import load_spectral
from vsora_imaging.closure import form_closures, wrap_phase
from vsora_imaging.rml import fit_closure_image
from vsora_imaging.objective_evaluation import evaluate_closure_image
from vsora_imaging.experiment import compare_relative
from vsora_simulator.sky import synthetic_sky
from vsora_simulator.visibility import direct_visibility
from vsora_observation.geometry import ARCSEC_RAD, enu_to_ecef

SETTINGS={'pixels':8,'pixel_arcsec':64.,'prior_fwhm_arcsec':240.,'entropy':.01,'tsv':.0001,'centroid':.1,'min_snr':10.,'starts':3,'max_iterations':800,'seed':21}
EXTERNAL_DATA={'cphase':100.,'logcamp':100.}
EXTERNAL_REG={'simple':1.,'tv2':.1,'flux':10000.,'cm':.1}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def initial_images(pixels=8,pixel_arcsec=64.,starts=3,seed=21):
    if type(pixels) is not int or pixels<2 or type(starts) is not int or not 1<=starts<=8 or not np.isfinite(pixel_arcsec) or pixel_arcsec<=0:
        raise ValueError('valid grid, pixel scale and starts required')
    axis=(np.arange(pixels)-pixels//2)*pixel_arcsec; yy,xx=np.meshgrid(axis,axis,indexing='ij')
    prior=np.maximum(np.exp(-4*np.log(2)*(xx*xx+yy*yy)/240.**2),1e-12);prior/=prior.sum()
    rng=np.random.default_rng(seed);images=[]
    for start in range(starts):
        z=np.log(prior.ravel())+(0 if start==0 else rng.normal(0,.5,prior.size))
        images.append(softmax(z).reshape(prior.shape))
    return prior,np.asarray(images)


def capture_minimize(function,expected_calls):
    """呼出し・返り値は変更せず、実SciPyの終了状態と初期配列だけを読む。"""
    if type(expected_calls) is not int or expected_calls<1:raise ValueError('positive call count required')
    inputs=[];results=[];target=minimize.__code__;previous=sys.getprofile()
    def profile(frame,event,arg):
        if frame.f_code is target:
            if event=='call':inputs.append(np.asarray(frame.f_locals['x0']).copy())
            elif event=='return' and arg is not None:results.append(arg)
    sys.setprofile(profile)
    try: value=function()
    finally:sys.setprofile(previous)
    if len(inputs)!=expected_calls or len(results)!=expected_calls:raise ValueError('unexpected actual minimize call count')
    records=[]
    for result in results:
        if not np.isfinite(result.fun):raise ValueError('nonfinite optimizer objective')
        records.append({'optimizer_success':bool(result.success),'optimizer_status':int(result.status),'optimizer_message':str(result.message),
            'iterations':int(result.nit),'function_evaluations':int(result.nfev),'objective':float(result.fun)})
    return value,records,inputs


def matched_reference(data,truth,pixel_arcsec,seed=123):
    truth=np.asarray(truth)
    if truth.ndim!=2 or truth.shape[0]!=truth.shape[1] or min(truth.shape)<2 or np.iscomplexobj(truth) or not np.isfinite(truth).all() or np.any(truth<0) or not np.isfinite(truth.sum()) or truth.sum()<=0:
        raise ValueError('finite nonnegative reference image required')
    uvw=np.asarray(data['uvw_lambda']).copy()
    if np.iscomplexobj(uvw):raise ValueError('real reference geometry required')
    uvw[...,2]=0.
    old_values=np.asarray(data['visibilities']);old_weights=np.asarray(data['weights']);pairs=np.asarray(data['pairs'])
    if old_values.ndim!=3 or old_weights.shape!=old_values.shape or uvw.shape!=(*old_values.shape,3):raise ValueError('matching spectral arrays required')
    if not np.iscomplexobj(old_values) or any(not np.isfinite(x).all() for x in [old_values,old_weights,uvw]) or np.iscomplexobj(old_weights) or np.any(old_weights<0):raise ValueError('finite visibility and real nonnegative weights required')
    model=direct_visibility(uvw,truth,pixel_arcsec);rng=np.random.default_rng(seed);stations=int(pairs.max())+1
    gains=np.exp(rng.uniform(-1.,1.,(len(model),stations))+1j*rng.uniform(-np.pi,np.pi,(len(model),stations)))
    products=gains[:,pairs[:,0]]*gains[:,pairs[:,1]].conj();measured=model*products[:,None]
    snr=np.abs(old_values)*np.sqrt(old_weights);weights=np.zeros_like(old_weights,dtype=float)
    select=(snr>0)&(np.abs(measured)>1e-14);weights[select]=snr[select]**2/np.abs(measured[select])**2
    original=form_closures(old_values,old_weights,pairs,10.);reference=form_closures(measured,weights,pairs,10.)
    if not np.array_equal(original['baseline_valid'],reference['baseline_valid']):raise ValueError('reference changed common baseline mask')
    base=form_closures(model,weights*np.abs(products[:,None])**2,pairs,10.)
    differences={}
    for kind in ['phase','logamp']:
        valid=reference[kind+'_valid'];assert np.array_equal(valid,base[kind+'_valid'])
        delta=reference[kind]-base[kind];delta=wrap_phase(delta) if kind=='phase' else delta
        differences[kind]=float(np.max(np.abs(delta[valid])))
        assert differences[kind]<3e-11
    np.testing.assert_allclose(np.abs(measured)*np.sqrt(weights),snr,rtol=3e-14,atol=1e-12)
    result={'visibilities':measured,'weights':weights,'uvw_lambda':uvw,'pairs':pairs.copy(),'times_s':data['times_s'].copy(),'frequencies_hz':data['frequencies_hz'].copy()}
    if 'integration_s' in data:
        integration=np.asarray(data['integration_s'])
        if integration.shape!=(len(old_values),len(pairs)) or np.iscomplexobj(integration) or not np.isfinite(integration).all() or np.any(integration<=0):
            raise ValueError('positive integration seconds per time/baseline required')
        result['integration_s']=integration.copy()
    return result,gains,differences


def prepare(repository,output):
    root=Path(repository).resolve();out=Path(output);out.mkdir(parents=True,exist_ok=False)
    prior_record=json.loads((root/'validation/runs/stage119/reference.json').read_text());row=next(x for x in prior_record['cases'] if x['pixels']==8 and x['branch']=='truth_rate_control')
    path=root/row['spectrum'];assert sha(path)==row['input_sha256'];source=load_spectral(path)
    config=deepcopy(source['metadata']['config']);config['image'].update(pixels=8,pixel_arcsec=64.);config['source'].update(model='casa',total_flux_jy=1.)
    truth=synthetic_sky(config);data,gains,gain_diff=matched_reference(source,truth,64.)
    assert 'integration_s' in data
    prior,starts=initial_images();arrays={**data,'prior':prior,'initial_images':starts}
    # fitter用bundleにはtruth/gainを入れない。
    np.savez_compressed(out/'input.npz',**arrays);np.save(out/'truth.npy',truth);np.save(out/'generation-gains.npy',gains)
    metadata={'settings':SETTINGS,'external_data':EXTERNAL_DATA,'external_reg':EXTERNAL_REG,'external_stop':1e-11,'external_maxset':False,
        'reference_unit':'arbitrary relative scalar visibility; not calibrated Jy or Stokes I','source_input':row['spectrum'],'source_sha256':row['input_sha256'],
        'site':config['site'],'stations':config['stations'],'source_direction':{k:config['source'][k] for k in ['ra_deg','dec_deg']},
        'input_sha256':sha(out/'input.npz'),'truth_sha256':sha(out/'truth.npy'),'generation_gains_sha256':sha(out/'generation-gains.npy'),
        'integration_s_range':[float(data['integration_s'].min()),float(data['integration_s'].max())],'times_s_range':[float(data['times_s'].min()),float(data['times_s'].max())],
        'reference_gain_seed':123,'common_mask_preserved':True,'station_gain_maximum_closure_difference':gain_diff,
        'physical_receiver_noise_generated':False,'w_zero_control_only':True,'truth_and_gain_in_fitter_input':False,'actual_observation_validated':False}
    (out/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n');return metadata


def load_input(reference):
    reference=Path(reference);metadata=json.loads((reference/'metadata.json').read_text());assert sha(reference/'input.npz')==metadata['input_sha256']
    with np.load(reference/'input.npz',allow_pickle=False) as f:data={k:f[k] for k in f.files}
    assert not any(k in data for k in ['truth','gain','gains']);return metadata,data


def native(reference,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);metadata,data=load_input(reference);began=time.monotonic()
    value,records,initials=capture_minimize(lambda:fit_closure_image(data['uvw_lambda'],data['visibilities'],data['weights'],data['pairs'],**SETTINGS),6)
    image,summary=value
    for i in range(3):np.testing.assert_allclose(initials[2*i],data['initial_images'][i].ravel(),rtol=1e-14,atol=1e-16)
    np.save(out/'relative-model.npy',image)
    science={'state':'complete','method':'native','input_sha256':metadata['input_sha256'],'summary':stable_rml_summary(summary),'actual_optimizer_calls':records,
        'initial_image_maximum_difference':float(max(np.max(np.abs(initials[2*i]-data['initial_images'][i].ravel())) for i in range(3))),
        'image_sha256':sha(out/'relative-model.npy'),'actual_observation_validated':False}
    (out/'science.json').write_text(json.dumps(science,indent=2)+'\n');(out/'timing.json').write_text(json.dumps({'elapsed_s':time.monotonic()-began})+'\n');return science


def external_problem(reference):
    import ehtim as eh
    import ehtim.const_def as constants
    from ehtim.observing.pulses import deltaPulse2D
    from astropy.coordinates import EarthLocation
    import astropy.units as units
    metadata,data=load_input(reference)
    cls=reference_observation_class();stations=metadata['stations'];site=metadata['site'];n=len(stations)
    location=EarthLocation.from_geodetic(site['longitude_deg']*units.deg,site['latitude_deg']*units.deg,site['height_m']*units.m)
    origin=np.array([v.to_value(units.m) for v in location.geocentric]);positions=origin+enu_to_ecef([s['enu_m'] for s in stations],site['latitude_deg'],site['longitude_deg'])
    tarr=np.zeros(n,dtype=constants.DTARR);tarr['site']=[f'S{i:02d}' for i in range(n)];tarr['x'],tarr['y'],tarr['z']=positions.T;tarr['sefdr']=1.;tarr['sefdl']=1.
    observations=[];channels=[]
    for index,channel in enumerate(spectral_channels(data)):
        count=len(channel['vis_relative']);channels.append({'channel_index':index,'frequency_hz':channel['frequency_hz'],'rows':count})
        if not count:continue
        table=np.zeros(count,dtype=constants.DTPOL_STOKES);table['time']=channel['time_hours'];table['tint']=data['integration_s'][channel['time_index'],channel['baseline_index']]
        table['t1']=[f'S{i:02d}' for i in channel['pairs'][:,0]];table['t2']=[f'S{i:02d}' for i in channel['pairs'][:,1]]
        table['u'],table['v']=channel['uv_eht'].T;table['vis']=channel['vis_relative']
        for name in ['sigma','qsigma','usigma','vsigma']:table[name]=channel['sigma_relative_per_quadrature']
        obs=cls(metadata['source_direction']['ra_deg']/15.,metadata['source_direction']['dec_deg'],channel['frequency_hz'],256000.,table,tarr.copy(),mjd=61315,source='w0 scalar reference',ampcal=False,phasecal=False)
        assert len(obs.c_phases()) and len(obs.c_amplitudes(ctype='logcamp',debias=False));observations.append(obs)
    assert len(observations)==3
    def image_object(image):
        return eh.image.Image(image[::-1,::-1].copy(),64.*ARCSEC_RAD,metadata['source_direction']['ra_deg']/15.,metadata['source_direction']['dec_deg'],rf=1.42e9,pulse=deltaPulse2D)
    return metadata,data,observations,channels,image_object


def external_imager(problem,initial_image,max_iterations=800):
    """同じ外部参照条件を組み立て、反復上限だけを明示的に変えられる。"""
    if type(max_iterations) is not int or not 1<=max_iterations<=5000:
        raise ValueError('external iterations must be 1..5000')
    import ehtim as eh
    metadata,data,observations,channels,image_object=problem
    return eh.imager.Imager(observations,image_object(initial_image),prior_im=image_object(data['prior']),flux=1.,data_term=EXTERNAL_DATA,reg_term=EXTERNAL_REG,
        maxit=max_iterations,stop=1e-11,ttype='direct',debias=False,snrcut=0.,maxset=False,weighting='natural',clipfloor=0.,norm_init=True,norm_reg=True,transform=['log'],pol='I')


def external(reference,output,max_iterations=800):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    problem=external_problem(reference);metadata,data,observations,channels,image_object=problem
    # actual geometry上で、半画素の位相差がw=0のClosureから消えることも直接確認。
    observed=form_closures(data['visibilities'],data['weights'],data['pairs'],10.)
    transfer_checks=[]
    for image in [data['prior'],*data['initial_images']]:
        _,uv,correction=image_transfer(image,data['uvw_lambda'],64.)
        sampled=image_object(image).sample_uv(uv.reshape(-1,2),ttype='direct',verbose=False)[0].reshape(data['visibilities'].shape)
        predicted=direct_visibility(data['uvw_lambda'],image,64.)
        np.testing.assert_allclose(sampled*correction,predicted,rtol=3e-12,atol=3e-14)
        row={'maximum_corrected_visibility_difference':float(np.max(np.abs(sampled*correction-predicted)))}
        for kind in ['phase','logamp']:
            left=np.angle(sampled) if kind=='phase' else np.log(np.abs(sampled))
            right=np.angle(predicted) if kind=='phase' else np.log(np.abs(predicted))
            delta=(left-right) @ observed[kind+'_matrix'].T
            if kind=='phase':delta=wrap_phase(delta)
            difference=float(np.max(np.abs(delta[observed[kind+'_valid']])))
            assert difference<3e-10;row[kind+'_closure_maximum_difference']=difference
        transfer_checks.append(row)
    runs=[];models=[]
    for start,image in enumerate(data['initial_images']):
        imager=external_imager(problem,image,max_iterations)
        began=time.monotonic();result,records,initials=capture_minimize(lambda:imager.make_image(pol='I',show_updates=False),1)
        np.testing.assert_allclose(np.exp(initials[0]).reshape(8,8)[::-1,::-1],image,rtol=3e-14,atol=1e-16)
        np.testing.assert_array_equal(result.imvec,imager.out_last().imvec)
        raw=result.imvec.reshape(8,8)[::-1,::-1].copy()
        if not np.isfinite(raw).all() or np.any(raw<0) or not np.isfinite(raw.sum()) or raw.sum()<=0:raise ValueError('external did not return a valid relative image')
        q=raw/raw.sum();np.save(out/f'start-{start}.npy',q);models.append(q)
        chisq={k:float(v) for k,v in imager.make_chisq_dict(result.imvec).items()}
        regularizers={k:float(v) for k,v in imager.make_reg_dict(result.imvec).items()}
        runs.append({'start':start,**records[0],'external_chisq_terms':chisq,'external_regularizer_terms':regularizers,'image_flux_before_gauge_normalization':float(raw.sum()),
            'initial_image_maximum_difference':float(np.max(np.abs(np.exp(initials[0]).reshape(8,8)[::-1,::-1]-image)))})
        print(json.dumps({'start':start,'optimizer_success':records[0]['optimizer_success'],'iterations':records[0]['iterations']}),flush=True)
    selected=int(np.argmin([r['objective'] for r in runs]));np.save(out/'relative-model.npy',models[selected])
    result={'state':'complete','method':'ehtim1.3.2','input_sha256':metadata['input_sha256'],'selected_start':selected,'runs':runs,
        'channels':channels,'half_pixel_closure_checks':transfer_checks,'fitted_frequency_groups':len(observations),'data_term':EXTERNAL_DATA,'reg_term':EXTERNAL_REG,
        'optimizer_args':{'maxit':max_iterations,'stop':1e-11,'ttype':'direct','debias':False,'maxset':False,'norm_reg':True},
        'image_sha256':sha(out/'relative-model.npy'),'optimizer_results_observed_without_modification':True,'physical_jy_or_stokes_calibration_performed':False,'actual_observation_validated':False}
    (out/'science.json').write_text(json.dumps(result,indent=2)+'\n');return result


def assess(reference,native_output,external_output,output):
    ref=Path(reference);out=Path(output);out.mkdir(parents=True,exist_ok=False);metadata,data=load_input(ref);assert sha(ref/'truth.npy')==metadata['truth_sha256'];truth=np.load(ref/'truth.npy',allow_pickle=False)
    candidates={'truth':truth,'prior':data['prior'],'native':np.load(Path(native_output)/'relative-model.npy',allow_pickle=False),'ehtim':np.load(Path(external_output)/'relative-model.npy',allow_pickle=False)};results={}
    settings={k:SETTINGS[k] for k in ['pixel_arcsec','prior_fwhm_arcsec','min_snr','entropy','tsv','centroid']}
    for name,image in candidates.items():
        cost=evaluate_closure_image(data['uvw_lambda'],data['visibilities'],data['weights'],data['pairs'],image,**settings)
        metrics,_,_,_=compare_relative(truth,image,64.)
        results[name]={'native_common_objective':cost,'reference_metrics':metrics}
    result={'stage':123,'state':'complete','candidates':results,'input_sha256':metadata['input_sha256'],'w_zero_control_only':True,'physical_receiver_noise_generated':False,'image_methods_ranked_by_truth':False,'actual_observation_validated':False}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['prepare','native','external','assess'],required=True);p.add_argument('--repository');p.add_argument('--reference');p.add_argument('--native-output');p.add_argument('--external-output');p.add_argument('--external-max-iterations',type=int,default=800);p.add_argument('--output',required=True);a=p.parse_args()
    functions={'prepare':lambda:prepare(a.repository,a.output),'native':lambda:native(a.reference,a.output),'external':lambda:external(a.reference,a.output,a.external_max_iterations),'assess':lambda:assess(a.reference,a.native_output,a.external_output,a.output)}
    value=functions[a.mode]();print(json.dumps({'state':value.get('state','complete'),'mode':a.mode}))


if __name__=='__main__':main()
