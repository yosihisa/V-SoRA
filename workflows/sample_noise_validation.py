"""Finite station sample-covariance estimator, truth used only for validation."""
import argparse
import json
from pathlib import Path
import numpy as np
from vsora_simulator.visibility_moments import visibility_noise_moments
from vsora_simulator.visibility_noise_estimate import estimate_visibility_noise


def batch_covariance(sample,m,pairs):
    i,j=pairs.T;b=len(pairs)
    gamma=sample[:,i[:,None],i[None,:]]*sample[:,j[None,:],j[:,None]]/m
    pseudo=sample[:,i[:,None],j[None,:]]*sample[:,i[None,:],j[:,None]]/m
    top=np.concatenate([np.real(gamma+pseudo),np.imag(pseudo-gamma)],axis=2)
    bottom=np.concatenate([np.imag(pseudo+gamma),np.real(gamma-pseudo)],axis=2)
    plug=.5*np.concatenate([top,bottom],axis=1)
    mean=sample[:,i,j];real=np.concatenate([mean.real,mean.imag],axis=1)
    corrected=(plug-real[:,:,None]*real[:,None,:]/m**2)/(1-1/m**2)
    return plug,corrected


def experiment(station_covariance,m,trials,seed):
    s=np.asarray(station_covariance,complex);truth=visibility_noise_moments(s,m);pairs=truth['pairs']
    target=truth['real_covariance'];mu=np.r_[truth['mean'].real,truth['mean'].imag]
    plugin_bias=np.outer(mu,mu)/m**2;normal=np.sqrt(np.diag(target)[:,None]*np.diag(target)[None,:])
    sums=np.zeros((2,*target.shape));squares=sums.copy();psd_count=0;minimum_eigenvalue=1.;examples=[]
    rng=np.random.default_rng(seed);factor=np.linalg.cholesky(s)
    for start in range(0,trials,64):
        count=min(64,trials-start)
        z=(rng.normal(size=(count,m,len(s)))+1j*rng.normal(size=(count,m,len(s))))/np.sqrt(2)
        x=z @ factor.T;sample=np.einsum('tmi,tmj->tij',x,x.conj())/m
        plugin,corrected=batch_covariance(sample,m,pairs)
        check=estimate_visibility_noise(sample[0],m,pairs)
        np.testing.assert_allclose(check['real_covariance'],corrected[0],rtol=1e-10,atol=1e-12*abs(corrected[0]).max())
        for k,a in enumerate((plugin,corrected)):sums[k]+=a.sum(axis=0);squares[k]+=(a*a).sum(axis=0)
        scale=np.max(abs(corrected),axis=(1,2));smallest=np.linalg.eigvalsh(corrected/scale[:,None,None])[:,0]
        psd_count+=int(np.count_nonzero(smallest>=-1e-12));minimum_eigenvalue=min(minimum_eigenvalue,float(smallest.min()))
        if not examples:
            examples=[{'station_sample_covariance_real':sample[0].real.tolist(),
                'station_sample_covariance_imag':sample[0].imag.tolist(),'estimated_covariance':corrected[0].tolist()}]
    means=sums/trials;se=np.sqrt(np.maximum(0.,(squares-sums*sums/trials)/(trials-1))/trials)
    expected=np.stack([target+plugin_bias,target]);errors=means-expected
    tolerance=6*se+1e-12*normal[None,:,:]
    return {'samples':m,'trials':trials,'seed':seed,'station_count':len(s),'generating_truth_used_in_estimator':False,
        'true_visibility_covariance':target.tolist(),'predicted_plugin_bias':plugin_bias.tolist(),
        'mean_plugin_covariance':means[0].tolist(),'mean_corrected_covariance':means[1].tolist(),
        'corrected_mean_standard_error':se[1].tolist(),
        'maximum_normalized_plugin_error_against_true_covariance':float(abs((means[0]-target)/normal).max()),
        'maximum_normalized_corrected_error_against_true_covariance':float(abs((means[1]-target)/normal).max()),
        'maximum_normalized_predicted_plugin_bias':float(abs(plugin_bias/normal).max()),
        'maximum_normalized_plugin_error_against_predicted_mean':float(abs(errors[0]/normal).max()),
        'all_corrected_means_within_six_standard_errors':bool(np.all(abs(errors[1])<=tolerance[1])),
        'all_plugin_means_within_six_standard_errors_of_predicted_bias':bool(np.all(abs(errors[0])<=tolerance[0])),
        'positive_semidefinite_estimates':psd_count,'minimum_normalized_estimated_eigenvalue':minimum_eigenvalue,
        'examples':examples,'scope':'Same independent zero-mean proper Gaussian samples for all station moments. Ensemble means, not per-observation true covariance or calibrated confidence.'}


def run(output,trials=32768):
    if isinstance(trials,bool) or not isinstance(trials,int) or not 256<=trials<=65536:
        raise ValueError('sample noise validation needs integer trials in 256..65536')
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    mode=np.exp(1j*np.array([0.,.4,1.1,2.2]));s=np.ones((4,4))+.7*mode[:,None]*mode.conj()[None,:]+1.5*np.eye(4)
    gains=np.array([.4,3,1.5,.75])*np.exp(1j*np.array([.3,-1,2,1.1]));s=gains[:,None]*s*gains.conj()[None,:]
    cases=[experiment(s,m,trials,46+i) for i,m in enumerate((4,8,64,512))]
    summary={'type':'sample_visibility_noise_validation','trials_per_case':trials,'cases':cases,
        'station_covariance_real_for_generation':s.real.tolist(),'station_covariance_imag_for_generation':s.imag.tolist(),
        'generating_truth_used_in_estimator':False,'actual_hardware_data':False,'physical_iq_vdif_processed':False,
        'production_rml_noise_model_changed':False,'covariance_confidence_calibrated_for_hardware':False,
        'scope':'Conditional ensemble-unbiased station-sample covariance formula, iid proper Gaussian zero-mean voltages. Same sample set, no empirical mean subtraction or masks. Actual ADC/FIR/VDIF, effective independent counts, OCXO and Cas A image fidelity unverified.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');plot(summary,out);return summary


def plot(summary,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cases=summary['cases'];x=np.arange(len(cases));fig,axes=plt.subplots(1,2,figsize=(9,3.7))
    for k,name in enumerate(('maximum_normalized_plugin_error_against_true_covariance','maximum_normalized_corrected_error_against_true_covariance')):
        axes[0].bar(x+(k-.5)*.32,[r[name] for r in cases],width=.32,label=('Plug-in mean error','Corrected mean error')[k])
    axes[0].plot(x,[r['maximum_normalized_predicted_plugin_bias'] for r in cases],'k:',label='Predicted plug-in bias')
    axes[0].set(title='Finite trial mean versus true covariance',ylabel='Maximum normalized error');axes[0].legend(fontsize=7)
    axes[1].bar(x,[r['positive_semidefinite_estimates']/r['trials'] for r in cases]);axes[1].set(title='PSD under conditional formula',ylabel='Fraction of estimates',ylim=(0,1.05))
    for axis in axes:axis.set_xticks(x,[str(r['samples']) for r in cases]);axis.set_xlabel('Independent samples per trial')
    fig.suptitle('Gaussian iid assumptions; not physical IQ or confidence calibration',fontsize=10)
    fig.tight_layout();fig.savefig(out/'sample-noise.png',dpi=140);plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--trials',type=int,default=32768)
    q=run(**vars(parser.parse_args()))
    print(json.dumps([{k:r[k] for k in ('samples','trials','maximum_normalized_plugin_error_against_true_covariance',
        'maximum_normalized_corrected_error_against_true_covariance','all_corrected_means_within_six_standard_errors','positive_semidefinite_estimates')} for r in q['cases']],indent=2))
