"""Conditional U3 averaging and Gaussian-reference coverage, with known S."""
import json
from pathlib import Path
import numpy as np
from scipy.stats import chi2
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum
from vsora_simulator.bispectrum_average import gaussian_averaged_bispectrum_moments
from workflows.bispectrum_moments_validation import model

MODELS=('zero','weak','low','two_components','rank_one')
WINDOWS=(1,4,16,64)


def covariance_support(covariance):
    if np.ma.isMaskedArray(covariance):raise ValueError('unmasked covariance required')
    c=np.asarray(covariance)
    if c.ndim!=2 or c.shape[0]!=c.shape[1] or not c.shape[0] or np.iscomplexobj(c) or not np.isfinite(c).all():
        raise ValueError('finite real square covariance required')
    scale=max(float(np.max(abs(c))),np.finfo(float).tiny)
    if not np.allclose(c,c.T,rtol=0,atol=1e-12*scale):raise ValueError('symmetric covariance required')
    values,vectors=np.linalg.eigh(c)
    if values.min() < -1e-12*scale:raise ValueError('positive semidefinite covariance required')
    keep=values>max(float(values.max()),np.finfo(float).tiny)*1e-12
    if not np.any(keep):raise ValueError('nonzero covariance support required')
    return values[keep],vectors[:,keep]


def summarize(parts,covariance,control_seed):
    parts=np.asarray(parts)
    if parts.ndim!=2 or len(parts)<2 or np.iscomplexobj(parts) or not np.isfinite(parts).all():raise ValueError('finite real residual trials required')
    trials=len(parts);values,vectors=covariance_support(covariance);rank=len(values)
    if parts.shape[1]!=len(covariance):raise ValueError('residual and covariance dimensions differ')
    projected=parts@vectors;whitened=projected/np.sqrt(values)
    outside=parts-projected@vectors.T
    scale=max(float(np.max(abs(parts))),float(np.sqrt(values.max())),np.finfo(float).tiny)
    support_ok=bool(np.max(abs(outside))<=1e-10*scale)
    distance=np.sum(whitened**2,axis=1)
    mean=parts.mean(axis=0);mean_se=parts.std(axis=0,ddof=1)/np.sqrt(trials)
    products=parts[:,:,None]*parts[:,None,:]
    observed=products.mean(axis=0);cov_se=products.std(axis=0,ddof=1)/np.sqrt(trials)
    rounding=1e-12*max(float(np.max(abs(covariance))),np.finfo(float).tiny)
    moments_ok=bool(np.all(abs(mean)<=6*mean_se+rounding) and np.all(abs(observed-covariance)<=6*cov_se+rounding))
    control=np.random.default_rng(control_seed).normal(size=(trials,rank))
    control_distance=np.sum(control**2,axis=1)
    references=[]
    for confidence in (.95,.99):
        threshold=float(chi2.ppf(confidence,rank))
        coverage=float(np.mean(distance<=threshold));control_coverage=float(np.mean(control_distance<=threshold))
        reference_se=float(np.sqrt(confidence*(1-confidence)/trials))
        references.append({'nominal_probability':confidence,'chi_squared_threshold':threshold,
            'u3_coverage_fraction':coverage,'u3_binomial_mc_standard_error':float(np.sqrt(coverage*(1-coverage)/trials)),
            'gaussian_control_coverage_fraction':control_coverage,'gaussian_reference_binomial_standard_error':reference_se,
            'gaussian_control_within_6_reference_se':abs(control_coverage-confidence)<=6*reference_se,
            'u3_within_6_reference_se':abs(coverage-confidence)<=6*reference_se})
    return {'trials':trials,'real_parameter_rank':rank,'support_relative_tolerance':1e-12,
        'all_residuals_within_covariance_support':support_ok,'mean_residual':mean.tolist(),'mean_standard_error':mean_se.tolist(),
        'model_covariance':covariance.tolist(),'observed_uncentered_residual_covariance':observed.tolist(),
        'covariance_mc_standard_error':cov_se.tolist(),'means_and_covariances_within_6se':moments_ok,
        'mean_mahalanobis_per_rank':float(distance.mean()/rank),'median_mahalanobis_per_rank':float(np.median(distance)/rank),
        'empirical_distance_quantiles':{str(p):float(np.quantile(distance,p)) for p in (.5,.95,.99)},'coverage_references':references,
        'gaussian_u3_distribution_verified':False,'observed_sample_selection_used':False}


def experiment(label,trials=8192,seed=68):
    if isinstance(trials,bool) or not isinstance(trials,int) or not 1024<=trials<=32768:
        raise ValueError('integer trials1024..32768 required')
    if isinstance(seed,bool) or not isinstance(seed,int) or not 0<=seed<=2**32-1:
        raise ValueError('integer seed0..2^32-1 required')
    s,m=model(label);theories={q:gaussian_averaged_bispectrum_moments(s,m,q) for q in WINDOWS}
    rng=np.random.default_rng(seed);root=None if label=='rank_one' else np.linalg.cholesky(s)
    collected={q:[] for q in WINDOWS}
    for start in range(0,trials,64):
        n=min(64,trials-start)
        shape=(n,max(WINDOWS),m,1 if root is None else 4)
        z=(rng.normal(size=shape)+1j*rng.normal(size=shape))/np.sqrt(2)
        x=np.repeat(z,4,axis=-1) if root is None else z@root.T
        u=distinct_sample_bispectrum(x)['distinct_sample_bispectrum']
        prefix=np.cumsum(u,axis=1)
        for q in WINDOWS:collected[q].append(prefix[:,q-1]/q)
    cases=[]
    for q in WINDOWS:
        theoretical=theories[q];u=np.concatenate(collected[q]);residual=u-theoretical['mean'];parts=np.c_[residual.real,residual.imag]
        result=summarize(parts,theoretical['real_covariance'],seed+1000+q)
        cases.append({'model':label,'samples_per_window':m,'independent_windows':q,'seed':seed,
            'nominal_total_voltage_samples':m*q,'voltage_samples_pooled':False,
            'known_mean_real_imag':np.c_[theoretical['mean'].real,theoretical['mean'].imag].tolist(),**result})
    return cases


def run(output,trials=8192):
    out=Path(output)
    if out.exists():raise FileExistsError('new averaging validation output required')
    out.mkdir(parents=True)
    cases=[c for index,label in enumerate(MODELS) for c in experiment(label,trials,68+index)]
    passed=all(c['all_residuals_within_covariance_support'] and c['means_and_covariances_within_6se']
        and all(r['gaussian_control_within_6_reference_se'] for r in c['coverage_references']) for c in cases)
    q={'type':'averaged_bispectrum_distribution_validation','state':'complete' if passed else 'failed_validation','trials_per_model':trials,
        'cases':cases,'same_voltage_trials_reused_for_q_prefix_comparison':True,'q_comparisons_statistically_paired':True,
        'generating_covariance_supplied':True,'independent_windows_assumed':True,'equal_window_mean_and_covariance_assumed':True,
        'gaussian_u3_coverage_is_not_a_pass_requirement':True,'gaussian_u3_distribution_verified':False,
        'physical_adc_vdif_processed':False,'actual_temporal_independence_verified':False,'real_hardware_validation_performed':False,
        'production_rml_noise_model_changed':False,
        'scope':'Known iid proper Gaussian station voltages in independent equal-statistics windows. Exact covariance of averaged U3 is C/Q. Chi-square regions are Gaussian reference diagnostics; neither a certified U3 likelihood nor hardware/image confidence.'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n')
    plot(q,out/'averaged-bispectrum.png')
    if not passed:raise RuntimeError('averaging moments, support or Gaussian control outside fixed validation criterion')
    return q


def plot(result,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(12,8))
    labels={'zero':'No source','weak':'Weak shared source','low':'Stronger shared source',
            'two_components':'Two components','rank_one':'Perfect shared signal'}
    for index,label in enumerate(MODELS):
        cases=[c for c in result['cases'] if c['model']==label]
        x=[c['independent_windows'] for c in cases];color=f'C{index}'
        for reference,axis in enumerate(axes[0]):
            values=[100*c['coverage_references'][reference]['u3_coverage_fraction'] for c in cases]
            errors=[200*c['coverage_references'][reference]['u3_binomial_mc_standard_error'] for c in cases]
            axis.errorbar(x,values,yerr=errors,color=color,marker='o',label=labels[label],capsize=3)
        axes[1,0].plot(x,[c['empirical_distance_quantiles']['0.99']/c['coverage_references'][1]['chi_squared_threshold'] for c in cases],color=color,marker='o')
        axes[1,1].plot(x,[c['mean_mahalanobis_per_rank'] for c in cases],color=color,marker='o')
    for axis,p in zip(axes[0],(95,99)):
        axis.axhline(p,color='black',linestyle='--',label='Gaussian reference')
        axis.set(title=f'Coverage of nominal {p}% region',ylabel='Coverage (%)')
    axes[1,0].set(title='Tail differs from Gaussian reference',ylabel='Empirical 99% radius squared / Gaussian threshold')
    axes[1,1].set(title='Correct covariance does not fix the distribution',ylabel='Mean squared distance / covariance rank')
    for axis in axes[1]:axis.axhline(1,color='black',linestyle='--')
    for axis in axes.flat:
        axis.set_xscale('log',base=2);axis.set_xticks(WINDOWS,[str(q) for q in WINDOWS])
        axis.set_xlabel('Independent equal-statistics windows Q');axis.grid(alpha=.2)
    axes[0,0].legend(fontsize=8,loc='lower right')
    fig.suptitle('Known Gaussian station voltages; U3 mean/covariance are exact, distribution need not be Gaussian\nCoverage bars: 2 Monte Carlo SE; no ADC, FIR, clocks, hardware or image confidence',fontsize=10)
    fig.tight_layout(rect=(0,0,1,.94));fig.savefig(path,dpi=140);plt.close(fig)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--trials',type=int,default=8192)
    result=run(**vars(p.parse_args()));print(json.dumps({'state':result['state'],'cases':len(result['cases'])}))
