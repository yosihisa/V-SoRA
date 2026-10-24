from types import SimpleNamespace
import numpy as np
import pytest
from scipy.stats import multivariate_normal

from vsora_correlator import gaussian_phase_profile as study
from vsora_correlator.gaussian_likelihood import gaussian_nll, sample_second_moment


def problem(n,seed=103,m=37):
    rng=np.random.default_rng(seed)
    a=rng.normal(size=(n,n))+1j*rng.normal(size=(n,n))
    c=a @ a.conj().T+np.eye(n)
    phi=rng.uniform(-np.pi,np.pi,n);g=np.exp(1j*phi)
    generated=g[:,None]*c*g.conj()[None,:]
    x=(rng.normal(size=(m,n))+1j*rng.normal(size=(m,n)))@np.linalg.cholesky(generated).T/np.sqrt(2)
    return c,sample_second_moment(x),x,generated


def matrix(fit):
    a=np.asarray(fit['fitted_covariance_real_imag']);return a[...,0]+1j*a[...,1]


@pytest.mark.parametrize('n',[2,3,8])
def test_cost_and_gradient_against_direct_nll_and_finite_difference(n):
    c,s,x,_=problem(n)
    _,_,a,scale,ratio,m=study._problem(c,s,len(x))
    theta=np.linspace(-.7,.9,n-1);p=np.exp(1j*np.r_[0.,theta])
    value,g=study._phase_cost_gradient(theta,a);zero=study._phase_cost_gradient(np.zeros(n-1),a)[0]
    transformed=p[:,None]*c*p.conj()[None,:]
    assert (value-zero)*scale*ratio*m==pytest.approx(gaussian_nll(transformed,s,m)-gaussian_nll(c,s,m),abs=4e-11)
    numeric=[]
    for i in range(n-1):
        step=np.eye(n-1)[i]*1e-6
        numeric.append((study._phase_cost_gradient(theta+step,a)[0]-study._phase_cost_gradient(theta-step,a)[0])/2e-6)
    np.testing.assert_allclose(g,numeric,rtol=1e-6,atol=3e-9)


@pytest.mark.parametrize('seed',[103,104,105])
def test_two_station_analytic_minimum(seed):
    c,s,x,_=problem(2,seed);m=len(x);k=np.linalg.solve(c,np.eye(2))
    expected=m*(np.linalg.slogdet(c)[1]+np.sum(k.diagonal().real*s.diagonal().real)-2*abs(k[1,0]*s[0,1]))
    q=study.fit_station_phases(c,s,m)
    assert q['state']=='analytic_two_station' and q['global_minimum_for_this_phase_objective_proved']
    assert q['nll_without_constant']==pytest.approx(expected,abs=2e-12)
    assert q['candidate_phase_rad'][0]==0 and q['optimizer_runs']==[]


@pytest.mark.parametrize('seed',[103,104,105])
def test_three_station_dense_grid(seed):
    c,s,x,_=problem(3,seed);q=study.fit_station_phases(c,s,len(x))
    assert q['state']=='stationary_candidate' and not q['global_minimum_for_this_phase_objective_proved']
    _,_,a,scale,ratio,m=study._problem(c,s,len(x))
    angle=np.linspace(-np.pi,np.pi,181,endpoint=False)
    p1,p2=np.meshgrid(np.exp(1j*angle),np.exp(1j*angle))
    grid=2*(a[0,1]*p1+a[0,2]*p2+a[1,2]*p2*p1.conj()).real
    assert q['phase_dependent_trace_per_mode']<=float(np.min(grid))*scale*ratio+1e-8
    assert q['gradient_inf_norm_normalized']<=1e-6


@pytest.mark.parametrize('n',[1,3,8])
def test_phase_independent_and_unidentified_not_claimed(n):
    c=np.diag(np.arange(1,n+1));s=np.eye(n)
    q=study.fit_station_phases(c,s,16)
    assert q['state']=='phase_independent' and q['candidate_phase_rad']==[0.]*n
    assert not q['physical_phase_identification_verified']
    assert q['global_minimum_for_this_phase_objective_proved']
    assert q['nll_without_constant']==pytest.approx(gaussian_nll(c,s,16))


@pytest.mark.parametrize('n',[2,3,8])
def test_known_phase_transport_and_same_model_family(n):
    c,s,x,_=problem(n);m=len(x)
    phase=np.exp(1j*np.linspace(-1.1,2.2,n));change=lambda a:phase[:,None]*a*phase.conj()[None,:]
    a=study.fit_station_phases(c,s,m);b=study.fit_station_phases(c,change(s),m)
    assert a['state']!='not_converged' and b['state']!='not_converged'
    assert b['nll_without_constant']==pytest.approx(a['nll_without_constant'],abs=3e-9)
    q=study.compare_phase_profiles(c,change(c),s,m)
    assert abs(q['log_likelihood1_minus0'])<3e-8
    same=study.compare_phase_profiles(c,c,s,m)
    assert same['log_likelihood1_minus0']==0
    assert not same['calibrated_hypothesis_test_defined'] and not same['image_probability_defined']


@pytest.mark.parametrize('scale',[1e-120,1.,1e120])
def test_common_units_and_independent_real_gaussian(scale):
    c,s,x,_=problem(3);m=len(x)
    base=study.fit_station_phases(c,s,m);q=study.fit_station_phases(c*scale,s*scale,m)
    assert q['state']=='stationary_candidate'
    assert q['nll_without_constant']==pytest.approx(base['nll_without_constant']+3*m*np.log(scale),abs=3e-10)
    fitted=matrix(q)/scale
    real=.5*np.block([[fitted.real,-fitted.imag],[fitted.imag,fitted.real]])
    expected=-np.sum(multivariate_normal.logpdf(np.concatenate([x.real,x.imag],axis=1),cov=real))-m*3*np.log(np.pi)
    assert q['nll_without_constant']-m*3*np.log(scale)==pytest.approx(expected,abs=3e-10)


@pytest.mark.parametrize('n',[2,3,8])
def test_population_covariance_reaches_known_phase_family_minimum(n):
    c,_,_,generated=problem(n)
    q=study.fit_station_phases(c,generated,37)
    assert q['state']!='not_converged'
    assert q['nll_without_constant']==pytest.approx(gaussian_nll(generated,generated,37),abs=3e-8)


@pytest.mark.parametrize('m',[0,-1,True,1.,2**53+1])
def test_invalid_modes(m):
    with pytest.raises(ValueError):study.fit_station_phases([[1]],[[1]],m)


@pytest.mark.parametrize('limit',[0,-1,True,1.,1001,None])
def test_invalid_iteration_limit(limit):
    with pytest.raises(ValueError):study.fit_station_phases([[1]],[[1]],1,max_iterations=limit)


@pytest.mark.parametrize('c,s',[([[0]],[[1]]),([[np.nan]],[[1]]),([[1]],[[-1]]),
    ([[1]],np.ma.array([[1]],mask=False)),([[True]],[[1]]),(np.eye(2),np.eye(3)),(np.eye(17),np.eye(17))])
def test_invalid_matrices(c,s):
    with pytest.raises(ValueError):study.fit_station_phases(c,s,1)


def test_nonconvergence_not_a_profile_score(monkeypatch):
    def stopped(fun,x0,args,jac,method,options):
        return SimpleNamespace(x=x0,success=False,nit=0,message='forced stop')
    monkeypatch.setattr(study,'minimize',stopped)
    c,s,x,_=problem(3)
    q=study.fit_station_phases(c,s,len(x));assert q['state']=='not_converged'
    assert not any(a['optimizer_success'] for a in q['optimizer_runs'])
    with pytest.raises(study.PhaseProfileConvergenceError):study.compare_phase_profiles(c,c,s,len(x))


def test_optimizer_nonfinite_phase_rejected(monkeypatch):
    def broken(fun,x0,args,jac,method,options):return SimpleNamespace(x=np.full_like(x0,np.nan))
    monkeypatch.setattr(study,'minimize',broken)
    c,s,x,_=problem(3)
    with pytest.raises(study.PhaseProfileConvergenceError):study.fit_station_phases(c,s,len(x))


def test_inputs_untouched_and_no_truth_phase_argument():
    c,s,x,_=problem(3);before_c=c.copy();before_s=s.copy()
    q=study.fit_station_phases(c,s,len(x))
    np.testing.assert_array_equal(c,before_c);np.testing.assert_array_equal(s,before_s)
    assert not q['true_phases_supplied_for_initialization'] and not q['unknown_amplitude_sefd_or_lo_estimated']
    with pytest.raises(TypeError):study.fit_station_phases(c,s,len(x),true_phases=np.zeros(3))


def test_real_iteration_limit_is_not_reported_converged():
    c,s,x,_=problem(5)
    q=study.fit_station_phases(c,s,len(x),max_iterations=1)
    assert q['state']=='not_converged' and not any(r['optimizer_success'] for r in q['optimizer_runs'])
    with pytest.raises(study.PhaseProfileConvergenceError):
        study.compare_phase_profiles(c,c+np.eye(5),s,len(x),max_iterations=1)


def test_nonzero_phase_coefficient_underflow_rejected():
    tiny=np.array([[1.,1e-200],[1e-200,1.]])
    with pytest.raises(ValueError,match='coefficient underflows'):
        study.fit_station_phases(tiny,tiny,37)


def test_diagonal_sample_has_no_phase_information_even_for_correlated_model():
    c,_,_,_=problem(3)
    q=study.fit_station_phases(c,np.eye(3),37)
    assert q['state']=='phase_independent' and not q['physical_phase_identification_verified']


@pytest.mark.parametrize('n',[3,8])
def test_station_reordering_changes_reference_but_not_profile_score(n):
    c,s,x,_=problem(n);c1=c+np.diag(np.linspace(.2,1.,n))
    permutation=np.roll(np.arange(n),1);change=lambda a:a[np.ix_(permutation,permutation)]
    baseline=study.compare_phase_profiles(c,c1,s,len(x))
    reordered=study.compare_phase_profiles(change(c),change(c1),change(s),len(x))
    assert reordered['log_likelihood1_minus0']==pytest.approx(baseline['log_likelihood1_minus0'],abs=4e-8)
    assert reordered['fit0']['candidate_phase_rad'][0]==0


def test_reference_station_perturbation_is_reanchored(monkeypatch):
    c,s,x,_=problem(3);actual_minimize=study.minimize;starts=[]
    def record(fun, initial, **kwargs):
        starts.append(np.asarray(initial).copy())
        return actual_minimize(fun,initial,**kwargs)
    monkeypatch.setattr(study,'minimize',record)
    study.fit_station_phases(c,s,len(x))
    assert len(starts)==6
    # First perturbation rotates the reference station; all relative phases
    # must therefore shift by -pi, rather than duplicating the initial start.
    np.testing.assert_allclose(starts[3]-starts[0],-np.pi,atol=1e-14)


@pytest.mark.parametrize('n',[2,3,8])
def test_different_candidate_score_and_data_phase_invariance(n):
    c,s,x,_=problem(n);c1=c+np.diag(np.linspace(.2,1.,n));m=len(x)
    q=study.compare_phase_profiles(c,c1,s,m)
    c0f=matrix(q['fit0']);c1f=matrix(q['fit1'])
    def logpdf(cov):
        real=.5*np.block([[cov.real,-cov.imag],[cov.imag,cov.real]])
        return float(np.sum(multivariate_normal.logpdf(np.concatenate([x.real,x.imag],axis=1),cov=real)))
    assert q['log_likelihood1_minus0']==pytest.approx(logpdf(c1f)-logpdf(c0f),abs=4e-10)
    phase=np.exp(1j*np.linspace(-1.2,2.,n));changed=phase[:,None]*s*phase.conj()[None,:]
    transported=study.compare_phase_profiles(c,c1,changed,m)
    assert transported['log_likelihood1_minus0']==pytest.approx(q['log_likelihood1_minus0'],abs=4e-8)
    reverse=study.compare_phase_profiles(c1,c,s,m)
    assert reverse['log_likelihood1_minus0']==pytest.approx(-q['log_likelihood1_minus0'],abs=2e-11)
