"""Paired known-phase and phase-only-fit scores on the same simulated voltages.

Fixed amplitudes/noise and two supplied skies. This is not a closure image
likelihood or a practical station calibration demonstration.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from vsora_correlator.gaussian_likelihood import gaussian_log_likelihood_ratio, sample_second_moment
from vsora_correlator.gaussian_phase_profile import compare_phase_profiles, PhaseProfileConvergenceError
from vsora_observation.reference import reference_path
from .casa_window_symmetry import _config, _known_model
from .gaussian_template_validation import known_model_error_summary
from .known_template_validation import empirical_auc
from .sensitivity import dish_area, sefd_from_area


def case_plan(profile='full'):
    if profile not in ('full','smoke'):
        raise ValueError('full or smoke profile required')
    large=float(sefd_from_area(100.,dish_area(1.,.6)))
    rows=[(m,s,False) for m in (512,19200) for s in (1000.,10000.,large)]
    rows.append((512,1000.,True))
    plan=[{'case_id':f'p{i:02d}','profile':'full','modes':m,'sefd_jy':s,
        'zero_sky_control':zero,'test_per_label':64,'seed':104000+i,
        'maximum_baseline_m':600.,'max_iterations':200} for i,(m,s,zero) in enumerate(rows)]
    if profile=='smoke':
        plan=[dict(plan[i],case_id=f'smoke-{i}',profile='smoke',modes=16,
            test_per_label=2,seed=114000+i) for i in (0,2,6)]
    return plan


def _metrics(point, casa):
    if any(v is None for v in point+casa):
        return {'state':'unresolved_windows','balanced_accuracy':None,'empirical_auroc':None,
            'false_casa_on_point':None,'missed_casa':None,'success_only_metric_reported':False}
    def rate(errors,n):
        q=known_model_error_summary(errors,n)
        q['fixed_algorithm_and_generator_binomial_confidence_level']=q.pop('conditional_fixed_models_binomial_confidence_level')
        return q
    false=rate(sum(v>0 for v in point),len(point));missed=rate(sum(v<=0 for v in casa),len(casa))
    return {'state':'complete','balanced_accuracy':1-(false['fraction']+missed['fraction'])/2,
        'empirical_auroc':empirical_auc(np.asarray(point),np.asarray(casa)),
        'false_casa_on_point':false,'missed_casa':missed,'auc_pairs_independent':False,
        'success_only_metric_reported':False,'image_confidence_defined':False}


def _voltage_score(c0,c1,voltage):
    """Independent raw-voltage quadratic form, without the moment API."""
    solved0=np.linalg.solve(c0,voltage.T)
    solved1=np.linalg.solve(c1,voltage.T)
    value=len(voltage)*(np.linalg.slogdet(c0)[1]-np.linalg.slogdet(c1)[1])
    return float(value+np.sum((voltage.conj().T*(solved0-solved1)).real))


def _fitted_matrix(fit):
    a=np.asarray(fit['fitted_covariance_real_imag'])
    return a[...,0]+1j*a[...,1]


def _draw(mode,role,case,c0,c1):
    _,root,_,_=_known_model(mode,600.,(case['sefd_jy'],)*8)
    rng=np.random.default_rng(np.random.SeedSequence([case['seed'],role]))
    phases=np.random.default_rng(np.random.SeedSequence([case['seed'],role,99]))
    rows=[];m=case['modes'];paired=np.zeros((2,2),dtype=int)
    for index in range(case['test_per_label']):
        z=(rng.normal(size=(m,8))+1j*rng.normal(size=(m,8)))/np.sqrt(2)
        original=z @ root.T;gain=np.exp(1j*phases.uniform(-np.pi,np.pi,8))
        voltage=original*gain;s=sample_second_moment(voltage)
        changed=lambda c:gain[:,None]*c*gain.conj()[None,:]
        oracle=gaussian_log_likelihood_ratio(changed(c0),changed(c1),s,m)
        original_score=gaussian_log_likelihood_ratio(c0,c1,sample_second_moment(original),m)
        if not np.isclose(oracle,original_score,rtol=2e-10,atol=2e-7):
            raise RuntimeError('known phase oracle transport mismatch')
        raw_oracle=None;raw_profile=None;profile_transport=None
        if index==0:
            raw_oracle=abs(oracle-_voltage_score(changed(c0),changed(c1),voltage))
            if raw_oracle>2e-7:raise RuntimeError('direct voltage oracle mismatch')
        try:
            fitted=compare_phase_profiles(c0,c1,s,m,max_iterations=case['max_iterations'])
        except PhaseProfileConvergenceError as error:
            if str(error)!='both phase fits must reach verified stationarity':raise
            score=None;state='not_converged';fit_states=None;grad=None
        else:
            score=fitted['log_likelihood1_minus0'];state='stationary_or_analytic_reference'
            fit_states=[fitted[k]['state'] for k in ('fit0','fit1')]
            grad=[fitted[k]['gradient_inf_norm_normalized'] for k in ('fit0','fit1')]
            paired[int(oracle>0),int(score>0)]+=1
            if index==0:
                raw_profile=abs(score-_voltage_score(_fitted_matrix(fitted['fit0']),_fitted_matrix(fitted['fit1']),voltage))
                if raw_profile>2e-7:raise RuntimeError('direct voltage profile mismatch')
                extra=np.exp(1j*np.linspace(-1.2,2.,8))
                transformed=extra[:,None]*s*extra.conj()[None,:]
                transported=compare_phase_profiles(c0,c1,transformed,m,max_iterations=case['max_iterations'])
                profile_transport=abs(score-transported['log_likelihood1_minus0'])
                if profile_transport>2e-7:raise RuntimeError('profile phase transport mismatch')
        rows.append({'window_index':index,'oracle_score':oracle,'phase_profile_score':score,
            'profile_state':state,'fit_states':fit_states,'fit_gradient_normalized':grad,
            'known_phase_transport_abs_difference':abs(oracle-original_score),
            'direct_voltage_oracle_abs_difference':raw_oracle,
            'direct_voltage_profile_abs_difference':raw_profile,
            'profile_data_phase_transport_abs_difference':profile_transport,
            'oracle_prediction_casa':bool(oracle>0),'profile_prediction_casa':None if score is None else bool(score>0)})
    return {'rows':rows,'unresolved_windows':sum(q['phase_profile_score'] is None for q in rows),
        'oracle_by_profile_prediction_counts_on_resolved_only':paired.tolist(),
        'paired_table_rows_oracle_columns_profile_point_then_casa':True,
        'rng_seed_sequence':[case['seed'],role],'phase_seed_sequence':[case['seed'],role,99],
        'maximum_voltage_array_complex_values':m*8,'same_voltage_used_for_both_scores':True,
        'true_phase_supplied_only_to_oracle':True,'profile_received_true_phase':False,
        'station_phase_constant_within_window':True,'independent_phase_draw_between_windows':True}


def experiment(case):
    if not isinstance(case,dict):raise ValueError('unmodified fixed case required')
    encoded=json.dumps(case,sort_keys=True,allow_nan=False)
    if not any(encoded==json.dumps(c,sort_keys=True,allow_nan=False) for c in case_plan(case.get('profile'))):
        raise ValueError('unmodified fixed case required')
    mode0,mode1=('zero','zero') if case['zero_sky_control'] else ('point','casa')
    c0=_known_model(mode0,600.,(case['sefd_jy'],)*8)[0]
    c1=_known_model(mode1,600.,(case['sefd_jy'],)*8)[0]
    point=_draw(mode0,0,case,c0,c1);casa=_draw(mode1,1,case,c0,c1)
    metrics={kind:_metrics(*[[r[key] for r in g['rows']] for g in (point,casa)])
        for kind,key in [('oracle','oracle_score'),('phase_profile','phase_profile_score')]}
    if case['zero_sky_control'] and any(r[k]!=0 for g in (point,casa) for r in g['rows'] for k in ('oracle_score','phase_profile_score')):
        raise RuntimeError('equal covariance control is not exactly zero')
    return {**case,'state':'complete','candidate0_mode':mode0,'candidate1_mode':mode1,
        'point_generation':point,'casa_generation':casa,'metrics':metrics,
        'unresolved_profile_windows':point['unresolved_windows']+casa['unresolved_windows'],
        'threshold_score':0.,'threshold_ties_assigned_to':'point','training_used':False,
        'true_phase_supplied_to_profile':False,'amplitudes_and_sefd_supplied_to_both':True,
        'global_profile_optimum_proved':bool(case['zero_sky_control']),
        'image_likelihood_defined':False,'unknown_amplitude_sefd_lo_estimated':False,
        'actual_fft_independence_verified':False,'real_hardware_validation_performed':False}


def run(output,profile='full',progress=None):
    plan=case_plan(profile);out=Path(output);out.mkdir(parents=True,exist_ok=False);(out/'cases').mkdir()
    cases=[]
    for i,case in enumerate(plan):
        if progress:progress(i,len(plan),case['case_id'])
        q=experiment(case);(out/'cases'/f"{case['case_id']}.json").write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');cases.append(q)
    config=_config()
    q={'state':'complete','type':'paired_known_phase_and_phase_profile','profile':profile,
        'cases':cases,'independent_voltage_windows_generated':sum(2*c['test_per_label'] for c in cases),
        'unresolved_profile_windows':sum(c['unresolved_profile_windows'] for c in cases),
        'assumed_frequency_hz':1.42e9,'maximum_baseline_m':600.,'assumed_source_total_flux_jy':1000.,
        'reference':config['reference'],'configuration_asset_sha256':hashlib.sha256(reference_path('known-casa-window-symmetry.json').read_bytes()).hexdigest(),
        'template_fits_sha256':hashlib.sha256(reference_path().read_bytes()).hexdigest(),
        'source_model_is_measured_at_this_frequency':False,'mode_count_is_measured_fft_independence':False,
        'image_likelihood_defined':False,'general_sky_reconstructed':False,
        'unknown_amplitude_sefd_lo_estimated':False,'production_rml_noise_model_changed':False,
        'software_smoke_only':profile=='smoke','unresolved_windows_never_dropped_from_overall_metrics':True}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');return q


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--profile',choices=('full','smoke'),default='full');args=p.parse_args()
    q=run(args.output,args.profile);print(json.dumps({'state':q['state'],'conditions':len(q['cases']),
        'windows':q['independent_voltage_windows_generated'],'unresolved':q['unresolved_profile_windows']}))


if __name__=='__main__':main()
