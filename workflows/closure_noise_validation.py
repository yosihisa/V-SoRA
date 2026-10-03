"""Joint closure noise: visibility approximation versus Gaussian voltages."""
import argparse
import json
from pathlib import Path
import numpy as np
from vsora_imaging.closure import wrap_phase
from vsora_imaging.closure_noise import joint_closure_noise
from vsora_simulator.visibility_moments import visibility_noise_moments


def factor(c):
    values,vectors=np.linalg.eigh(c)
    return vectors*np.sqrt(np.maximum(0.,values))[None,:]


def errors(values,q):
    phase=wrap_phase(np.angle(values) @ q['phase_matrix'].T-q['joint_values'][:q['phase_count']])
    amplitude=np.log(abs(values)) @ q['logamp_matrix'].T-q['joint_values'][q['phase_count']:]
    return np.c_[phase,amplitude][:,q['joint_valid']]


def experiment(label,s,kind,trials,seed,samples=512):
    moments=visibility_noise_moments(s,samples);mean=moments['mean'];p=moments['pairs'];b=len(p)
    q=joint_closure_noise(mean,moments['real_covariance'],p)
    if not q['joint_valid'].all():raise ValueError('fixed experiment means must meet SNR mask')
    rng=np.random.default_rng(seed);f=factor(moments['real_covariance'] if kind=='gaussian_visibility' else s)
    rows=[]
    for start in range(0,trials,64):
        count=min(64,trials-start)
        if kind=='gaussian_visibility':
            noise=rng.normal(size=(count,2*b)) @ f.T
            v=mean+noise[:,:b]+1j*noise[:,b:]
        elif kind=='gaussian_voltage':
            z=(rng.normal(size=(count,samples,len(s)))+1j*rng.normal(size=(count,samples,len(s))))/np.sqrt(2)
            x=z @ f.T
            v=np.mean(x[:,:,p[:,0]]*x[:,:,p[:,1]].conj(),axis=1)
        else:raise ValueError('unknown noise experiment kind')
        if not np.isfinite(v).all() or np.any(abs(v)==0):raise ValueError('nonfinite or exactly zero simulated visibility')
        rows.append(errors(v,q))
    residual=np.concatenate(rows);empirical=np.cov(residual,rowvar=False);calculated=q['joint_covariance']
    diagonal=np.diag(calculated);normalization=np.sqrt(diagonal[:,None]*diagonal[None,:])
    delta=(empirical-calculated)/normalization
    # Baseline-independent circular approximation uses each Re/Im average.
    average=.5*(np.diag(moments['real_covariance'])[:b]+np.diag(moments['real_covariance'])[b:])
    naive=joint_closure_noise(mean,np.diag(np.r_[average,average]),p)
    return {'label':label,'noise_generation':kind,'trials':trials,'seed':seed,'independent_samples_per_trial':samples,
        'station_covariance_real':s.real.tolist(),'station_covariance_imag':s.imag.tolist(),
        'minimum_mean_baseline_snr':float(q['baseline_snr'].min()),'joint_parameter_order':q['joint_parameter_order'],
        'phase_count':q['phase_count'],'logamp_count':q['logamp_count'],'selection_on_observed_visibility':False,
        'calculated_joint_covariance':calculated.tolist(),'empirical_joint_covariance':empirical.tolist(),
        'empirical_to_first_order_variance_ratio':(np.diag(empirical)/diagonal).tolist(),
        'first_order_to_independent_circular_variance_ratio':(diagonal/np.diag(naive['joint_covariance'])).tolist(),
        'maximum_normalized_covariance_difference':float(abs(delta).max()),
        'mean_closure_error':residual.mean(axis=0).tolist(),
        'maximum_calculated_phase_logamp_covariance':float(abs(calculated[:q['phase_count'],q['phase_count']:]).max()),
        'exact_visibility_moments':True,'closure_covariance_first_order':True,
        'physical_iq_vdif_processed':False,'actual_hardware_data':False}


def run(output,trials=16384):
    if isinstance(trials,bool) or not isinstance(trials,int) or not 256<=trials<=65536:
        raise ValueError('closure noise validation needs integer trials in 256..65536')
    out=Path(output);out.mkdir(parents=True,exist_ok=False);models=[]
    for rho in (.2,.5,.9):
        s=np.ones((4,4),complex);np.fill_diagonal(s,1/rho)
        models.append(('point-'+str(rho),s))
    mode=np.exp(1j*np.array([0.,.4,1.1,2.2]));s=np.ones((4,4))+.7*mode[:,None]*mode.conj()[None,:]+1.5*np.eye(4)
    models.append(('two-components',s))
    results=[experiment(label,s,kind,trials,44+i*2+j) for i,(label,s) in enumerate(models)
        for j,kind in enumerate(('gaussian_visibility','gaussian_voltage'))]
    summary={'type':'joint_closure_noise_validation','trials_per_case':trials,'cases':results,
        'actual_hardware_data':False,'physical_iq_vdif_processed':False,'production_rml_noise_model_changed':False,
        'scope':'Known station covariance, 4 stations, iid proper Gaussian voltages, 512 samples per trial. Gaussian visibility approximation compared separately. Joint high-SNR first-order closure covariance, no observed-value selection. No ADC/FIR/VDIF/OCXO/Cas A fidelity or real confidence calibration.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');plot(summary,out);return summary


def plot(summary,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cases=summary['cases'];fig,axes=plt.subplots(1,2,figsize=(10,4));x=np.arange(len(cases))
    for k,r in enumerate(cases):
        axes[0].scatter(np.full(6,k),r['first_order_to_independent_circular_variance_ratio'],marker='o',s=14)
        axes[1].scatter(np.full(6,k),r['empirical_to_first_order_variance_ratio'],marker='x',s=18)
    axes[0].set(title='Known full / independent circular variance',ylabel='First-order variance ratio')
    axes[1].set(title='Finite simulation / first-order variance',ylabel='Empirical variance ratio');axes[1].axhline(1,color='gray',linestyle=':')
    for axis in axes:
        axis.set_xticks(x,[r['label']+'\n'+('V Gaussian' if r['noise_generation']=='gaussian_visibility' else 'voltage samples') for r in cases],rotation=45,ha='right',fontsize=7)
    fig.suptitle('Assumed known models; closure approximation, not hardware or image fidelity',fontsize=10)
    fig.tight_layout();fig.savefig(out/'closure-noise.png',dpi=140);plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--trials',type=int,default=16384)
    q=run(**vars(parser.parse_args()))
    print(json.dumps([{k:r[k] for k in ('label','noise_generation','minimum_mean_baseline_snr','maximum_normalized_covariance_difference')} for r in q['cases']],indent=2))
