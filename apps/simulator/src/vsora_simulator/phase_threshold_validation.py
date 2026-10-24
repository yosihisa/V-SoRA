"""Train a scalar phase-profile threshold and evaluate on independent voltages.

Receiver amplitudes/SEFD and two skies stay supplied. No image likelihood,
unknown LO, or general receiver calibration is defined here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from vsora_observation.reference import reference_path
from .gaussian_phase_template import _draw
from .casa_window_symmetry import _known_model
from .known_template_validation import empirical_auc,error_rate_summary
from .sensitivity import dish_area,sefd_from_area


def _scores(value):
    a=np.asarray(value)
    if a.ndim!=1 or not 1<=len(a)<=65536 or a.dtype.kind not in 'fiu' or not np.isfinite(a).all():
        raise ValueError('one to65536 finite real scores required')
    with np.errstate(over="ignore",invalid="ignore"):
        result=a.astype(float)
    if not np.isfinite(result).all():raise ValueError("scores must fit float64")
    return result


def learn_threshold(point_scores,casa_scores):
    """Empirical balanced-error minimizer; fixed greater-than direction."""
    point=_scores(point_scores);casa=_scores(casa_scores)
    unique=np.unique(np.r_[point,casa,0.])
    with np.errstate(over='ignore'):
        below=float(np.nextafter(min(point.min(),casa.min()),-np.inf))
    if np.isfinite(below):unique=np.unique(np.r_[unique,below])
    false=len(point)-np.searchsorted(np.sort(point),unique,side='right')
    missed=np.searchsorted(np.sort(casa),unique,side='right')
    loss=false.astype(np.int64)*len(casa)+missed.astype(np.int64)*len(point)
    choices=np.flatnonzero(loss==loss.min());chosen=min(choices,key=lambda i:(abs(unique[i]),unique[i]))
    return {'state':'complete','threshold':float(unique[chosen]),'direction':'score>threshold_is_casa',
        'ties_assigned_to':'point','candidate_count':len(unique),
        'training_point_trials':len(point),'training_casa_trials':len(casa),
        'training_false_casa':int(false[chosen]),'training_missed_casa':int(missed[chosen]),
        'training_balanced_accuracy':1-float(loss[chosen])/(2*len(point)*len(casa)),
        'tie_break':'minimum_absolute_threshold_then_minimum_threshold',
        'test_data_used':False,'true_phases_or_oracle_scores_used':False}


def _evaluate(point,casa,threshold,trained):
    unresolved=sum(v is None for v in point+casa)
    if unresolved or threshold is None:
        return {'state':'unresolved','unresolved_test_windows':unresolved,
            'balanced_accuracy':None,'empirical_auroc':None,'false_casa_on_point':None,'missed_casa':None,
            'success_only_metric_reported':False}
    p=_scores(point);c=_scores(casa)
    def rate(errors,n):
        q=error_rate_summary(int(errors),n);q['training_used']=trained
        if not trained:q['fixed_algorithm_binomial_confidence_level']=q.pop('conditional_fixed_training_binomial_confidence_level')
        return q
    false=rate(np.count_nonzero(p>threshold),len(p));missed=rate(np.count_nonzero(c<=threshold),len(c))
    return {'state':'complete','unresolved_test_windows':0,'balanced_accuracy':1-(false['fraction']+missed['fraction'])/2,
        'empirical_auroc':empirical_auc(p,c),'false_casa_on_point':false,'missed_casa':missed,
        'auc_pairs_independent':False,'training_variability_included':False,'success_only_metric_reported':False}


def case_plan(profile='full'):
    if profile not in ('full','smoke'):raise ValueError('full or smoke profile required')
    large=float(sefd_from_area(100.,dish_area(1.,.6)))
    plan=[{'case_id':f't{i:02d}','profile':'full','modes':m,'sefd_jy':s,'zero_sky_control':zero,
        'training_per_label':64,'test_per_label':64,'seed':107000+i,'max_iterations':200,'maximum_baseline_m':600.}
        for i,(m,s,zero) in enumerate([(512,large,False),(19200,large,False),(512,1000.,True)])]
    return plan if profile=='full' else [dict(plan[i],case_id=f'smoke-{i}',profile='smoke',modes=16,training_per_label=4,test_per_label=4,seed=117000+i) for i in (0,2)]


def experiment(case):
    if not isinstance(case,dict):raise ValueError('unmodified fixed case required')
    encoded=json.dumps(case,sort_keys=True,allow_nan=False)
    if not any(encoded==json.dumps(c,sort_keys=True,allow_nan=False) for c in case_plan(case.get('profile'))):raise ValueError('unmodified fixed case required')
    mode0,mode1=('zero','zero') if case['zero_sky_control'] else ('point','casa')
    c0=_known_model(mode0,600.,(case['sefd_jy'],)*8)[0];c1=_known_model(mode1,600.,(case['sefd_jy'],)*8)[0]
    data={}
    for name,mode,role,count in [('training_point',mode0,10,case['training_per_label']),('training_casa',mode1,11,case['training_per_label']),('test_point',mode0,20,case['test_per_label']),('test_casa',mode1,21,case['test_per_label'])]:
        draw_case=dict(case,test_per_label=count);data[name]=_draw(mode,role,draw_case,c0,c1)
    values=lambda name,key:[r[key] for r in data[name]['rows']]
    tp,tc=values('training_point','phase_profile_score'),values('training_casa','phase_profile_score')
    unresolved=sum(v is None for v in tp+tc)
    learned=learn_threshold(tp,tc) if not unresolved else {'state':'training_unresolved','threshold':None,'unresolved_training_windows':unresolved,'test_data_used':False}
    p,c=values('test_point','phase_profile_score'),values('test_casa','phase_profile_score')
    metrics={'oracle':_evaluate(values('test_point','oracle_score'),values('test_casa','oracle_score'),0.,False),
        'fixed_zero':_evaluate(p,c,0.,False),'learned_threshold':_evaluate(p,c,learned['threshold'],True)}
    for role in ('test_point','test_casa'):
        for row in data[role]['rows']:
            v=row['phase_profile_score'];row['learned_prediction_casa']=None if v is None or learned['threshold'] is None else bool(v>learned['threshold'])
    return {**case,'state':'complete','learned':learned,'data':data,'metrics':metrics,
        'training_and_test_seed_roles_disjoint':True,'threshold_learned_without_test_or_oracle_scores':True,
        'amplitudes_and_sefd_supplied':True,'unknown_amplitude_sefd_lo_estimated':False,
        'image_likelihood_defined':False,'image_reconstructed':False,'training_variability_included':False}


def run(output,profile='full'):
    plan=case_plan(profile);out=Path(output);out.mkdir(parents=True,exist_ok=False);(out/'cases').mkdir();cases=[]
    for case in plan:
        q=experiment(case);(out/'cases'/f"{case['case_id']}.json").write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');cases.append(q)
    q={'state':'complete','type':'independent_phase_threshold_validation','profile':profile,'cases':cases,
        'independent_voltage_windows_generated':sum(2*(c['training_per_label']+c['test_per_label']) for c in cases),
        'assumed_frequency_hz':1.42e9,'maximum_baseline_m':600.,'assumed_source_total_flux_jy':1000.,
        'true_phase_supplied_only_to_oracle':True,'image_likelihood_defined':False,'actual_hardware_data':False,
        'configuration_asset_sha256':hashlib.sha256(reference_path('known-casa-window-symmetry.json').read_bytes()).hexdigest(),
        'template_fits_sha256':hashlib.sha256(reference_path().read_bytes()).hexdigest(),
        'production_rml_noise_model_changed':False,'software_smoke_only':profile=='smoke'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');return q


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--profile',choices=('full','smoke'),default='full');a=p.parse_args();q=run(a.output,a.profile)
    print(json.dumps({'state':q['state'],'cases':len(q['cases']),'windows':q['independent_voltage_windows_generated']}))


if __name__=='__main__':main()
