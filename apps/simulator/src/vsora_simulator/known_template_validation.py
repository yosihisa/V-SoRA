"""Fixed two-known-sky holdout discrimination; not an image likelihood."""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
from scipy.stats import binomtest
from vsora_observation.reference import reference_path
from .template_score import fit_template_mean_score,score_template_features
from vsora_simulator.bispectrum_observed_power import observed_power_normalized_bispectrum
from vsora_simulator.casa_window_symmetry import _config,_known_model
from vsora_simulator.sensitivity import sefd_from_area,dish_area


def case_plan(profile='full'):
    if profile not in ('full','smoke'):raise ValueError('full or smoke profile required')
    large=float(sefd_from_area(100.,dish_area(1.,.6)));cases=[]
    for modes in (512,19200):
        for sefd in (1000.,10000.,large):
            cases.append({'modes':modes,'training_sefd_jy':sefd,'point_test_sefd_jy':sefd,
                          'casa_test_sefd_jy':sefd,'zero_sky_control':False,'receiver_model_matches_training':True})
    for train,point in ((1000.,10000.),(10000.,1000.)):
        cases.append({'modes':19200,'training_sefd_jy':train,'point_test_sefd_jy':point,
                      'casa_test_sefd_jy':train,'zero_sky_control':False,'receiver_model_matches_training':False})
    cases.append({'modes':512,'training_sefd_jy':1000.,'point_test_sefd_jy':1000.,
                  'casa_test_sefd_jy':1000.,'zero_sky_control':True,'receiver_model_matches_training':True})
    for index,c in enumerate(cases):
        c.update(case_id=f'd{index:02d}',seed=9600+index,training_per_label=128,test_per_label=512,
                 maximum_baseline_m=600.,profile='full',formal_mc_precision=True)
    if profile=='smoke':
        cases=[dict(cases[i],case_id=f'smoke-{i}',modes=16,training_per_label=8,test_per_label=16,
                    profile='smoke',formal_mc_precision=False) for i in (0,6,8)]
    return cases


def error_rate_summary(errors,trials):
    if (isinstance(errors,(bool,np.bool_)) or isinstance(trials,(bool,np.bool_))
        or not isinstance(errors,(int,np.integer)) or not isinstance(trials,(int,np.integer))
        or not 1<=trials<=65536 or not 0<=errors<=trials):
        raise ValueError('integer error count0..n and trials1..65536 required')
    k,n=int(errors),int(trials);fraction=k/n
    ci=binomtest(k,n).proportion_ci(confidence_level=.95,method='exact')
    return {'errors':k,'trials':n,'fraction':fraction,'plug_in_mc_standard_error':math.sqrt(fraction*(1-fraction)/n),
            'conditional_fixed_training_binomial_confidence_level':.95,
            'clopper_pearson_interval':[float(ci.low),float(ci.high)],
            'training_variability_included':False,'actual_observation_confidence_interval':False}


def empirical_auc(point_scores,casa_scores):
    p=np.asarray(point_scores);c=np.asarray(casa_scores)
    if (p.ndim!=1 or c.ndim!=1 or not len(p) or not len(c) or max(len(p),len(c))>4096
        or any(np.ma.isMaskedArray(v) for v in (point_scores,casa_scores))
        or any(np.iscomplexobj(v) or not np.issubdtype(v.dtype,np.number) or not np.isfinite(v).all() for v in (p,c))):
        raise ValueError('finite real score vectors1..4096 required')
    return float(np.mean(c[:,None]>p[None,:])+.5*np.mean(c[:,None]==p[None,:]))


def _draw(mode,sefd,n,modes,seed,role,model=None):
    covariance,root,_,_=_known_model(mode,600.,(float(sefd),)*8)
    rng=np.random.default_rng(np.random.SeedSequence([seed,role]))
    gain_rng=np.random.default_rng(np.random.SeedSequence([seed,role,99]))
    batch=min(32,max(1,1000000//(modes*8)));parts=[];gain_feature_error=0.;gain_score_error=0.;predictions_equal=True;checks=0
    for start in range(0,n,batch):
        count=min(batch,n-start);shape=(count,modes,8)
        z=(rng.normal(size=shape)+1j*rng.normal(size=shape))/np.sqrt(2)
        x=z@root.T
        q=observed_power_normalized_bispectrum(x)
        values=q['observed_power_normalized_u3'];features=np.concatenate((values.real,values.imag),axis=-1)
        parts.append(features)
        check=min(count,max(0,4-start)) if model is not None else 0
        if check:
            gains=np.exp(gain_rng.uniform(-.8,.8,size=(check,1,8))+1j*gain_rng.uniform(-np.pi,np.pi,size=(check,1,8)))
            changed=observed_power_normalized_bispectrum(x[:check]*gains)['observed_power_normalized_u3']
            changed=np.concatenate((changed.real,changed.imag),axis=-1)
            gain_feature_error=max(gain_feature_error,float(np.max(abs(changed-features[:check]))))
            baseline=score_template_features(features[:check],model);transported=score_template_features(changed,model)
            gain_score_error=max(gain_score_error,float(np.max(abs(baseline-transported))))
            predictions_equal=predictions_equal and bool(np.array_equal(baseline>0,transported>0));checks+=check
    return np.concatenate(parts),{'gain_checks':checks,'maximum_gain_feature_abs_difference':gain_feature_error,
        'maximum_gain_score_abs_difference':gain_score_error,'gain_predictions_identical':predictions_equal,
        'station_covariance_real_imag':np.stack((covariance.real,covariance.imag),axis=-1).tolist()}


def experiment(case):
    plans=case_plan(case.get('profile')) if isinstance(case,dict) else []
    if not any(case==c for c in plans):raise ValueError('unmodified fixed template-validation case required')
    modes=case['modes'];seed=case['seed'];train=case['training_per_label'];n=case['test_per_label']
    modes0,modes1=('zero','zero') if case['zero_sky_control'] else ('point','casa')
    ptrain,_=_draw(modes0,case['training_sefd_jy'],train,modes,seed,0)
    ctrain,_=_draw(modes1,case['training_sefd_jy'],train,modes,seed,1)
    model=fit_template_mean_score(ptrain,ctrain)
    if model['state']!='identified_training_direction':raise RuntimeError('fixed training produced no direction')
    point,pc=_draw(modes0,case['point_test_sefd_jy'],n,modes,seed,2,model)
    casa,cc=_draw(modes1,case['casa_test_sefd_jy'],n,modes,seed,3,model)
    ps=score_template_features(point,model);cs=score_template_features(casa,model)
    false_casa=error_rate_summary(int(np.count_nonzero(ps>0)),n)
    missed_casa=error_rate_summary(int(np.count_nonzero(cs<=0)),n)
    accuracy=1-(false_casa['fraction']+missed_casa['fraction'])/2
    se=.5*math.sqrt(false_casa['plug_in_mc_standard_error']**2+missed_casa['plug_in_mc_standard_error']**2)
    zero_applies=case['zero_sky_control'] and case['formal_mc_precision']
    maximum_zero_se=math.sqrt(1/(8*n))
    zero_check=abs(accuracy-.5)<=6*maximum_zero_se if zero_applies else None
    gain_ok=all(c['maximum_gain_feature_abs_difference']<=2e-12 and c['maximum_gain_score_abs_difference']<=2e-8
                and c['gain_predictions_identical'] for c in (pc,cc))
    good=gain_ok and zero_check is not False
    return {**case,'state':'complete' if good else 'failed_validation','feature_count':point.shape[1],
        'training_sky_models':[modes0,modes1],'test_sky_models':[modes0,modes1],
        'assumed_source_total_flux_jy_by_label':[0.,0.] if case['zero_sky_control'] else [1000.,1000.],
        'feature_order':'56 normalized U3 real, then56 imaginary','training_model':model,
        'point_test_scores':ps.tolist(),'casa_test_scores':cs.tolist(),
        'false_casa_on_point':false_casa,'missed_casa':missed_casa,
        'balanced_accuracy':accuracy,'balanced_accuracy_plug_in_mc_standard_error':se,
        'empirical_auroc':empirical_auc(ps,cs),'auc_pair_count':n*n,'auc_pairs_treated_as_independent':False,
        'zero_control_check_applied':zero_applies,'zero_control_maximum_conditional_mc_se':maximum_zero_se,
        'zero_control_within_half_plus_minus_six_max_se':zero_check,
        'point_generation':pc,'casa_generation':cc,
        'training_test_roles':[0,1,2,3],'rng_streams_separate_by_seed_sequence':True,
        'test_used_for_threshold_or_direction':False,'threshold_score':0.,'threshold_ties_assigned_to':'point',
        'fixed_station_gain_check_feature_atol':2e-12,'fixed_station_gain_check_score_atol':2e-8,
        'independent_gaussian_modes_assumed':True,'within_window_station_gain_constant_assumed':True,
        'ideal_mode_time_interpretation':{'bandwidth_hz':64000.,'integration_s':.3,'actual_fft_independence_verified':False} if modes==19200 else None,
        'receiver_model_is_generating_assumption':True,'actual_receiver_sefd_estimated':False,
        'unknown_lo_estimated':False,'image_reconstructed':False,'source_detection_claimed':False,
        'best_classifier_or_information_bound_claimed':False,'production_rml_noise_model_changed':False}


def run(output,profile='full',progress=None):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);(out/'cases').mkdir();cases=[]
    for index,case in enumerate(case_plan(profile)):
        if progress:progress(index,len(case_plan(profile)),case['case_id'])
        q=experiment(case);cases.append(q)
        (out/'cases'/(case['case_id']+'.json')).write_text(json.dumps(q,indent=2,allow_nan=False)+'\n')
        if q['state']!='complete':raise RuntimeError('fixed template validation failed: '+case['case_id'])
    cfg=_config();q={'type':'known_template_holdout_discrimination','state':'complete','profile':profile,
       'cases':cases,'assumed_frequency_hz':1.42e9,'maximum_baseline_m':600.,
       'assumed_source_total_flux_jy':1000.,'zero_sky_control_source_flux_jy':0.,'reference':cfg['reference'],
       'fixed_geometry':next(g for g in cfg['geometry'] if g['maximum_baseline_m']==600.),
       'configuration_asset_sha256':hashlib.sha256(reference_path('known-casa-window-symmetry.json').read_bytes()).hexdigest(),
       'independent_voltage_windows_generated':sum(2*c['training_per_label']+2*c['test_per_label'] for c in cases),
       'mode_count_is_adc_fft_measurement':False,'actual_hardware_data':False,
       'unknown_sefd_or_lo_calibration_validated':False,'general_sky_reconstructed':False,
       'image_likelihood_defined':False,'production_rml_noise_model_changed':False,
       'scope':'Fixed two-known-sky training/holdout feature benchmark under supplied receiver covariance. '
               'Noise mismatch and equal zero-sky controls constrain interpretation. No actual source detection, '
               'general sky reconstruction, optimality, observing-time guarantee or image confidence.'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n')
    plot(q,out/'template-holdout.png');return q


def plot(q,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(10,4));x=np.arange(len(q['cases']))
    ax.plot(x,[c['balanced_accuracy'] for c in q['cases']],'o-',label='Balanced accuracy')
    ax.plot(x,[c['empirical_auroc'] for c in q['cases']],'s-',label='Empirical AUROC')
    ax.axhline(.5,color='black',linestyle='--')
    ax.set(xticks=x,xticklabels=[c['case_id'] for c in q['cases']],ylim=(-.02,1.02),
           xlabel='Fixed known-model condition',ylabel='Held-out feature classification metric',
           title='Known receiver/sky training only; no actual image confidence')
    ax.legend();ax.grid(alpha=.25);fig.tight_layout();fig.savefig(path,dpi=140);plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--profile',choices=('full','smoke'),default='full');args=p.parse_args()
    q=run(args.output,args.profile,lambda i,n,label:print(f'condition {i+1}/{n}: {label}',flush=True))
    print(json.dumps({'state':q['state'],'conditions':len(q['cases'])}))


if __name__=='__main__':main()
