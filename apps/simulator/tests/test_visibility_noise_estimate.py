from itertools import combinations
import numpy as np
import pytest
from vsora_simulator.visibility_moments import visibility_noise_moments
from vsora_simulator.visibility_noise_estimate import estimate_visibility_noise


def test_finite_sample_formula_and_metadata():
    s=np.array([[2,.6+.2j],[.6-.2j,3]])
    m=8;q=estimate_visibility_noise(s,m);v=s[0,1]
    np.testing.assert_allclose(q['complex_covariance'],(m*6-abs(v)**2)/(m*m-1))
    np.testing.assert_allclose(q['complex_pseudocovariance'],v*v/(m+1))
    assert q['conditional_ensemble_unbiased'] and not q['generating_truth_used']
    assert not q['distribution_gaussian_assumed'] and not q['covariance_inverted']


@pytest.mark.parametrize('m',[4,8,64,512])
def test_psd_and_joint_closure_radial_correction(m):
    from vsora_imaging.closure_noise import joint_closure_noise
    s=np.ones((4,4),complex)+np.eye(4)*.2
    q=estimate_visibility_noise(s,m);scale=abs(q['real_covariance']).max()
    assert np.linalg.eigvalsh(q['real_covariance']).min()>=-1e-12*scale
    if m==512:
        propagated=joint_closure_noise(q['mean'],q['real_covariance'],q['pairs'])
        naive=joint_closure_noise(q['mean'],q['plug_in_real_covariance'],q['pairs'])
        # The removed plug-in bias is a common *radial* visibility error.
        # Its Jacobian contribution to both kinds of closure is zero.
        np.testing.assert_allclose(propagated['joint_covariance'],naive['joint_covariance']/(1-1/m**2),rtol=1e-11,atol=1e-17)


def test_complex_station_gain_covariance_transformation():
    rng=np.random.default_rng(46);a=rng.normal(size=(4,3))+1j*rng.normal(size=(4,3));s=a @ a.conj().T+np.eye(4)
    q=estimate_visibility_noise(s,16);gains=np.array([.4,3,1.5,.75])*np.exp(1j*np.array([.3,-1,2,1.1]))
    transformed=gains[:,None]*s*gains.conj()[None,:];r=estimate_visibility_noise(transformed,16)
    i,j=q['pairs'].T;baseline=gains[i]*gains[j].conj()
    matrix=np.block([[np.diag(baseline.real),-np.diag(baseline.imag)],
        [np.diag(baseline.imag),np.diag(baseline.real)]])
    np.testing.assert_allclose(r['real_covariance'],matrix @ q['real_covariance'] @ matrix.T,rtol=1e-11,atol=1e-14)


@pytest.mark.parametrize('m',[4,16])
def test_actual_voltage_ensemble_unbiased(m):
    rng=np.random.default_rng(46+m);s=np.array([[2.,.6+.2j],[.6-.2j,3.]])
    trials=65536;z=(rng.normal(size=(trials,m,2))+1j*rng.normal(size=(trials,m,2)))/np.sqrt(2)
    x=z @ np.linalg.cholesky(s).T;sample=np.einsum('tmi,tmj->tij',x,x.conj())/m
    # Independent scalar implementation of the two-station estimator.
    gamma=(m*sample[:,0,0].real*sample[:,1,1].real-abs(sample[:,0,1])**2)/(m*m-1)
    pseudo=sample[:,0,1]**2/(m+1)
    truth=visibility_noise_moments(s,m)
    for values,expected in [(gamma,truth['complex_covariance'][0,0]),(pseudo,truth['complex_pseudocovariance'][0,0])]:
        assert abs(values.mean()-expected)<6*values.std()/np.sqrt(trials)+1e-8
    for k in range(8):
        q=estimate_visibility_noise(sample[k],m)
        np.testing.assert_allclose(q['complex_covariance'][0,0],gamma[k],rtol=1e-12)
        np.testing.assert_allclose(q['complex_pseudocovariance'][0,0],pseudo[k],rtol=1e-12)


@pytest.mark.parametrize('m',[True,0,1,3,4.,2**53+1])
def test_invalid_sample_counts(m):
    with pytest.raises(ValueError):estimate_visibility_noise(np.eye(4),m)


@pytest.mark.parametrize('s',[np.ones(4),np.ones((2,3)),np.eye(1),np.eye(33),
    np.array([[1,np.nan],[np.nan,1]]),np.array([[1,2],[2,1]]),np.array([[1,1],[0,1]])])
def test_invalid_station_covariances(s):
    with pytest.raises(ValueError):estimate_visibility_noise(s,64)


def test_full_baseline_batch_formula_matches_public_estimator():
    from workflows.sample_noise_validation import batch_covariance
    rng=np.random.default_rng(91);a=rng.normal(size=(8,4,3))+1j*rng.normal(size=(8,4,3))
    s=a @ a.conj().transpose(0,2,1)+np.eye(4)
    pairs=np.array(list(combinations(range(4),2)));plugin,corrected=batch_covariance(s,16,pairs)
    for k in range(8):
        q=estimate_visibility_noise(s[k],16,pairs)
        np.testing.assert_allclose(q['real_covariance'],corrected[k],rtol=1e-12,atol=1e-14)
        np.testing.assert_allclose(q['plug_in_real_covariance'],plugin[k],rtol=1e-12,atol=1e-14)


def test_sample_noise_workflow_retains_conditions(tmp_path):
    from workflows.sample_noise_validation import run
    q=run(tmp_path/'noise',256)
    assert len(q['cases'])==4 and not q['generating_truth_used_in_estimator']
    assert not q['actual_hardware_data'] and not q['physical_iq_vdif_processed']
    assert not q['covariance_confidence_calibrated_for_hardware']
    for r in q['cases']:
        assert r['positive_semidefinite_estimates']==256 and len(r['examples'])==1
    assert (tmp_path/'noise/sample-noise.png').is_file()


@pytest.mark.parametrize('trials',[True,255,65537,2.5])
def test_sample_noise_workflow_invalid_count(tmp_path,trials):
    from workflows.sample_noise_validation import run
    with pytest.raises(ValueError):run(tmp_path/'invalid',trials)
    assert not (tmp_path/'invalid').exists()
