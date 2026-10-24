"""Known-template experiments with independent training and test replicates.

This reference study does not define an image likelihood or estimate SEFD.
"""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
from vsora_simulator.known_template_validation import _draw,error_rate_summary,empirical_auc
from vsora_simulator.template_score import fit_template_mean_score,score_template_features
from vsora_simulator.sensitivity import sefd_from_area,dish_area
from vsora_observation.reference import reference_path


def independent_replicate_summary(values):
    """Use the independent outer replicate, never individual scored pairs."""
    if np.ma.isMaskedArray(values):raise ValueError('unmasked replicate values required')
    raw=np.asarray(values)
    if (raw.ndim!=1 or not 2<=len(raw)<=64 or not np.issubdtype(raw.dtype,np.number)
        or np.iscomplexobj(raw) or not np.isfinite(raw).all() or np.any(raw<0) or np.any(raw>1)):
        raise ValueError('finite real rates [R], R2..64, in0..1 required')
    x=raw.astype(float)
    if not np.isfinite(x).all() or np.any((raw!=0)&(x==0)):
        raise ValueError('float64 must not erase a nonzero rate')
    scale=float(np.max(x));normalized=x/scale if scale else x.copy()
    if np.any((x!=0)&(normalized==0)):raise ValueError('normalization must not erase a rate')
    mean_scaled=float(np.mean(normalized));sd_scaled=float(np.std(normalized,ddof=1))
    mean=mean_scaled*scale;sd=sd_scaled*scale;se=sd/math.sqrt(len(x))
    if (mean_scaled>0 and mean==0) or (sd_scaled>0 and sd==0) or (sd>0 and se==0):
        raise ValueError('float64 summary must not underflow a positive statistic')
    return {'independent_replicates':len(x),'mean':mean,
        'sample_standard_deviation_ddof1':sd,'monte_carlo_standard_error_of_mean':se,
        'minimum':float(np.min(x)),'maximum':float(np.max(x)),
        'statistical_unit':'independent training-and-test replicate',
        'replicate_independence_is_an_assumption_for_summary':True,
        'training_and_test_variation_both_included':True,'training_only_variation_isolated':False,
        'pooled_binomial_confidence_interval_defined':False,'image_confidence_interval_defined':False}


def case_plan(profile='full'):
    if profile not in ('full','smoke'):raise ValueError('full or smoke profile required')
    large=float(sefd_from_area(100.,dish_area(1.,.6)))
    rows=[(512,1000.,1000.,False),(512,10000.,10000.,False),(512,large,large,False),
          (19200,10000.,10000.,False),(19200,large,large,False),
          (19200,1000.,10000.,False),(512,1000.,1000.,True)]
    result=[]
    for i,(m,train,point,zero) in enumerate(rows):
        result.append({'case_id':f'r{i:02d}','profile':'full','modes':m,
            'training_sefd_jy':train,'point_test_sefd_jy':point,'casa_test_sefd_jy':train,
            'zero_sky_control':zero,'receiver_model_matches_training':point==train,
            'outer_replicates':16,'training_per_label':32,'test_per_label':128,
            'seed_base':980000+100*i,'maximum_baseline_m':600.,'formal_mc_precision':True})
    if profile=='smoke':
        result=[dict(result[i],case_id=f'smoke-{i}',profile='smoke',modes=16,
                outer_replicates=3,training_per_label=8,test_per_label=16,
                seed_base=result[i]['seed_base']+10000,formal_mc_precision=False) for i in (1,5,6)]
    return result


def experiment(case,progress=None):
    if not isinstance(case,dict) or not any(case==c for c in case_plan(case.get('profile'))):
        raise ValueError('unmodified fixed independent-training case required')
    modes=case['modes'];train=case['training_per_label'];test=case['test_per_label']
    point_mode,casa_mode=('zero','zero') if case['zero_sky_control'] else ('point','casa')
    repeats=[]
    for index in range(case['outer_replicates']):
        if progress:progress(index,case['outer_replicates'])
        seed=case['seed_base']+index
        ptrain,_=_draw(point_mode,case['training_sefd_jy'],train,modes,seed,0)
        ctrain,_=_draw(casa_mode,case['training_sefd_jy'],train,modes,seed,1)
        model=fit_template_mean_score(ptrain,ctrain)
        if model['state']!='identified_training_direction':raise RuntimeError('training means give no direction')
        point,pc=_draw(point_mode,case['point_test_sefd_jy'],test,modes,seed,2,model)
        casa,cc=_draw(casa_mode,case['casa_test_sefd_jy'],test,modes,seed,3,model)
        ps=score_template_features(point,model);cs=score_template_features(casa,model)
        false=error_rate_summary(int(np.count_nonzero(ps>0)),test)
        missed=error_rate_summary(int(np.count_nonzero(cs<=0)),test)
        gain_ok=all(c['maximum_gain_feature_abs_difference']<=2e-12
            and c['maximum_gain_score_abs_difference']<=2e-8 and c['gain_predictions_identical'] for c in (pc,cc))
        repeats.append({'replicate_index':index,'seed':seed,'state':'complete' if gain_ok else 'failed_validation',
            'training_model':model,'point_test_scores':ps.tolist(),'casa_test_scores':cs.tolist(),
            'false_casa_on_point':false,'missed_casa':missed,
            'balanced_accuracy':1-(false['fraction']+missed['fraction'])/2,
            'empirical_auroc':empirical_auc(ps,cs),'point_generation':pc,'casa_generation':cc,
            'training_and_test_roles':[0,1,2,3],'test_used_for_training_or_selection':False,
            'threshold_score':0.,'threshold_ties_assigned_to':'point'})
    metrics={name:independent_replicate_summary([r[name] for r in repeats])
        for name in ('balanced_accuracy','empirical_auroc')}
    for name in ('false_casa_on_point','missed_casa'):
        metrics[name]=independent_replicate_summary([r[name]['fraction'] for r in repeats])
    zero_applies=case['zero_sky_control'] and case['formal_mc_precision']
    maximum_zero_se=math.sqrt(1/(8*test*len(repeats)))
    zero_check=abs(metrics['balanced_accuracy']['mean']-.5)<=6*maximum_zero_se if zero_applies else None
    return {**case,'state':'complete' if all(r['state']=='complete' for r in repeats) and zero_check is not False else 'failed_validation',
        'replicates':repeats,'metrics':metrics,'seed_roles_disjoint':True,
        'test_selected_threshold_or_hyperparameters':False,'same_evaluation_windows_reused_across_training':False,
        'training_variation_isolated_from_test_variation':False,
        'training_sky_models':[point_mode,casa_mode],'test_sky_models':[point_mode,casa_mode],
        'assumed_source_total_flux_jy_by_label':[0.,0.] if case['zero_sky_control'] else [1000.,1000.],
        'zero_control_check_applied':zero_applies,'zero_control_maximum_outer_mean_mc_se':maximum_zero_se,
        'zero_control_within_half_plus_minus_six_max_se':zero_check,
        'independent_gaussian_modes_assumed':True,'actual_fft_independence_verified':False,
        'unknown_receiver_sefd_estimated':False,'unknown_lo_estimated':False,
        'image_likelihood_defined':False,'image_reconstructed':False,'real_hardware_validation_performed':False,
        'production_rml_noise_model_changed':False}


def run(output,profile='full',progress=None):
    plan=case_plan(profile)  # Reject bad plans before creating an output folder.
    out=Path(output);out.mkdir(parents=True,exist_ok=False);(out/'cases').mkdir()
    cases=[]
    for i,case in enumerate(plan):
        if progress:progress(i,len(plan),case['case_id'])
        value=experiment(case)
        (out/'cases'/f"{case['case_id']}.json").write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
        cases.append(value)
    summary={'type':'known_template_independent_training_repeats','profile':profile,
        'state':'complete' if all(c['state']=='complete' for c in cases) else 'failed_validation',
        'cases':cases,'outer_replicates_total':sum(c['outer_replicates'] for c in cases),
        'independent_voltage_windows_generated':sum(c['outer_replicates']*2*(c['training_per_label']+c['test_per_label']) for c in cases),
        'statistical_unit':'independent training-and-test replicate',
        'pooled_binomial_interval_used':False,'production_rml_noise_model_changed':False,
        'real_hardware_validation_performed':False,'software_smoke_only':profile=='smoke'}
    summary.update(config_fixture_sha256=hashlib.sha256(reference_path('known-casa-window-symmetry.json').read_bytes()).hexdigest(),
        template_fits_sha256=hashlib.sha256(reference_path().read_bytes()).hexdigest(),
        feature_order='56 normalized U3 real, then56 imaginary',
        individual_replicate_intervals_conditional_on_that_replicate_training=True,
        aggregate_mc_standard_error_is_not_a_risk_bound=True,
        independent_training_and_test_draws_assumed=True)
    (out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    plot(summary,out/'independent-training-repeats.png')
    return summary


def plot(summary,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True,sharey=True)
    for ax,name in zip(axes,('balanced_accuracy','empirical_auroc'),strict=True):
        for i,case in enumerate(summary['cases']):
            values=[r[name] for r in case['replicates']];metric=case['metrics'][name]
            ax.scatter([i]*len(values),values,color='tab:blue',s=14,alpha=.6)
            ax.errorbar(i,metric['mean'],yerr=metric['sample_standard_deviation_ddof1'],
                        fmt='D',color='black',capsize=4,markersize=4)
        ax.axhline(.5,color='grey',linestyle='--');ax.set_ylabel(name)
        ax.set_ylim(-.12,1.12);ax.grid(alpha=.2)
    axes[-1].set(xticks=range(len(summary['cases'])),xticklabels=[c['case_id'] for c in summary['cases']],
                 xlabel='Fixed known-model condition; independent training and test per dot')
    fig.suptitle('Independent training/test replicates: mean +/- sample SD; not image confidence')
    fig.tight_layout();fig.savefig(path,dpi=140);plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--profile',choices=('full','smoke'),default='full');a=p.parse_args()
    q=run(a.output,a.profile,lambda i,n,label:print(f'condition {i+1}/{n}: {label}',flush=True))
    if q['state']!='complete':raise SystemExit('validation failed')


if __name__=='__main__':main()
