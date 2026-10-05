"""Known independent frequency-group comparison; no observed band coaddition."""
import json
from pathlib import Path
import numpy as np
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum
from vsora_simulator.bispectrum_moments import gaussian_distinct_bispectrum_moments
from vsora_simulator.bispectrum_average import gaussian_averaged_bispectrum_moments
from vsora_simulator.bispectrum_pooling import pooled_covariance_bispectrum_mean
from workflows.bispectrum_moments_validation import model

MODELS=('zero','weak','low','two_components','rank_one')
GROUPS=(1,4,16)
SAMPLES=32


def summarize(values,mean,covariance=None):
    residual=values-mean
    parts=np.c_[residual.real,residual.imag]
    observed_mean=parts.mean(axis=0);mean_se=parts.std(axis=0,ddof=1)/np.sqrt(len(parts))
    tolerance=1e-12*max(1.,float(np.max(abs(mean))))
    passed=bool(np.all(abs(observed_mean)<=6*mean_se+tolerance))
    q={'known_mean_real_imag':np.c_[mean.real,mean.imag].tolist(),
       'ensemble_mean_real_imag':np.c_[values.mean(axis=0).real,values.mean(axis=0).imag].tolist(),
       'mean_mc_standard_error_all_real_then_imag':mean_se.tolist(),
       'mean_within_6se':passed,'covariance_calculated':covariance is not None}
    if covariance is not None:
        products=parts[:,:,None]*parts[:,None,:]
        observed=products.mean(axis=0);se=products.std(axis=0,ddof=1)/np.sqrt(len(parts))
        cov_ok=bool(np.all(abs(observed-covariance)<=6*se+1e-12*max(1.,float(np.max(abs(covariance))))))
        q.update(known_real_covariance=covariance.tolist(),observed_real_covariance=observed.tolist(),
                 covariance_mc_standard_error=se.tolist(),covariance_within_6se=cov_ok)
        passed=passed and cov_ok
    q['all_calculated_moments_within_6se']=passed
    return q


def validate_trials(trials,seed):
    if isinstance(trials,bool) or not isinstance(trials,int) or not 1024<=trials<=32768:
        raise ValueError('integer trials1024..32768 required')
    if isinstance(seed,bool) or not isinstance(seed,int) or not 0<=seed<=2**32-1:
        raise ValueError('integer seed0..2^32-1 required')


def experiment(label,trials=8192,seed=74):
    validate_trials(trials,seed)
    s,_=model(label);rng=np.random.default_rng(seed)
    root=None if label=='rank_one' else np.linalg.cholesky(s)
    gathered={g:{method:[] for method in ('average','pooled')} for g in GROUPS}
    for start in range(0,trials,64):
        count=min(64,trials-start);shape=(count,max(GROUPS),SAMPLES,1 if root is None else 4)
        z=(rng.normal(size=shape)+1j*rng.normal(size=shape))/np.sqrt(2)
        x=np.repeat(z,4,axis=-1) if root is None else z @ root.T
        each=distinct_sample_bispectrum(x)['distinct_sample_bispectrum']
        for g in GROUPS:
            gathered[g]['average'].append(each[:,:g].mean(axis=1))
            gathered[g]['pooled'].append(distinct_sample_bispectrum(x[:,:g].reshape(count,g*SAMPLES,4))['distinct_sample_bispectrum'])
    cases=[]
    for g in GROUPS:
        average=gaussian_averaged_bispectrum_moments(s,SAMPLES,g)
        pooled=gaussian_distinct_bispectrum_moments(s,SAMPLES*g)
        methods={name:summarize(np.concatenate(gathered[g][name]),theory['mean'],theory['real_covariance'])
                 for name,theory in (('average',average),('pooled',pooled))}
        ratio=average['complex_covariance'].diagonal().real/pooled['complex_covariance'].diagonal().real
        cases.append({'model':label,'independent_groups':g,'samples_per_group':SAMPLES,
            'pooled_samples':SAMPLES*g,'seed':seed,'triangles':pooled['triangles'].tolist(),
            'average_to_pooled_complex_variance_ratio':ratio.tolist(),'methods':methods,
            'all_calculated_moments_within_6se':all(v['all_calculated_moments_within_6se'] for v in methods.values())})
    return cases


def phase_experiment(trials=8192,seed=79):
    validate_trials(trials,seed)
    groups=4;s=np.eye(4)+.1*np.ones((4,4));root=np.linalg.cholesky(s)
    gain=np.exp(2j*np.pi*np.arange(groups)[:,None]*np.arange(4)[None,:]/groups)
    sg=gain[:,:,None]*s*gain[:,None,:].conj();known=pooled_covariance_bispectrum_mean(sg,SAMPLES)
    rng=np.random.default_rng(seed);average=[];pooled=[];maximum_gain_invariance_difference=0.
    for start in range(0,trials,64):
        count=min(64,trials-start);shape=(count,groups,SAMPLES,4)
        z=(rng.normal(size=shape)+1j*rng.normal(size=shape))/np.sqrt(2);x=z @ root.T;y=x*gain[None,:,None,:]
        each=distinct_sample_bispectrum(x)['distinct_sample_bispectrum'];changed=distinct_sample_bispectrum(y)['distinct_sample_bispectrum']
        maximum_gain_invariance_difference=max(maximum_gain_invariance_difference,float(np.max(abs(each-changed))))
        average.append(changed.mean(axis=1));pooled.append(distinct_sample_bispectrum(y.reshape(count,groups*SAMPLES,4))['distinct_sample_bispectrum'])
    methods={'average':summarize(np.concatenate(average),known['equal_group_u3_mean']),
             'pooled':summarize(np.concatenate(pooled),known['pooled_u3_mean'])}
    return {'independent_groups':groups,'samples_per_group':SAMPLES,'pooled_samples':groups*SAMPLES,'seed':seed,
        'triangles':known['triangles'].tolist(),'station_phase_gains_real_imag':np.stack((gain.real,gain.imag),axis=-1).tolist(),
        'maximum_per_group_u3_gain_invariance_difference':maximum_gain_invariance_difference,
        'fixed_per_group_phase_invariance_checked':maximum_gain_invariance_difference<=1e-12,
        'methods':methods,'heterogeneous_group_covariance_calculated':False,
        'all_calculated_moments_within_6se':all(v['all_calculated_moments_within_6se'] for v in methods.values())}


def run(output,trials=8192):
    validate_trials(trials,74);out=Path(output)
    if out.exists():raise FileExistsError('new pooling validation output required')
    out.mkdir(parents=True)
    cases=[c for i,label in enumerate(MODELS) for c in experiment(label,trials,74+i)]
    phase=phase_experiment(trials,79)
    passed=all(c['all_calculated_moments_within_6se'] for c in cases) and phase['all_calculated_moments_within_6se'] and phase['fixed_per_group_phase_invariance_checked']
    q={'type':'independent_group_bispectrum_pooling_validation','state':'complete' if passed else 'failed_validation',
        'trials_per_model':trials,'cases':cases,'frequency_dependent_phase_example':phase,
        'generating_covariances_supplied':True,'independent_groups_assumed':True,'same_voltage_trials_reused':True,
        'group_prefix_comparisons_statistically_paired':True,'actual_frequency_independence_verified':False,
        'observed_frequency_coaddition_performed':False,'frequency_phase_alignment_performed':False,
        'physical_adc_vdif_processed':False,'real_hardware_validation_performed':False,
        'gaussian_u3_distribution_verified':False,'production_rml_noise_model_changed':False,
        'scope':'Known independent Gaussian groups; constant S covariance comparison and a group-dependent station-phase mean counterexample. No observed bandpass/delay estimation, FFT independence, detection probability or image confidence.'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');plot(q,out/'bispectrum-pooling.png')
    if not passed:raise RuntimeError('pooling moments outside fixed6SE criterion or gain invariance failed')
    return q


def plot(q,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    labels={'zero':'No source','weak':'Weak source','low':'Stronger source','two_components':'Two components','rank_one':'Perfect shared signal'}
    for label in MODELS:
        cases=[c for c in q['cases'] if c['model']==label]
        axes[0].plot(GROUPS,[c['average_to_pooled_complex_variance_ratio'][0] for c in cases],'o-',label=labels[label])
    axes[0].set(xscale='log',yscale='log',xlabel='Independent equal-statistics groups G',ylabel='Variance of averaged U3 / pooled U3',title='Known same S; 32 samples per group')
    axes[0].set_xticks(GROUPS,[str(g) for g in GROUPS]);axes[0].legend(fontsize=8);axes[0].grid(alpha=.2)
    phase=q['frequency_dependent_phase_example'];names=['Per-group U3 mean','Pooled U3 mean']
    known=[phase['methods'][name]['known_mean_real_imag'][0][0] for name in ('average','pooled')]
    axes[1].bar(names,known);axes[1].set(ylabel='Known real mean, first triangle',title='Known frequency-dependent station phases')
    axes[1].ticklabel_format(axis='y',style='sci',scilimits=(0,0));axes[1].grid(axis='y',alpha=.2)
    fig.suptitle('Conditional independent-group calculation; no actual FFT, band alignment, detection or image confidence',fontsize=10)
    fig.tight_layout();fig.savefig(path,dpi=140);plt.close(fig)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--trials',type=int,default=8192)
    q=run(**vars(p.parse_args()));print(json.dumps({'state':q['state'],'cases':len(q['cases'])}))
