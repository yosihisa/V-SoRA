"""Finite software checks; full holdout experiments are run separately."""
import math
import numpy as np
import pytest
from vsora_simulator.known_template_validation import case_plan,error_rate_summary,empirical_auc,experiment,run

def test_fixed_plan_and_control_roles():
    p=case_plan();assert len(p)==9 and len({c['seed'] for c in p})==9
    assert all(c['training_per_label']==128 and c['test_per_label']==512 for c in p)
    assert [c['receiver_model_matches_training'] for c in p]==[True]*6+[False]*2+[True]
    assert p[-1]['zero_sky_control']
    assert all(c['modes'] in (512,19200) for c in p)
    assert len(case_plan('smoke'))==3
    with pytest.raises(ValueError):case_plan('unknown')

@pytest.mark.parametrize('errors,n',[(0,512),(512,512),(2,5),(4,10)])
def test_exact_binomial_interval_with_polynomial(errors,n):
    q=error_rate_summary(errors,n);low,high=q['clopper_pearson_interval']
    assert q['fraction']==errors/n and not q['actual_observation_confidence_interval']
    if errors==0:
        assert low==0
        assert high==pytest.approx(-math.expm1(math.log(.025)/n),abs=2e-12)
    else:
        tail=sum(math.comb(n,k)*low**k*(1-low)**(n-k) for k in range(errors,n+1))
        assert tail==pytest.approx(.025,abs=2e-11)
    if errors==n:assert high==1
    else:
        tail=sum(math.comb(n,k)*high**k*(1-high)**(n-k) for k in range(errors+1))
        assert tail==pytest.approx(.025,abs=2e-11)

@pytest.mark.parametrize('errors,n',[(-1,10),(11,10),(True,10),(1,True),(1.,10),(0,0),(0,65537)])
def test_invalid_mc_counts(errors,n):
    with pytest.raises(ValueError):error_rate_summary(errors,n)

@pytest.mark.parametrize('point,casa,expected',[
    ([0.,1.],[2.,3.],1.),([2.,3.],[0.,1.],0.),([1.,1.],[1.,1.],.5),
    ([0.,1.],[1.,2.],.875)])
def test_auc_order_and_ties(point,casa,expected):
    assert empirical_auc(np.array(point),np.array(casa))==expected

@pytest.mark.parametrize('point,casa',[
    ([],[1.]),([1.],[]),([np.nan],[1.]),([1j],[1.]),
    (np.ma.array([1.],mask=True),[2.]),([[1.]], [2.]),(['x'],[1.])])
def test_invalid_auc(point,casa):
    with pytest.raises(ValueError):empirical_auc(np.asarray(point) if not np.ma.isMaskedArray(point) else point,np.asarray(casa))

def test_edited_plan_rejected():
    p=case_plan('smoke')[0];p['seed']+=1
    with pytest.raises(ValueError):experiment(p)

def test_smoke_native_outputs_and_no_overwrite(tmp_path):
    out=tmp_path/'study';q=run(out,'smoke')
    assert len(q['cases'])==3 and not q['image_likelihood_defined']
    assert q['independent_voltage_windows_generated']==3*(16+32)
    for c in q['cases']:
        assert c['state']=='complete' and len(c['point_test_scores'])==16
        assert c['training_sky_models']==c['test_sky_models']
        assert c['assumed_source_total_flux_jy_by_label']==([0.,0.] if c['zero_sky_control'] else [1000.,1000.])
        assert c['test_used_for_threshold_or_direction'] is False
        assert c['auc_pair_count']==256 and not c['auc_pairs_treated_as_independent']
        assert c['point_generation']['gain_predictions_identical']
        assert c['casa_generation']['gain_predictions_identical']
        assert c['false_casa_on_point']['trials']==16
    with pytest.raises(FileExistsError):run(out,'smoke')
