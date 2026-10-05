import numpy as np
import pytest
from workflows.bispectrum_average_validation import covariance_support,summarize,experiment


def test_gaussian_reference_control():
    values=np.random.default_rng(68).normal(size=(8192,2))
    q=summarize(values,np.eye(2),70)
    assert q['means_and_covariances_within_6se'] and q['all_residuals_within_covariance_support']
    assert all(r['gaussian_control_within_6_reference_se'] for r in q['coverage_references'])
    assert all(r['u3_within_6_reference_se'] for r in q['coverage_references'])


def test_correct_covariance_does_not_imply_gaussian_coverage():
    values=np.zeros((10000,1));values[:50]=10;values[50:100]=-10
    q=summarize(values,np.ones((1,1)),71)
    assert q['means_and_covariances_within_6se'] and q['mean_mahalanobis_per_rank']==1
    assert q['coverage_references'][0]['u3_coverage_fraction']==.99
    assert not q['coverage_references'][0]['u3_within_6_reference_se']
    assert not q['gaussian_u3_distribution_verified']


@pytest.mark.parametrize('covariance',[[],[[1,2]],[[1,2],[0,1]],[[-1]],[[float('nan')]],[[1j]],np.ma.array([[1.]])])
def test_invalid_covariance_support(covariance):
    with pytest.raises(ValueError):covariance_support(covariance)


def test_zero_covariance_refuses_nonzero_rank_reference():
    with pytest.raises(ValueError,match='nonzero'):covariance_support(np.zeros((2,2)))


def test_singular_support_checks_discarded_directions():
    rng=np.random.default_rng(69);values=np.c_[rng.normal(size=8192),np.zeros(8192)]
    q=summarize(values,np.diag([1.,0.]),72)
    assert q['real_parameter_rank']==1 and q['all_residuals_within_covariance_support']
    values[:,1]=1
    assert not summarize(values,np.diag([1.,0.]),72)['all_residuals_within_covariance_support']


@pytest.mark.parametrize('trials',[True,0,1023,32769,8192.5])
def test_invalid_trials(trials):
    with pytest.raises(ValueError,match='trials'):experiment('zero',trials)


@pytest.mark.parametrize('seed',[True,-1,2**32,1.5])
def test_invalid_seed(seed):
    with pytest.raises(ValueError,match='seed'):experiment('zero',1024,seed)


@pytest.mark.parametrize('moments_ok',[True,False])
def test_run_records_moment_failure_but_not_gaussian_coverage_failure(tmp_path,monkeypatch,moments_ok):
    import json
    from workflows import bispectrum_average_validation as module
    row={'all_residuals_within_covariance_support':True,'means_and_covariances_within_6se':moments_ok,
         'coverage_references':[{'gaussian_control_within_6_reference_se':True,'u3_within_6_reference_se':False}]}
    monkeypatch.setattr(module,'experiment',lambda *args:[row])
    monkeypatch.setattr(module,'plot',lambda *args:None)
    out=tmp_path/'validation'
    if moments_ok:
        q=module.run(out);assert q['state']=='complete'
    else:
        with pytest.raises(RuntimeError,match='criterion'):module.run(out)
    q=json.loads((out/'summary.json').read_text())
    assert q['state']==('complete' if moments_ok else 'failed_validation')
    assert q['gaussian_u3_coverage_is_not_a_pass_requirement']
    assert not q['gaussian_u3_distribution_verified']
    with pytest.raises(FileExistsError):module.run(out)
