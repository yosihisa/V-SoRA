import json
import numpy as np
import pytest
from scipy.stats import multivariate_normal
from vsora_simulator import gaussian_phase_template as study


@pytest.mark.parametrize('n',[2,3,8])
def test_raw_voltage_score_against_independent_real_gaussian(n):
    rng=np.random.default_rng(104);a=rng.normal(size=(n,n))+1j*rng.normal(size=(n,n))
    c=a @ a.conj().T+np.eye(n);c1=c+np.eye(n)
    x=(rng.normal(size=(5,n))+1j*rng.normal(size=(5,n))) @ np.linalg.cholesky(c).T/np.sqrt(2)
    def real_score(cov):
        real=.5*np.block([[cov.real,-cov.imag],[cov.imag,cov.real]])
        return np.sum(multivariate_normal.logpdf(np.concatenate([x.real,x.imag],axis=1),cov=real))
    assert study._voltage_score(c,c1,x)==pytest.approx(real_score(c1)-real_score(c),abs=2e-11)


def test_fixed_plans():
    p=study.case_plan();assert len(p)==7 and sum(2*c['test_per_label'] for c in p)==896
    assert [c['modes'] for c in p]==[512]*3+[19200]*3+[512]
    assert len({(c['seed'],role) for c in p for role in (0,1)})==14
    assert p[-1]['zero_sky_control'] and len(study.case_plan('smoke'))==3


@pytest.mark.parametrize('profile',[None,False,1,'bad'])
def test_invalid_profile_creates_no_output(tmp_path,profile):
    with pytest.raises(ValueError):study.run(tmp_path/'out',profile)
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('case',[None,[],{'profile':'full'},{'profile':'bad'}])
def test_invalid_case(case):
    with pytest.raises(ValueError):study.experiment(case)


@pytest.mark.parametrize('key,value',[('modes',1),('seed',1),('test_per_label',1),
    ('sefd_jy',1.),('zero_sky_control',0),('max_iterations',1),('extra','x')])
def test_modified_cases_rejected(key,value):
    c=study.case_plan('smoke')[0];c[key]=value
    with pytest.raises(ValueError):study.experiment(c)


@pytest.mark.parametrize('point,casa,accuracy',[([-1.,-2.],[1.,2.],1.),([1.,-1.],[1.,-1.],.5),([1.,2.],[-1.,-2.],0.)])
def test_metrics_fixed_threshold_and_intervals(point,casa,accuracy):
    q=study._metrics(point,casa);assert q['balanced_accuracy']==accuracy
    for role in ('false_casa_on_point','missed_casa'):
        b=q[role];assert b['trials']==2 and b['clopper_pearson_interval'][0]<=b['fraction']<=b['clopper_pearson_interval'][1]
        assert b['fixed_algorithm_and_generator_binomial_confidence_level']==.95
    assert not q['auc_pairs_independent'] and not q['image_confidence_defined']


@pytest.mark.parametrize('point,casa',[([None,0.],[1.,2.]),([1.,2.],[None,0.])])
def test_unresolved_has_no_success_only_overall_metrics(point,casa):
    q=study._metrics(point,casa);assert q['state']=='unresolved_windows'
    assert q['balanced_accuracy'] is None and q['empirical_auroc'] is None
    assert q['false_casa_on_point'] is None and q['missed_casa'] is None
    assert not q['success_only_metric_reported']


def test_smoke_pairing_zero_no_overwrite_and_reproducibility(tmp_path):
    out=tmp_path/'out';events=[];q=study.run(out,'smoke',lambda i,n,label:events.append((i,n,label)))
    assert len(events)==3 and q['independent_voltage_windows_generated']==12
    assert json.loads((out/'summary.json').read_text())==q
    assert study.experiment(study.case_plan('smoke')[0])==q['cases'][0]
    for c in q['cases']:
        for role in ('point_generation','casa_generation'):
            g=c[role];assert len(g['rows'])==2
            assert sum(map(sum,g['oracle_by_profile_prediction_counts_on_resolved_only']))+g['unresolved_windows']==2
            assert not g['profile_received_true_phase'] and g['same_voltage_used_for_both_scores']
            for row in g['rows']:
                assert row['oracle_prediction_casa']==(row['oracle_score']>0)
                assert row['known_phase_transport_abs_difference']<2e-7
                if row['phase_profile_score'] is not None:assert row['profile_prediction_casa']==(row['phase_profile_score']>0)
            assert g['rows'][0]['direct_voltage_oracle_abs_difference']<2e-7
            if g['rows'][0]['phase_profile_score'] is not None:
                assert g['rows'][0]['direct_voltage_profile_abs_difference']<2e-7
                assert g['rows'][0]['profile_data_phase_transport_abs_difference']<2e-7
    zero=q['cases'][-1];assert zero['metrics']['oracle']['balanced_accuracy']==zero['metrics']['phase_profile']['balanced_accuracy']==.5
    with pytest.raises(FileExistsError):study.run(out,'smoke')
    assert json.loads((out/'summary.json').read_text())==q


def test_profile_failure_kept_in_denominator_and_not_scored(monkeypatch):
    seen=[]
    def unfinished(c0,c1,s,m,*,max_iterations):
        seen.append((c0.shape,s.shape,m,max_iterations))
        raise study.PhaseProfileConvergenceError('both phase fits must reach verified stationarity')
    monkeypatch.setattr(study,'compare_phase_profiles',unfinished)
    q=study.experiment(study.case_plan('smoke')[0]);assert len(seen)==4
    assert q['unresolved_profile_windows']==4 and q['metrics']['phase_profile']['balanced_accuracy'] is None
    assert q['metrics']['oracle']['state']=='complete'
    assert all(row['profile_prediction_casa'] is None for role in ('point_generation','casa_generation') for row in q[role]['rows'])


def test_unexpected_optimizer_error_is_not_hidden(monkeypatch):
    def broken(*args,**kwargs):raise study.PhaseProfileConvergenceError('optimizer returned invalid phases')
    monkeypatch.setattr(study,'compare_phase_profiles',broken)
    with pytest.raises(study.PhaseProfileConvergenceError,match='invalid phases'):study.experiment(study.case_plan('smoke')[0])
