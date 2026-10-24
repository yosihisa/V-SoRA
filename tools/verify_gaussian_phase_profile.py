"""Fixed numerical phase-profile references; optional installed-prefix check."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np
from scipy.stats import multivariate_normal
from vsora_correlator import gaussian_phase_profile as api
from vsora_correlator.gaussian_likelihood import sample_second_moment


def fixture(n, seed):
    rng=np.random.default_rng(seed);m=37
    a=rng.normal(size=(n,n))+1j*rng.normal(size=(n,n))
    c=a @ a.conj().T+np.eye(n)
    phi=rng.uniform(-np.pi,np.pi,n);gain=np.exp(1j*phi)
    generating=gain[:,None]*c*gain.conj()[None,:]
    x=(rng.normal(size=(m,n))+1j*rng.normal(size=(m,n)))@np.linalg.cholesky(generating).T/np.sqrt(2)
    return c,sample_second_moment(x),x


def matrix(fit):
    a=np.asarray(fit['fitted_covariance_real_imag']);return a[...,0]+1j*a[...,1]


def real_logpdf(c, x):
    real=.5*np.block([[c.real,-c.imag],[c.imag,c.real]])
    return float(np.sum(multivariate_normal.logpdf(np.concatenate([x.real,x.imag],axis=1),cov=real)))


def experiment():
    rows=[]
    for n in (2,3,8):
        for seed in (103,104,105):
            c,s,x=fixture(n,seed);m=len(x);c1=c+np.diag(np.linspace(.2,1.,n))
            result=api.compare_phase_profiles(c,c1,s,m)
            expected=real_logpdf(matrix(result['fit1']),x)-real_logpdf(matrix(result['fit0']),x)
            assert np.isclose(result['log_likelihood1_minus0'],expected,rtol=1e-9,atol=4e-10)
            phase=np.exp(1j*np.linspace(-1.2,2.,n));changed=phase[:,None]*s*phase.conj()[None,:]
            transported=api.compare_phase_profiles(c,c1,changed,m)
            difference=abs(transported['log_likelihood1_minus0']-result['log_likelihood1_minus0'])
            assert difference<4e-8
            _,_,a,ascale,sratio,_=api._problem(c,s,m)
            grid_check=None
            if n==3:
                angle=np.linspace(-np.pi,np.pi,181,endpoint=False)
                p1,p2=np.meshgrid(np.exp(1j*angle),np.exp(1j*angle))
                values=2*(a[0,1]*p1+a[0,2]*p2+a[1,2]*p2*p1.conj()).real*ascale*sratio
                minimum=float(np.min(values))
                assert result['fit0']['phase_dependent_trace_per_mode']<=minimum+1e-8
                grid_check={'points_per_axis':181,'grid_points':181**2,'discrete_grid_minimum_per_mode':minimum,
                    'candidate_at_or_below_discrete_grid_minimum':True,'global_optimum_certified':False}
            rows.append({'stations':n,'seed':seed,'modes':m,'state':'complete',
                'fitted_comparison':result,'independent_real_gaussian_score':expected,
                'real_gaussian_abs_difference':abs(result['log_likelihood1_minus0']-expected),
                'known_data_phase_transport_abs_difference':difference,'dense_grid_check':grid_check})
    flat=[]
    for n in (1,3,8):
        fit=api.fit_station_phases(np.diag(np.arange(1,n+1)),np.eye(n),37)
        assert fit['state']=='phase_independent' and not fit['physical_phase_identification_verified']
        flat.append(fit)
    c,s,x=fixture(5,103);limited=api.fit_station_phases(c,s,len(x),max_iterations=1)
    assert limited['state']=='not_converged'
    try:api.compare_phase_profiles(c,c+np.eye(5),s,len(x),max_iterations=1)
    except api.PhaseProfileConvergenceError:refused=True
    else:raise AssertionError('unfinished phase fits produced a reference score')
    return {'state':'complete','type':'known_covariance_phase_profile_reference',
        'matrix_cases':rows,'matrix_case_count':9,'phase_independent_cases':flat,
        'phase_independent_case_count':3,'actual_iteration_limited_case':limited,
        'unfinished_profile_comparison_refused':refused,
        'true_instrument_phases_supplied_to_fit':False,'amplitudes_and_sefd_held_fixed':True,
        'general_sky_image_reconstructed':False,'unknown_amplitude_sefd_lo_estimated':False,
        'image_likelihood_defined':False,'real_hardware_validation_performed':False,
        'production_rml_noise_model_changed':False}


def plot(path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    c,s,x=fixture(3,103);fit=api.fit_station_phases(c,s,len(x))
    _,_,a,scale,ratio,_=api._problem(c,s,len(x))
    angle=np.linspace(-np.pi,np.pi,181,endpoint=False)
    p1,p2=np.meshgrid(np.exp(1j*angle),np.exp(1j*angle))
    surface=2*(a[0,1]*p1+a[0,2]*p2+a[1,2]*p2*p1.conj()).real*scale*ratio
    fig,ax=plt.subplots(figsize=(8,5))
    image=ax.contourf(angle,angle,surface,levels=25)
    ax.scatter(fit['candidate_phase_rad'][1],fit['candidate_phase_rad'][2],marker='*',s=160,c='red',label='Fitted stationary candidate')
    ax.set(xlabel='Station1 phase relative to station0 (rad)',ylabel='Station2 phase relative to station0 (rad)',
           title='Phase objective with supplied amplitudes/noise; not confidence')
    ax.legend();fig.colorbar(image,ax=ax,label='Phase-dependent trace per mode')
    fig.tight_layout();fig.savefig(path,dpi=140);plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--reference');p.add_argument('--installed',action='store_true');args=p.parse_args()
    target=Path(args.output)
    if target.exists():raise FileExistsError('existing output must not be overwritten')
    if args.installed:
        assert 'PYTHONPATH' not in os.environ
        assert not Path.cwd().resolve().is_relative_to(Path(__file__).resolve().parents[1])
        assert not (Path.cwd()/'tools/run.py').exists()
    q=experiment()
    if args.reference:assert q==json.loads(Path(args.reference).read_text())
    modules=sorted(n for n,m in sys.modules.items() if n.startswith('vsora_') and getattr(m,'__file__',None))
    if args.installed:assert all(Path(sys.modules[n].__file__).is_relative_to(Path(sys.prefix)) for n in modules)
    target.mkdir(parents=True,exist_ok=False)
    (target/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n')
    plot(target/'phase-profile-objective.png')
    origin={'state':'complete','installed_prefix_checked':args.installed,
        'project_modules':modules,'project_module_count':len(modules),'all_reference_json_identical':bool(args.reference),
        'api_source_sha256':hashlib.sha256(Path(api.__file__).read_bytes()).hexdigest()}
    (target/'installation.json').write_text(json.dumps(origin,indent=2)+'\n')
    print(json.dumps({'state':'complete','matrix_cases':9,'phase_independent_cases':3,'limited_case_refused':True}))


if __name__=='__main__':main()
