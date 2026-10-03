"""Known raw Gaussian signal -> fixed linear operators -> visibility moments."""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.signal import fftconvolve
from vsora_simulator.filtered_noise import aligned_fft_kernel,filtered_visibility_moments


def experiment(station_covariance,kernels,stride,samples,trials,seed):
    s=np.asarray(station_covariance,complex);h=np.asarray(kernels,complex)
    q=filtered_visibility_moments(s,h,stride,samples);truth=q['real_covariance'];p=q['pairs'];i,j=p.T
    n=len(s);b=len(p);length=(samples-1)*stride+h.shape[1]
    sums=np.zeros(2*b);products=np.zeros((2*b,2*b));squared_products=products.copy()
    factor=np.linalg.cholesky(s);rng=np.random.default_rng(seed)
    for first in range(0,trials,64):
        count=min(64,trials-first)
        raw=(rng.normal(size=(count,length,n))+1j*rng.normal(size=(count,length,n)))/np.sqrt(2)
        raw=(raw @ factor.T).transpose(0,2,1)
        y=fftconvolve(raw,h[None,:,::-1],mode='valid',axes=-1)[:,:,::stride]
        assert y.shape==(count,n,samples)
        v=(y[:,i]*y[:,j].conj()).mean(axis=-1);residual=v-q['mean'];values=np.c_[residual.real,residual.imag]
        sums+=values.sum(axis=0);products+=values.T @ values;squared_products+=(values**2).T @ (values**2)
    measured=products/trials;se=np.sqrt(np.maximum(0.,(squared_products-products**2/trials)/(trials-1))/trials)
    normal=np.sqrt(np.maximum(0.,np.diag(truth)[:,None]*np.diag(truth)[None,:]))
    tolerance=6*se+1e-12*np.max(normal)
    mean=sums/trials;mean_se=np.sqrt(np.maximum(0.,np.diag(truth))/trials)
    iid=q['iid_counterfactual_real_covariance'];valid=np.diag(iid)>1e-15*np.max(abs(iid))
    ratios=np.diag(truth)[valid]/np.diag(iid)[valid]
    return {'trials':trials,'seed':seed,'station_count':n,'samples':samples,'stride_raw_samples':stride,
        'kernel_length':h.shape[1],'maximum_included_lag_blocks':q['maximum_included_lag_blocks'],
        'identical_station_kernels':q['identical_station_kernels'],
        'common_kernel_variance_factor':q['common_kernel_variance_factor'],
        'common_kernel_effective_count':q['common_kernel_effective_count'],
        'known_real_covariance':truth.tolist(),'measured_real_covariance':measured.tolist(),
        'measured_covariance_mean_standard_error':se.tolist(),'measured_centered_mean':mean.tolist(),
        'all_covariance_elements_within_six_standard_errors':bool(np.all(abs(measured-truth)<=tolerance)),
        'all_mean_elements_within_six_standard_errors':bool(np.all(abs(mean)<=6*mean_se+1e-12*np.sqrt(np.max(np.diag(truth))))),
        'maximum_normalized_iid_counterfactual_difference':float(np.max(abs(truth-iid)/np.maximum(normal,1e-15*np.max(normal)))),
        'maximum_normalized_covariance_difference':float(np.max(abs(measured-truth)/np.maximum(normal,1e-15*np.max(normal)))),
        'known_variance_to_iid_variance_range':[float(ratios.min()),float(ratios.max())],
        'raw_covariance_supplied':True,'observed_visibility_selection':False}


def cases():
    mode=np.exp(1j*np.array([0.,.4,1.1,2.2]));s=np.ones((4,4))+.7*mode[:,None]*mode.conj()[None,:]+1.5*np.eye(4)
    out=[]
    for length,channel,offsets,label in [(8,4,[0.]*4,'reference-fft8-dc'),(32,16,[.25]*4,'reference-fft32-dc'),
        (32,24,[.25]*4,'reference-fft32-quarter-band'),(8,6,[0.,.25,.5,.75],'station-offsets-fft8-quarter-band')]:
        h=np.array([aligned_fft_kernel(length,channel,x) for x in offsets])
        out.append((label,s,h,length,128,{'fft_length':length,'channel_index':channel,'fractional_sample_offsets':offsets,
            'description':'Equal sample rates, fixed fractional offsets, reference FIR/sinc/FFT; white known Gaussian input'}))
    out.append(('long-moving-average',s,np.full((4,65),1/np.sqrt(65)),8,128,
        {'description':'Illustrative normalized 65-sample moving average at stride8; not the production alignment filter'}))
    out.append(('different-integer-shifts',np.ones((3,3))+np.eye(3),np.eye(3),1,16,
        {'description':'Illustrative station-specific time shifts; zero mean visibility but cross-baseline noise, no closure image'}))
    return out


def run(output,trials=8192):
    if isinstance(trials,bool) or not isinstance(trials,int) or not 256<=trials<=32768:raise ValueError('256..32768 trials required')
    out=Path(output);out.mkdir(parents=True,exist_ok=False);rows=[]
    for index,(label,s,h,stride,m,parameters) in enumerate(cases()):
        q=experiment(s,h,stride,m,trials,49+index);q.update(label=label,parameters=parameters,
             raw_station_covariance_real=s.real.tolist(),raw_station_covariance_imag=s.imag.tolist())
        assert q['all_covariance_elements_within_six_standard_errors'],label
        assert q['all_mean_elements_within_six_standard_errors'],label
        rows.append(q)
    summary={'type':'filtered_visibility_noise_validation','trials_per_case':trials,'cases':rows,
        'actual_hardware_data':False,'production_rml_noise_model_changed':False,
        'physical_adc_vdif_processed':False,'measured_effective_sample_count':False,
        'scope':'Known iid proper Gaussian raw covariance and fixed finite operators. Exact moments and finite Monte Carlo, no real input spectrum, variable clocks, ADC, masks or hardware confidence.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,3,figsize=(14,4.8));x=np.arange(len(rows))
    for k in (0,1):ax[0].scatter(x,[r['known_variance_to_iid_variance_range'][k] for r in rows],label=['Minimum','Maximum'][k])
    ax[0].set(yscale='log',ylabel='Variance ratio: exact / iid',title='Fixed assumed Gaussian operators');ax[0].legend()
    ax[1].bar(x,[r['maximum_normalized_covariance_difference'] for r in rows]);ax[1].set(ylabel='MC covariance difference',title='Monte Carlo vs exact Gaussian moments')
    ax[2].bar(x,[r['maximum_normalized_iid_counterfactual_difference'] for r in rows]);ax[2].set(ylabel='Exact vs iid covariance difference',title='Includes cross-baseline structure')
    for a in ax:a.set_xticks(x,[r['label'] for r in rows],rotation=40,ha='right');a.grid(alpha=.2)
    fig.tight_layout();fig.savefig(out/'filtered-noise.png',dpi=140);plt.close(fig)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--trials',type=int,default=8192)
    run(**vars(parser.parse_args()))
