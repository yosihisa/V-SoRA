from itertools import combinations
import numpy as np
import pytest
from vsora_imaging.closure import form_closures, wrap_phase
from vsora_imaging.closure_noise import joint_closure_noise
from vsora_simulator.visibility_moments import visibility_noise_moments

PAIRS=np.array(list(combinations(range(4),2)))


def test_independent_circular_matches_existing_closure_covariance():
    v=np.array([1,2,3,4,2,1],complex)*np.exp(1j*np.arange(6)*.4)
    variances=np.arange(1,7)*1e-5;c=np.diag(np.r_[variances,variances])
    q=joint_closure_noise(v,c,PAIRS);old=form_closures(v,1/variances,PAIRS)
    for name,selection in [('phase',slice(0,4)),('logamp',slice(4,6))]:
        a=old[name+'_matrix'];expected=(a*old['baseline_variance']) @ a.T
        np.testing.assert_allclose(q['joint_values'][selection],old[name],atol=1e-14)
        np.testing.assert_allclose(q['joint_covariance'][selection,selection],expected,rtol=1e-12,atol=1e-18)
    np.testing.assert_allclose(q['joint_covariance'][:4,4:],0,atol=1e-18)


@pytest.mark.parametrize('rho',[.2,.5,.9,1.])
def test_shared_point_closure_covariance_ratio(rho):
    s=np.ones((4,4));np.fill_diagonal(s,1/rho)
    m=512;noise=visibility_noise_moments(s,m)
    q=joint_closure_noise(noise['mean'],noise['real_covariance'],PAIRS)
    circular=joint_closure_noise(noise['mean'],np.eye(12)/(2*m*rho*rho),PAIRS)
    np.testing.assert_allclose(q['joint_covariance'],circular['joint_covariance']*(1-rho)**2,atol=1e-17,rtol=1e-12)
    assert q['joint_valid'].all() and not q['closure_distribution_gaussian_guaranteed']


def test_gain_invariance_and_phase_amplitude_cross_covariance():
    rng=np.random.default_rng(44);a=rng.normal(size=(4,3))+1j*rng.normal(size=(4,3))
    s=a @ a.conj().T+np.eye(4)*4
    noise=visibility_noise_moments(s,65536);q=joint_closure_noise(noise['mean'],noise['real_covariance'],PAIRS)
    assert q['joint_valid'].all() and abs(q['joint_covariance'][:4,4:]).max()>1e-8
    gains=np.array([.4,3.,1.5,.75])*np.exp(1j*np.array([.3,-1,2,1.1]))
    transformed=gains[:,None]*s*gains.conj()[None,:]
    noise2=visibility_noise_moments(transformed,65536)
    q2=joint_closure_noise(noise2['mean'],noise2['real_covariance'],PAIRS)
    np.testing.assert_allclose(wrap_phase(q2['joint_values'][:4]-q['joint_values'][:4]),0,atol=1e-14)
    np.testing.assert_allclose(q2['joint_values'][4:],q['joint_values'][4:],atol=1e-14)
    np.testing.assert_allclose(q2['joint_covariance'],q['joint_covariance'],rtol=1e-11,atol=1e-16)


def test_jacobian_finite_difference():
    rng=np.random.default_rng(45);v=np.exp(rng.normal(size=6)+1j*rng.normal(size=6))
    q=joint_closure_noise(v,np.eye(12)*1e-8,PAIRS)
    for k in range(12):
        delta=np.zeros(6,complex);delta[k%6]=1e-6*(1 if k<6 else 1j)
        plus=joint_closure_noise(v+delta,np.eye(12)*1e-8,PAIRS)['joint_values']
        minus=joint_closure_noise(v-delta,np.eye(12)*1e-8,PAIRS)['joint_values']
        difference=plus-minus;difference[:4]=wrap_phase(difference[:4])
        np.testing.assert_allclose(difference/2e-6,q['joint_jacobian'][:,k],rtol=1e-8,atol=1e-8)


def test_zero_and_low_snr_mask_are_not_measurements():
    v=np.ones(6,complex);v[0]=0;v[1]=.01
    q=joint_closure_noise(v,np.eye(12)*.0001,PAIRS)
    assert not q['baseline_valid'][:2].any() and not q['joint_valid'].all()
    assert (q['joint_values'][~q['joint_valid']]==0).all()
    assert (q['joint_covariance'][~q['joint_valid']]==0).all()
    assert (q['joint_jacobian'][~q['joint_valid']]==0).all()


def test_no_closures_is_empty_not_a_detection():
    q=joint_closure_noise(np.ones(1,complex),np.eye(2)*.001,np.array([[0,1]]))
    assert q['joint_covariance'].shape==(0,0) and q['joint_values'].size==0


def test_workflow_voltage_and_visibility_models_are_separate(tmp_path):
    from workflows.closure_noise_validation import run
    q=run(tmp_path/'noise',256)
    assert len(q['cases'])==8 and not q['actual_hardware_data']
    assert not q['production_rml_noise_model_changed']
    assert {r['noise_generation'] for r in q['cases']}=={'gaussian_visibility','gaussian_voltage'}
    for r in q['cases']:
        assert r['minimum_mean_baseline_snr']>=5 and r['trials']==256
        assert not r['selection_on_observed_visibility'] and not r['physical_iq_vdif_processed']
        assert np.isfinite(r['empirical_joint_covariance']).all()
    assert q['cases'][-1]['maximum_calculated_phase_logamp_covariance']>1e-8
    assert (tmp_path/'noise/closure-noise.png').is_file()


def test_actual_gaussian_voltage_closure_covariance_first_order():
    from workflows.closure_noise_validation import experiment
    mode=np.exp(1j*np.array([0.,.4,1.1,2.2]))
    s=np.ones((4,4))+.7*mode[:,None]*mode.conj()[None,:]+1.5*np.eye(4)
    r=experiment('two-components',s,'gaussian_voltage',8192,91)
    # Finite draw tolerance includes first-order/nonlinear discrepancy, not a
    # claim that all physical observations have this covariance accuracy.
    assert r['maximum_normalized_covariance_difference']<.12
    assert r['maximum_calculated_phase_logamp_covariance']>1e-8


@pytest.mark.parametrize('trials',[True,255,65537,1.5])
def test_workflow_invalid_trials(tmp_path,trials):
    from workflows.closure_noise_validation import run
    with pytest.raises(ValueError):run(tmp_path/'invalid',trials)
    assert not (tmp_path/'invalid').exists()


@pytest.mark.parametrize('kind',['real_mean','nan_mean','wrong_mean','wrong_covariance','complex_covariance',
    'nan_covariance','asymmetric','negative','low_threshold','nan_threshold','too_many_stations','tiny_overflow'])
def test_invalid_inputs(kind):
    v=np.ones(6,complex);c=np.eye(12)*.001;p=PAIRS;threshold=5.
    if kind=='real_mean':v=v.real
    elif kind=='nan_mean':v[0]=np.nan
    elif kind=='wrong_mean':v=v[:-1]
    elif kind=='wrong_covariance':c=c[:-1]
    elif kind=='complex_covariance':c=c.astype(complex)
    elif kind=='nan_covariance':c[0,0]=np.nan
    elif kind=='asymmetric':c[0,1]=.001
    elif kind=='negative':c[0,0]=-.001
    elif kind=='low_threshold':threshold=4.
    elif kind=='nan_threshold':threshold=np.nan
    elif kind=='too_many_stations':p=np.array(list(combinations(range(9),2)));v=np.ones(len(p),complex);c=np.eye(2*len(p))*.001
    elif kind=='tiny_overflow':v[:]=1e-320;c[:]=0
    with pytest.raises(ValueError):joint_closure_noise(v,c,p,threshold)
