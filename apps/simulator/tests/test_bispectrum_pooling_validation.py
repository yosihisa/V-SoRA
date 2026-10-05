import json
import numpy as np
import pytest
from vsora_simulator.bispectrum_moments import gaussian_distinct_bispectrum_moments
from vsora_simulator.bispectrum_average import gaussian_averaged_bispectrum_moments
from workflows import bispectrum_pooling_validation as workflow


@pytest.mark.parametrize('groups',[1,4,16])
def test_null_covariance_ratio_matches_closed_form(groups):
    m=32;n=m*groups
    average=gaussian_averaged_bispectrum_moments(np.eye(4),m,groups)
    pooled=gaussian_distinct_bispectrum_moments(np.eye(4),n)
    expected=(n-1)*(n-2)/((m-1)*(m-2))
    np.testing.assert_allclose(average['complex_covariance'].diagonal()/pooled['complex_covariance'].diagonal(),expected,rtol=1e-13)


@pytest.mark.parametrize('trials,seed',[(True,74),(1023,74),(32769,74),(1024.,74),(1024,True),(1024,-1),(1024,2**32)])
def test_fixed_trial_and_seed_range(trials,seed):
    with pytest.raises(ValueError):workflow.validate_trials(trials,seed)


def test_mean_and_covariance_summary_accepts_exact_moments_and_reports_failure():
    values=np.array([-1,1]*512,dtype=complex)[:,None];covariance=np.diag([1.,0.])
    q=workflow.summarize(values,np.array([0j]),covariance)
    assert q['all_calculated_moments_within_6se']
    assert not workflow.summarize(values,np.array([1j]),covariance)['all_calculated_moments_within_6se']
    assert not workflow.summarize(values,np.array([0j]),np.zeros((2,2)))['all_calculated_moments_within_6se']


@pytest.mark.parametrize('passed',[True,False])
def test_fixed_experiment_preserves_output_on_failure(tmp_path,monkeypatch,passed):
    called=[]
    def experiment(label,trials,seed):
        called.append((label,trials,seed))
        return [{'model':label,'independent_groups':g,'all_calculated_moments_within_6se':passed} for g in workflow.GROUPS]
    def phase(trials,seed):
        called.append(('phase',trials,seed))
        return {'all_calculated_moments_within_6se':passed,'fixed_per_group_phase_invariance_checked':True}
    monkeypatch.setattr(workflow,'experiment',experiment);monkeypatch.setattr(workflow,'phase_experiment',phase)
    monkeypatch.setattr(workflow,'plot',lambda *args:None)
    out=tmp_path/'run'
    if passed:workflow.run(out)
    else:
        with pytest.raises(RuntimeError):workflow.run(out)
    q=json.loads((out/'summary.json').read_text());assert q['state']==('complete' if passed else 'failed_validation')
    assert len(q['cases'])==15 and q['trials_per_model']==8192
    assert called==[(label,8192,74+i) for i,label in enumerate(workflow.MODELS)]+[('phase',8192,79)]
    assert not q['observed_frequency_coaddition_performed'] and not q['frequency_phase_alignment_performed']
    with pytest.raises(FileExistsError):workflow.run(out)
