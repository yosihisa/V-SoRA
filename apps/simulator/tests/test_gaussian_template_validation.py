import hashlib
import json
import numpy as np
import pytest

from vsora_simulator import gaussian_template_validation as study
from vsora_correlator.gaussian_likelihood import gaussian_log_likelihood_ratio


def test_fixed_plan_counts_roles_and_mismatch():
    plan=study.case_plan();assert len(plan)==9
    assert sum(2*c['test_per_label'] for c in plan)==9216
    assert len({(c['seed'],role) for c in plan for role in (0,1)})==18
    assert [c['modes'] for c in plan]==[512]*3+[19200]*5+[512]
    assert all(c['receiver_model_matches_generation'] for c in plan[:6])
    assert not plan[6]['receiver_model_matches_generation'] and not plan[7]['receiver_model_matches_generation']
    assert plan[-1]['zero_sky_control']


@pytest.mark.parametrize('profile',['bad',None,False,1])
def test_invalid_profiles_do_not_create_output(tmp_path,profile):
    out=tmp_path/'out'
    with pytest.raises(ValueError):study.run(out,profile)
    assert not out.exists()


@pytest.mark.parametrize('key,value',[('modes',32),('seed',1),('test_per_label',1),
    ('assumed_receiver_sefd_jy',1.),('zero_sky_control',0),('maximum_baseline_m',1.),('extra','value')])
def test_modified_fixed_cases_rejected(key,value):
    c=study.case_plan('smoke')[0];c[key]=value
    with pytest.raises(ValueError):study.experiment(c)


@pytest.mark.parametrize('case',[None,[],{'profile':'full'}, {'profile':'bad'}])
def test_invalid_case_rejected(case):
    with pytest.raises(ValueError):study.experiment(case)


@pytest.mark.parametrize('errors,trials',[(0,16),(8,16),(16,16)])
def test_known_model_interval_no_training_label(errors,trials):
    q=study.known_model_error_summary(errors,trials)
    assert q['fraction']==errors/trials
    assert q['clopper_pearson_interval'][0]<=errors/trials<=q['clopper_pearson_interval'][1]
    assert q['conditional_fixed_models_binomial_confidence_level']==.95 and not q['training_used']
    assert 'conditional_fixed_training_binomial_confidence_level' not in q
    assert not q['actual_observation_confidence_interval']


@pytest.mark.parametrize('errors,trials',[(-1,16),(17,16),(0,0),(True,16),(0,16.),(1,65537)])
def test_invalid_error_counts(errors,trials):
    with pytest.raises(ValueError):study.known_model_error_summary(errors,trials)


def test_smoke_direct_raw_reference_known_transport_and_zero(tmp_path):
    events=[];out=tmp_path/'out'
    q=study.run(out,'smoke',lambda i,n,label:events.append((i,n,label)))
    assert q['state']=='complete' and q['software_smoke_only'] and len(events)==3
    assert q['independent_voltage_windows_generated']==96 and not q['training_used']
    assert json.loads((out/'summary.json').read_text())==q
    for c in q['cases']:
        p=np.asarray(c['point_test_log_likelihood_ratios']);s=np.asarray(c['casa_test_log_likelihood_ratios'])
        assert len(p)==len(s)==16
        assert c['false_casa_on_point']['errors']==int(np.count_nonzero(p>0))
        assert c['missed_casa']['errors']==int(np.count_nonzero(s<=0))
        assert c['balanced_accuracy']==1-(np.mean(p>0)+np.mean(s<=0))/2
        assert c['empirical_auroc']==study.empirical_auc(p,s)
        for name in ('point_generation','casa_generation'):
            g=c[name];assert g['direct_voltage_checks']==g['known_gain_checks']==2
            assert g['maximum_generated_array_complex_values']<=1000000
            assert g['same_modes_used_for_all_stations'] and g['known_gain_predictions_identical']
            assert not g['unknown_station_gain_estimated']
        assert not c['auc_pairs_treated_as_independent'] and not c['test_used_for_threshold_or_model_selection']
        assert not c['unknown_gain_sefd_lo_estimated'] and not c['image_likelihood_defined']
    z=q['cases'][-1]
    assert z['zero_control_all_scores_exactly_zero'] and z['balanced_accuracy']==z['empirical_auroc']==.5
    assert z['false_casa_on_point']['fraction']==0 and z['missed_casa']['fraction']==1
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
    with pytest.raises(FileExistsError):study.run(out,'smoke')
    assert {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}==before


def test_reproducible_and_cached_covariance_not_modified():
    case=study.case_plan('smoke')[0]
    c=study._known_model('point',600.,(1000.,)*8)[0];before=c.copy()
    a=study.experiment(case);b=study.experiment(case)
    assert a==b;np.testing.assert_array_equal(c,before)
    assert not c.flags.writeable


def test_population_likelihood_means_have_correct_direction():
    c0=study._known_model('point',600.,(10000.,)*8)[0]
    c1=study._known_model('casa',600.,(10000.,)*8)[0]
    assert gaussian_log_likelihood_ratio(c0,c1,c0,512)<0
    assert gaussian_log_likelihood_ratio(c0,c1,c1,512)>0
    assert gaussian_log_likelihood_ratio(c0,c0,c1,512)==0


def test_draw_failure_propagates_without_success_summary(tmp_path,monkeypatch):
    def fail(*args,**kwargs):raise RuntimeError('explicit failure')
    monkeypatch.setattr(study,'_draw',fail)
    out=tmp_path/'out'
    with pytest.raises(RuntimeError,match='explicit failure'):study.run(out,'smoke')
    assert not (out/'summary.json').exists()


@pytest.mark.parametrize('bad',[np.nan,123456789.])
def test_bad_likelihood_output_rejected(monkeypatch,bad):
    monkeypatch.setattr(study,'gaussian_log_likelihood_ratio',lambda *a:bad)
    with pytest.raises((ValueError,RuntimeError)):study.experiment(study.case_plan('smoke')[0])
