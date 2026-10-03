"""Finite rate-error/covariance experiments, keeping rejected trials visible."""
import argparse
from collections import Counter
from itertools import combinations
import json
from pathlib import Path
import numpy as np
from scipy.stats import chi2
from vsora_correlator.rate_linear import estimate_linear_rates
from vsora_simulator.visibility_moments import visibility_noise_moments
from workflows.rate_variation_validation import pilot

RATES = np.array([0., 17., -11., 26.])


def shared_model(rho, sigma=.05):
    if not np.isfinite(rho) or not 0 < rho <= 1:
        raise ValueError('shared point coherence must be in (0, 1]')
    s=np.ones((4,4));np.fill_diagonal(s,1/rho)
    samples=max(1,round(1/(2*rho*rho*sigma*sigma)))
    q=visibility_noise_moments(s,samples);c=q['real_covariance']
    values,vectors=np.linalg.eigh(c)
    factor=vectors*np.sqrt(np.maximum(0.,values))[None,:]
    return {'rho':rho,'samples':samples,'factor':factor,'moments':q,
        'weight':2*samples*rho*rho,'sigma_per_quadrature_average':float(np.sqrt(1/(2*samples*rho*rho)))}


def shared_pilot(seed, model):
    rng=np.random.default_rng(seed);t=(np.arange(128)+.5)*.004;pairs=model['moments']['pairs']
    phase=2*np.pi*t[:,None]*RATES;rotation=np.exp(1j*(phase[:,pairs[:,0]]-phase[:,pairs[:,1]]))[:,None,:]
    noise=rng.normal(size=(128,8,12)) @ model['factor'].T
    values=(model['moments']['mean']+noise[:,:,:6]+1j*noise[:,:,6:])*rotation
    return {'visibilities':values,'weights':np.full(values.shape,model['weight']),'times_s':t,'pairs':pairs}


def group(label, trials, make_data, slopes=None):
    slopes=np.zeros(4) if slopes is None else np.asarray(slopes)
    rows=[];states=Counter();standardized=[];whitened=[];mahalanobis=[]
    for seed in range(trials):
        data=make_data(seed)
        try:profile=estimate_linear_rates(data)
        except ValueError as exc:
            reason=str(exc)
            if not any(s in reason for s in ('four verified subpilot','inconsistent with a linear rate model',
                    'curvature too large','outside supplied baseline rate bound')):raise
            states[reason]+=1;rows.append({'seed':seed,'state':'unverified','reason':reason});continue
        epoch=profile['time_reference_s'];truth=np.r_[(RATES+slopes*epoch)[1:],slopes[1:]]
        measured=np.r_[np.array(profile['station_rates_hz'])[1:],np.array(profile['station_rate_slopes_hz_per_s'])[1:]]
        error=measured-truth;c=np.array(profile['parameter_covariance']);z=error/np.sqrt(np.diag(c))
        white=np.linalg.solve(np.linalg.cholesky(c),error);d2=float(white @ white)
        standardized.append(z);whitened.append(white);mahalanobis.append(d2);states['accepted']+=1
        rows.append({'seed':seed,'state':'accepted','error':error.tolist(),'diagonal_standardized_error':z.tolist(),
            'mahalanobis_squared_error':d2,'parameter_covariance':c.tolist(),
            'linear_model_reduced_chisq':profile['linear_model_reduced_chisq']})
    result={'label':label,'trials':trials,'states':dict(states),'accepted_count':states['accepted'],
        'accepted_fraction':states['accepted']/trials,'truth_initial_rates_hz':RATES.tolist(),
        'truth_slopes_hz_per_s':slopes.tolist(),'statistics_conditioned_on_accepted':True,
        'successful_seed_indices':[r['seed'] for r in rows if r['state']=='accepted'],
        'examples':rows[:4]}
    if standardized:
        z=np.asarray(standardized);white=np.asarray(whitened);d2=np.asarray(mahalanobis)
        result.update(parameter_order='rates ST02/ST03/ST04 Hz, then slopes Hz/s',
            standardized_error_mean=z.mean(axis=0).tolist(),
            standardized_error_covariance=np.cov(z,rowvar=False).tolist() if len(z)>1 else None,
            fraction_within_one_nominal_sigma=np.mean(abs(z)<=1,axis=0).tolist(),
            fraction_within_two_nominal_sigma=np.mean(abs(z)<=2,axis=0).tolist(),
            mean_mahalanobis_squared_error=float(d2.mean()),
            mean_mahalanobis_per_parameter=float(d2.mean()/6),
            nominal_95pct_ellipsoid_threshold=float(chi2.ppf(.95,6)),
            accepted_fraction_inside_nominal_95pct_ellipsoid=float(np.mean(d2<=chi2.ppf(.95,6))),
            whitened_error_covariance=np.cov(white,rowvar=False).tolist() if len(white)>1 else None,
            covariance_confidence_calibrated_for_hardware=False)
    return result,rows


def run(output,trials=1024):
    if isinstance(trials,bool) or not isinstance(trials,int) or not 8<=trials<=4096:
        raise ValueError('covariance validation needs integer trials in 8..4096')
    out=Path(output);out.mkdir(parents=True,exist_ok=False);groups=[]
    for sigma in (.1,.5,1.,2.):
        label='independent-'+str(sigma)
        result,rows=group(label,trials,lambda seed:pilot(seed,noise=sigma))
        result.update(noise_model='Independent circular complex Gaussian visibility errors; random unknown per-channel/baseline constants',
            sigma_per_quadrature=sigma,measurement_model_matches_estimator_noise=True)
        groups.append(result);(out/(label+'-trials.json')).write_text(json.dumps(rows,indent=2)+'\n')
    slopes=[0.,2.,-1.,3.]
    result,rows=group('independent-linear',trials,lambda seed:pilot(seed,noise=.5,slopes=slopes),slopes)
    result.update(noise_model='Independent circular complex Gaussian visibility with quadratic phase; locally constant subpart fits are approximate',
        sigma_per_quadrature=.5,measurement_model_matches_estimator_noise=True)
    groups.append(result);(out/'independent-linear-trials.json').write_text(json.dumps(rows,indent=2)+'\n')
    for rho in (.05,.5,.9):
        model=shared_model(rho);label='shared-'+str(rho)
        result,rows=group(label,trials,lambda seed:shared_pilot(seed,model))
        result.update(noise_model='Gaussian visibility approximation with exact second moments from iid proper Gaussian station voltages; common point signal',
            assumed_source_station_coherence=rho,independent_voltage_samples_per_cell=model['samples'],
            sigma_per_quadrature_average=model['sigma_per_quadrature_average'],
            measurement_model_matches_estimator_noise=False,
            baseline_real_covariance=model['moments']['real_covariance'].tolist())
        groups.append(result);(out/(label+'-trials.json')).write_text(json.dumps(rows,indent=2)+'\n')
    summary={'type':'rate_covariance_validation','trials_per_group':trials,'groups':groups,
        'actual_hardware_data':False,'physical_iq_vdif_processed':False,'generating_truth_in_rate_fit':False,
        'pilot':{'stations':4,'channels':8,'baselines':6,'integrations':128,'cadence_s':.004,'span_s':.512,
            'parts':4,'reference_station':0,'max_rate_hz':100.},
        'scope':'Finite conditional visibility models. Same solver and thresholds in all cases. Truth only used after fitting. Rejected trials retained; accepted error statistics are selection-conditioned. Full receiver/filter/quantization, low-SNR detection false alarms, Cas A and real OCXO remain uncalibrated.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');plot(summary,out);return summary


def plot(summary,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    groups=summary['groups'];x=np.arange(len(groups));fig,axes=plt.subplots(1,3,figsize=(12,3.7))
    axes[0].bar(x,[r['accepted_fraction'] for r in groups]);axes[0].set(ylabel='Fraction',title='Accepted models (rejections retained)',ylim=(0,1.05))
    axes[1].bar(x,[r.get('mean_mahalanobis_per_parameter',0.) for r in groups]);axes[1].axhline(1,color='gray',linestyle=':')
    axes[1].set(ylabel='Mean squared whitened error / 6',title='Conditional on acceptance; not hardware')
    axes[2].bar(x,[r.get('accepted_fraction_inside_nominal_95pct_ellipsoid',0.) for r in groups]);axes[2].axhline(.95,color='gray',linestyle=':')
    axes[2].set(ylabel='Accepted fraction',title='Inside nominal 95% error ellipsoid',ylim=(0,1.05))
    for axis in axes:axis.set_xticks(x,[r['label'] for r in groups],rotation=45,ha='right',fontsize=6)
    fig.tight_layout();fig.savefig(out/'rate-covariance.png',dpi=140);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--trials',type=int,default=1024)
    q=run(**vars(p.parse_args()))
    print(json.dumps([{k:r.get(k) for k in ('label','accepted_count','trials','mean_mahalanobis_per_parameter',
        'accepted_fraction_inside_nominal_95pct_ellipsoid')} for r in q['groups']],indent=2))
