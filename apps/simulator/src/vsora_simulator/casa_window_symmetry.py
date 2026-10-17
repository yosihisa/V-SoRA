"""Known finite Gaussian modes and conditional window symmetry; no image test."""
from functools import lru_cache
import argparse
import hashlib
import json
from pathlib import Path
import re
import numpy as np
from vsora_observation.reference import reference_path
from vsora_imaging.window_symmetry import exact_window_sign_flip_test
from .sky import synthetic_sky
from .sky_covariance import sky_station_covariance
from .bispectrum_observed_power import observed_power_normalized_bispectrum

MODES=('point','casa','zero','heterogeneous_point','equal_double','unequal_double',
       'quadratic_phase','known_inverse','copied_windows')
PHASE_COEFFICIENTS=np.array([0.,.9,-.7,1.3,-1.1,.6,-.4,1.5])


@lru_cache(maxsize=1)
def _config():
    asset=reference_path('known-casa-window-symmetry.json')
    q=json.loads(asset.read_text())
    if q['schema_version']!=1 or q['assumed_frequency_hz']!=1.42e9:
        raise ValueError('supported fixed known-sky configuration required')
    actual=hashlib.sha256(reference_path().read_bytes()).hexdigest()
    if actual!=q['reference']['derived_sha256']:
        raise ValueError('known sky reference SHA mismatch')
    return q


@lru_cache(maxsize=8)
def _sky(mode):
    cfg=_config();size=cfg['image_pixels'];flux=cfg['assumed_source_total_flux_jy']
    if mode in ('equal_double','unequal_double'):
        image=np.zeros((size,size));fraction=.5 if mode=='equal_double' else .75
        image[size//2,size//2-2]=fraction*flux
        image[size//2,size//2+2]=(1-fraction)*flux
    elif mode=='zero':image=np.zeros((size,size))
    else:
        base=json.loads(reference_path('known-array-scale-config.json').read_text())
        ra,dec=cfg['assumed_source_icrs_deg']
        base['source'].update(model=mode,frame='icrs',ra_deg=ra,dec_deg=dec,total_flux_jy=flux)
        base['image']={'pixels':size,'pixel_arcsec':cfg['image_pixel_arcsec']}
        image=synthetic_sky(base)
    image.setflags(write=False);return image


@lru_cache(maxsize=64)
def _known_model(mode,maximum,sefd):
    base_mode=mode if mode in ('casa','zero','equal_double','unequal_double') else 'point'
    cfg=_config();geometry=next(r for r in cfg['geometry'] if r['maximum_baseline_m']==maximum)
    coords=np.asarray(geometry['station_uvw_lambda'])
    q=sky_station_covariance(coords,_sky(base_mode),cfg['image_pixel_arcsec'],np.asarray(sefd))
    s=q['station_covariance_jy'];root=np.linalg.cholesky(s)
    phase=np.exp(-1j*np.angle(s[:,0]));gauged=phase[:,None]*s*phase.conj()[None,:]
    residual=float(np.max(abs(gauged.imag))/np.max(abs(s)))
    if base_mode=='casa':
        pairs=np.asarray(geometry['pairs']);expected=np.asarray(geometry['known_casa_visibility_jy_real_imag'])
        expected=expected[:,0]+1j*expected[:,1]
        np.testing.assert_allclose(q['source_covariance_jy'][pairs[:,0],pairs[:,1]],expected,rtol=1e-12,atol=1e-9)
    s.setflags(write=False);root.setflags(write=False)
    return s,root,residual,float(_sky(base_mode).sum())


def case_plan(profile='full'):
    if profile not in ('full','smoke'):raise ValueError('full or smoke profile required')
    cases=[]
    # Preserve the exact receiver example from the established area/Tsys API.
    from .sensitivity import sefd_from_area,dish_area
    large=sefd_from_area(100.,dish_area(1.,.6))
    def add(mode,maximum,modes,sefd,trials):
        n=len(cases)
        cases.append({'case_id':f'c{n:03d}-{mode}','mode':mode,'maximum_baseline_m':maximum,
                      'modes':modes,'windows':8,'receiver_sefd_jy':[float(sefd)]*8,
                      'trials':trials,'seed':8700+n,'formal_mc_precision':True})
    for modes in (128,512):
        for maximum in (25.,100.,600.):
            for sefd in (1000.,10000.,large):
                for mode in ('point','casa'):add(mode,maximum,modes,sefd,1024)
    for maximum in (100.,600.):
        for sefd in (1000.,large):
            for mode in ('point','casa'):add(mode,maximum,19200,sefd,256)
    for mode in ('point','casa'):add(mode,600.,19200,10000.,256)
    for mode in ('zero','heterogeneous_point','equal_double','unequal_double','quadratic_phase','known_inverse','copied_windows'):
        add(mode,600.,512,1000.,1024)
    cases[47]['receiver_sefd_jy']=[1000.,2000.,4000.,8000.]*2
    for index in (50,51):cases[index]['seed']=cases[30]['seed']
    assert len(cases)==53
    if profile=='smoke':
        selected=[]
        for n,index in enumerate((30,31,52)):
            c=cases[index].copy();c.update(case_id=f'smoke-{n}-{c["mode"]}',modes=16,trials=16,formal_mc_precision=False)
            selected.append(c)
        return selected
    return cases


def _validate_case(case):
    if not isinstance(case,dict):raise ValueError('fixed case dictionary required')
    for key,low,high in (('modes',3,19200),('windows',1,12),('trials',2,4096),('seed',0,2**32-1)):
        value=case.get(key)
        if isinstance(value,bool) or not isinstance(value,int) or not low<=value<=high:
            raise ValueError('supported integer '+key+' required')
    if case.get('mode') not in MODES or case.get('maximum_baseline_m') not in (25.,100.,600.):
        raise ValueError('supported known model and frozen geometry required')
    if not isinstance(case.get('case_id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]+',case['case_id']):
        raise ValueError('safe fixed case identifier required')
    if np.ma.isMaskedArray(case.get('receiver_sefd_jy')):raise ValueError('unmasked receiver model required')
    noise=np.asarray(case.get('receiver_sefd_jy'))
    if (noise.shape!=(8,) or np.iscomplexobj(noise) or not np.issubdtype(noise.dtype,np.number)
        or not np.isfinite(noise).all() or np.any(noise<100) or np.any(noise>1e7)):
        raise ValueError('eight finite receiver powers100..1e7 Jy required')
    if not isinstance(case.get('formal_mc_precision'),bool):raise ValueError('explicit precision profile required')
    if case['formal_mc_precision'] and case['trials']<256:raise ValueError('formal precision needs at least256 trials')


def experiment(case):
    _validate_case(case)
    mode=case['mode'];m=case['modes'];windows=case['windows'];trials=case['trials']
    s,root,gauge_residual,flux=_known_model(mode,case['maximum_baseline_m'],tuple(case['receiver_sefd_jy']))
    null_supported=mode in ('point','zero','heterogeneous_point','equal_double','known_inverse')
    if null_supported and gauge_residual>1e-10:raise RuntimeError('generating null lacks a real station gauge')
    rng=np.random.default_rng(case['seed']);gain_rng=np.random.default_rng(case['seed']+100000)
    phase=np.exp(1j*(((np.arange(m)-(m-1)/2)/(m/2))**2)[:,None]*PHASE_COEFFICIENTS[None,:])
    pvalues=[];tails=[];trial_means=[];max_gain_error=0.;max_conjugation_error=0.;max_inverse_error=0.;gain_p_ok=True
    batch=min(16,max(1,1000000//(windows*m*8)));gain_checks=0
    for start in range(0,trials,batch):
        n=min(batch,trials-start);draw_windows=1 if mode=='copied_windows' else windows
        shape=(n,draw_windows,m,8)
        z=(rng.normal(size=shape)+1j*rng.normal(size=shape))/np.sqrt(2)
        x=z @ root.T
        if mode=='copied_windows':x=np.repeat(x,windows,axis=1)
        uncorrected=None
        if mode in ('quadratic_phase','known_inverse'):
            if mode=='known_inverse':uncorrected=x
            x=x*phase[None,None,:,:]
            if mode=='known_inverse':x=x*phase.conj()[None,None,:,:]
        values=observed_power_normalized_bispectrum(x)['observed_power_normalized_u3']
        if uncorrected is not None:
            baseline=observed_power_normalized_bispectrum(uncorrected)['observed_power_normalized_u3']
            max_inverse_error=max(max_inverse_error,float(np.max(abs(values-baseline))))
        vectors=values.imag
        results=[exact_window_sign_flip_test(v) for v in vectors]
        pvalues.extend(r['upper_tail_p_value'] for r in results);tails.extend(r['tail_count'] for r in results)
        trial_means.append(vectors.mean(axis=1))
        check=min(n,max(0,4-start))
        if check:
            gains=np.exp(gain_rng.uniform(-.8,.8,size=(check,windows,8))
                         +1j*gain_rng.uniform(-np.pi,np.pi,size=(check,windows,8)))
            changed=observed_power_normalized_bispectrum(x[:check]*gains[:,:,None,:])['observed_power_normalized_u3']
            max_gain_error=max(max_gain_error,float(np.max(abs(changed-values[:check]))))
            changed_p=[exact_window_sign_flip_test(v)['upper_tail_p_value'] for v in changed.imag]
            gain_p_ok=gain_p_ok and changed_p==[r['upper_tail_p_value'] for r in results[:check]]
            conjugated=x[:check].copy();conjugated[:,::2]=conjugated[:,::2].conj()
            transported=observed_power_normalized_bispectrum(conjugated)['observed_power_normalized_u3']
            expected=values[:check].copy();expected[:,::2]=expected[:,::2].conj()
            max_conjugation_error=max(max_conjugation_error,float(np.max(abs(transported-expected))))
            gain_checks+=check
    p=np.asarray(pvalues);means=np.concatenate(trial_means);tail_counts,counts=np.unique(tails,return_counts=True)
    levels=[]
    for alpha in (.01,.05):
        rejected=int(np.count_nonzero(p<=alpha));fraction=rejected/trials
        reference_se=float(np.sqrt(alpha*(1-alpha)/trials));applies=null_supported and case['formal_mc_precision']
        levels.append({'nominal_level':alpha,'rejections':rejected,'fraction':fraction,
                       'reference_binomial_mc_se_at_nominal':reference_se,
                       'null_mc_check_applied':applies,
                       'within_nominal_plus_6_reference_se':bool(fraction<=alpha+6*reference_se) if applies else None})
    minimum=2/(1 << windows)
    numerical_ok=max_gain_error<=2e-12 and max_conjugation_error<=2e-12 and max_inverse_error<=2e-12 and gain_p_ok
    copy_ok=bool(np.all(p==minimum)) if mode=='copied_windows' else True
    passed=bool(numerical_ok and copy_ok and all(r['within_nominal_plus_6_reference_se'] is not False for r in levels))
    return {**case,'state':'complete' if passed else 'failed_validation','station_covariance_real_imag':np.stack((s.real,s.imag),axis=-1).tolist(),
            'assumed_source_flux_jy':flux,'spatial_covariance_real_gauge_relative_residual':gauge_residual,
            'joint_null_invariance_supported_by_generation':null_supported,
            'window_draws_independent':mode!='copied_windows','independent_modes_assumed':True,
            'within_window_station_gain_constant_assumed':mode not in ('quadratic_phase','known_inverse'),
            'synthetic_quadratic_phase_applied':mode in ('quadratic_phase','known_inverse'),
            'known_truth_inverse_phase_applied':mode=='known_inverse','unknown_lo_estimated':False,
            'mode_count_interpretation':{'bandwidth_hz':64000.,'exposure_s':.3,'ideal_independence_assumed':True} if m==19200 else None,
            'gain_checks':gain_checks,'maximum_gain_feature_abs_difference':max_gain_error,'gain_p_values_identical':gain_p_ok,
            'maximum_conjugation_transport_abs_difference':max_conjugation_error,'maximum_known_inverse_feature_abs_difference':max_inverse_error,
            'levels':levels,'p_value_minimum':float(p.min()),'p_value_median':float(np.median(p)),'p_value_maximum':float(p.max()),
            'p_value_histogram':[{'tail_count':int(a),'count':int(b)} for a,b in zip(tail_counts,counts)],'sign_group_size':1 << windows,
            'mc_mean_window_imaginary_features':means.mean(axis=0).tolist(),
            'mc_standard_error_window_mean_features':(means.std(axis=0,ddof=1)/np.sqrt(trials)).tolist(),
            'detector_inputs':'observed_power_normalized_u3.imag only; no supplied S, SEFD, sky or sigma',
            'sky_used_for_generation_and_validation_only':True,'rml_image_generated':False,'actual_hardware_data':False}


def _write_json(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');temporary.replace(path)


def run(output,profile='full',progress=None):
    plan=case_plan(profile);out=Path(output)
    if out.exists():raise FileExistsError('new known-Cas A symmetry output required')
    out.mkdir(parents=True);(out/'cases').mkdir();cases=[]
    for index,case in enumerate(plan):
        if progress is not None:progress(index,len(plan),case['case_id'])
        result=experiment(case);cases.append(result);_write_json(out/'cases'/f'{case["case_id"]}.json',result)
        if result['state']!='complete':raise RuntimeError('known voltage case failed fixed checks: '+case['case_id'])
    cfg=_config();result={'type':'known_casa_window_symmetry','state':'complete','profile':profile,
          'software_smoke_only':profile=='smoke','cases':cases,'fixed_geometry':cfg['geometry'],
          'configuration_asset_sha256':hashlib.sha256(reference_path('known-casa-window-symmetry.json').read_bytes()).hexdigest(),
          'source_stage081_result_sha256':cfg['source_result_sha256'],'reference':cfg['reference'],
          'assumed_frequency_hz':cfg['assumed_frequency_hz'],'assumed_site':cfg['assumed_site'],
          'assumed_start_utc':cfg['assumed_start_utc'],'snapshot_offset_s':cfg['snapshot_offset_s'],
          'all_windows_use_same_frozen_geometry':True,'finite_proper_gaussian_modes_generated':True,
          'receiver_background_and_source_self_noise_included':True,'adc_fft_fir_quantization_vdif_processed':False,
          'actual_temporal_independence_verified':False,'actual_clock_or_lo_estimated':False,
          'source_detection_or_extent_claimed':False,'image_reconstructed':False,'optimal_layout_selected':False,
          'production_rml_noise_model_changed':False,'actual_hardware_data':False,
          'scope':'Fixed synthetic single-epoch sky and known Gaussian modes. Conditional symmetry rejection fractions only. Equal double sources and instrumental or dependent-window controls limit interpretation; no actual Cas A detection, image confidence or observing-time guarantee.'}
    _write_json(out/'summary.json',result)
    plot(result,out/'casa-window-symmetry.png')
    return result


def plot(result,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(11,4))
    cases=result['cases'];rates=[c['levels'][1]['fraction'] for c in cases]
    ax.plot(range(len(cases)),rates,'o',markersize=3);ax.axhline(.05,color='black',linestyle='--')
    ax.set(xlabel='Predefined condition index',ylabel='MC rejection fraction at nominal0.05',
           title='Known voltage models only; rejection is not source detection or image quality',ylim=(-.02,1.02))
    ax.grid(alpha=.2);fig.tight_layout();fig.savefig(path,dpi=140);plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--profile',choices=('full','smoke'),default='full')
    args=p.parse_args()
    def progress(index,total,label):print(f'condition {index+1}/{total}: {label}',flush=True)
    q=run(args.output,args.profile,progress)
    print(json.dumps({'state':q['state'],'profile':q['profile'],'conditions':len(q['cases'])}))


if __name__=='__main__':main()
