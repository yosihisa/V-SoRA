import json
import numpy as np
import pytest
from vsora_simulator import phase_threshold_validation as study


@pytest.mark.parametrize('seed',range(8))
def test_threshold_against_independent_brute_force(seed):
    rng=np.random.default_rng(seed);p=rng.integers(-3,4,5).astype(float);c=rng.integers(-3,4,7).astype(float)
    candidates=sorted(set([0.,*p,*c,float(np.nextafter(min(p.min(),c.min()),-np.inf))]))
    def loss(t):return sum(v>t for v in p)*len(c)+sum(v<=t for v in c)*len(p)
    expected=min(candidates,key=lambda t:(loss(t),abs(t),t));q=study.learn_threshold(p,c)
    assert q['threshold']==expected and q['training_false_casa']==sum(p>expected) and q['training_missed_casa']==sum(c<=expected)
    assert q['training_balanced_accuracy']==pytest.approx(1-loss(expected)/(2*len(p)*len(c)))


@pytest.mark.parametrize('value',[[],[np.nan],[np.inf],[True],[1+0j],[[1.]],['1'],[None],np.zeros(65537)])
def test_invalid_scores_rejected(value):
    with pytest.raises(ValueError):study.learn_threshold(value,[1.])
    with pytest.raises(ValueError):study.learn_threshold([1.],value)


def test_zero_ties_direction_and_inputs_unchanged():
    p=np.array([-2.,-1.]);c=np.array([1.,2.]);a=p.copy();b=c.copy()
    q=study.learn_threshold(p,c);assert q['threshold']==0 and q['training_balanced_accuracy']==1
    np.testing.assert_array_equal(p,a);np.testing.assert_array_equal(c,b)
    q=study.learn_threshold([0.,0.],[0.,0.]);assert q['threshold']==0 and q['training_balanced_accuracy']==.5
    q=study.learn_threshold([2.,2.],[-2.,-2.]);assert q['training_balanced_accuracy']==.5 and q['direction']=='score>threshold_is_casa'
    with pytest.raises(TypeError):study.learn_threshold(p,c,test_scores=[0.])


def test_conditional_interval_and_unresolved():
    q=study._evaluate([-1.,-2.],[1.,2.],0.,True);assert q['balanced_accuracy']==1
    assert q['false_casa_on_point']['conditional_fixed_training_binomial_confidence_level']==.95
    assert not q['training_variability_included'] and not q['auc_pairs_independent']
    assert study._evaluate([None,-1.],[1.,2.],0.,True)['balanced_accuracy'] is None
    assert study._evaluate([-1.,-2.],[1.,2.],None,True)['balanced_accuracy'] is None


@pytest.mark.parametrize('profile',[False,None,1,'bad'])
def test_invalid_plan(profile,tmp_path):
    with pytest.raises(ValueError):study.run(tmp_path/'out',profile)
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('key,value',[('modes',1),('seed',1),('training_per_label',1),('test_per_label',1),('sefd_jy',1.),('extra','x')])
def test_modified_case_rejected(key,value):
    c=study.case_plan('smoke')[0];c[key]=value
    with pytest.raises(ValueError):study.experiment(c)


def test_smoke_independent_roles_fixed_seed_and_no_overwrite(tmp_path):
    q=study.run(tmp_path/'out','smoke');assert q['independent_voltage_windows_generated']==32
    assert len(study.case_plan())==3 and sum(2*(c['training_per_label']+c['test_per_label']) for c in study.case_plan())==768
    assert json.loads((tmp_path/'out/summary.json').read_text())==q
    for c in q['cases']:
        assert len({tuple(g['rng_seed_sequence']) for g in c['data'].values()})==4
        assert not c['learned']['test_data_used']
        assert c['metrics']['fixed_zero']['empirical_auroc']==c['metrics']['learned_threshold']['empirical_auroc']
    zero=q['cases'][-1];assert zero['learned']['threshold']==0 and zero['metrics']['learned_threshold']['balanced_accuracy']==.5
    assert study.experiment(study.case_plan('smoke')[0])==q['cases'][0]
    with pytest.raises(FileExistsError):study.run(tmp_path/'out','smoke')


def test_learner_receives_training_profile_scores_only(monkeypatch):
    original=study.learn_threshold;seen=[]
    def record(point,casa):seen.append((list(point),list(casa)));return original(point,casa)
    monkeypatch.setattr(study,'learn_threshold',record);q=study.experiment(study.case_plan('smoke')[0])
    assert seen==[([v['phase_profile_score'] for v in q['data']['training_point']['rows']],[v['phase_profile_score'] for v in q['data']['training_casa']['rows']])]


def test_unresolved_training_has_no_learned_threshold_or_test_prediction(monkeypatch):
    original=study._draw
    def unresolved(mode,role,case,c0,c1):
        q=original(mode,role,case,c0,c1)
        if role==10:q['rows'][0]['phase_profile_score']=None
        return q
    monkeypatch.setattr(study,'_draw',unresolved);q=study.experiment(study.case_plan('smoke')[0])
    assert q['learned']['state']=='training_unresolved' and q['learned']['threshold'] is None
    assert q['metrics']['learned_threshold']['balanced_accuracy'] is None
    assert all(r['learned_prediction_casa'] is None for role in ('test_point','test_casa') for r in q['data'][role]['rows'])
