import math
import numpy as np
import pytest
from vsora_simulator import independent_training_validation as study


def test_summary_uses_outer_unit_and_sample_sd():
    q=study.independent_replicate_summary([0.,.5,1.])
    assert q['mean']==.5 and q['sample_standard_deviation_ddof1']==.5
    assert q['monte_carlo_standard_error_of_mean']==pytest.approx(.5/math.sqrt(3))
    assert q['minimum']==0 and q['maximum']==1 and q['independent_replicates']==3
    assert q['training_and_test_variation_both_included'] and not q['training_only_variation_isolated']
    assert not q['pooled_binomial_confidence_interval_defined'] and not q['image_confidence_interval_defined']


@pytest.mark.parametrize('value',[0.,.25,.5,1.])
def test_constant_replicates(value):
    q=study.independent_replicate_summary([value]*16)
    assert q['mean']==value and q['sample_standard_deviation_ddof1']==0
    assert q['monte_carlo_standard_error_of_mean']==0


@pytest.mark.parametrize('bad',[[],[.5],[0.]*65,[[0.,1.]],[-.1,.5],[.5,1.1],
    [float('nan'),0.],[float('inf'),0.],[0j,1j],[True,False],['0','1'],np.ma.array([0.,1.],mask=[False,True])])
def test_summary_rejects_invalid_inputs(bad):
    with pytest.raises(ValueError):study.independent_replicate_summary(bad)


def test_longdouble_underflow_rejected():
    if np.finfo(np.longdouble).tiny==np.finfo(float).tiny:pytest.skip('no extra exponent range')
    with pytest.raises(ValueError):study.independent_replicate_summary(np.array([0,np.finfo(np.longdouble).tiny],dtype=np.longdouble))


def test_replication_count_uses_ddof1_and_se_formula():
    # These arrays are arithmetic checks, not evidence of independent duplicated trials.
    a=study.independent_replicate_summary([0.,1.]);b=study.independent_replicate_summary([0.,0.,1.,1.])
    assert a['sample_standard_deviation_ddof1']==pytest.approx(math.sqrt(.5))
    assert b['sample_standard_deviation_ddof1']==pytest.approx(math.sqrt(1/3))
    assert b['monte_carlo_standard_error_of_mean']==pytest.approx(math.sqrt(1/12))


def test_tiny_rates_have_scaled_nonzero_sd():
    q=study.independent_replicate_summary([1e-300,2e-300])
    assert q['mean']==pytest.approx(1.5e-300,abs=0)
    assert q['sample_standard_deviation_ddof1']==pytest.approx(math.sqrt(.5)*1e-300,abs=0)
    assert q['monte_carlo_standard_error_of_mean']==pytest.approx(.5e-300,abs=0)


def test_unrepresentable_positive_summary_rejected():
    with pytest.raises(ValueError,match='underflow'):
        study.independent_replicate_summary([0.,np.nextafter(0.,1.)])


def test_full_plan_disjoint_seeds_roles_and_counts():
    plan=study.case_plan();assert len(plan)==7
    streams=[(c['seed_base']+i,r) for c in plan for i in range(c['outer_replicates']) for r in range(4)]
    assert len(streams)==len(set(streams))==448
    assert sum(c['outer_replicates']*2*(c['training_per_label']+c['test_per_label']) for c in plan)==35840
    assert sum(c['outer_replicates'] for c in plan)==112
    assert plan[-1]['zero_sky_control'] and not plan[-2]['receiver_model_matches_training']


@pytest.mark.parametrize('profile',['bad',None,False,1])
def test_bad_profiles_do_not_create_output(tmp_path,profile):
    out=tmp_path/'out'
    with pytest.raises(ValueError):study.run(out,profile)
    assert not out.exists()


@pytest.mark.parametrize('key,value',[('outer_replicates',2),('seed_base',1),('modes',32),('training_per_label',16),('test_per_label',1)])
def test_case_plan_modifications_rejected(key,value):
    c=study.case_plan('smoke')[0];c[key]=value
    with pytest.raises(ValueError):study.experiment(c)


def test_smoke_real_voltages_separate_roles_and_summary(tmp_path):
    q=study.run(tmp_path/'out','smoke')
    assert q['state']=='complete' and q['software_smoke_only']
    assert q['outer_replicates_total']==9 and q['independent_voltage_windows_generated']==432
    assert not q['pooled_binomial_interval_used']
    for c in q['cases']:
        assert len(c['replicates'])==3 and not c['training_variation_isolated_from_test_variation']
        assert not c['same_evaluation_windows_reused_across_training']
        for r in c['replicates']:
            p=np.array(r['point_test_scores']);s=np.array(r['casa_test_scores'])
            assert len(p)==len(s)==16
            assert r['false_casa_on_point']['errors']==int(np.count_nonzero(p>0))
            assert r['missed_casa']['errors']==int(np.count_nonzero(s<=0))
            assert r['balanced_accuracy']==1-(np.mean(p>0)+np.mean(s<=0))/2
            assert r['training_and_test_roles']==[0,1,2,3] and not r['test_used_for_training_or_selection']
        values=[r['balanced_accuracy'] for r in c['replicates']]
        assert c['metrics']['balanced_accuracy']==study.independent_replicate_summary(values)
        assert not c['zero_control_check_applied']
    with pytest.raises(FileExistsError):study.run(tmp_path/'out','smoke')


def test_reproducibility_and_progress():
    c=study.case_plan('smoke')[0];progress=[]
    a=study.experiment(c,lambda i,n:progress.append((i,n)));b=study.experiment(c)
    assert a==b and progress==[(0,3),(1,3),(2,3)]


def test_failure_in_draw_propagates_without_success(tmp_path,monkeypatch):
    def fail(*a,**k):raise RuntimeError('explicit draw failure')
    monkeypatch.setattr(study,'_draw',fail)
    out=tmp_path/'out'
    with pytest.raises(RuntimeError,match='explicit draw failure'):study.run(out,'smoke')
    assert not (out/'summary.json').exists()
