"""Known separable signal plus receiver Gaussian covariance: time-dependent means."""
import json
from pathlib import Path
import numpy as np
from vsora_simulator.bispectrum_common_temporal import common_temporal_bispectrum_mean
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum
from vsora_simulator.bispectrum_temporal import white_filter_temporal_covariance
from vsora_simulator.filtered_noise import aligned_fft_kernel
from workflows.bispectrum_moments_validation import model

SOURCES=('zero','weak','low','two_components','rank_one')
TIME_MODELS=('white','long_average','reference_fft','guarded_average','guarded_reference')


def time_model(label):
    if label not in TIME_MODELS:raise ValueError('known common time model required')
    nominal=128;guard={'guarded_average':9,'guarded_reference':5}.get(label,1)
    if label=='white':h=np.ones(1);hop=1
    elif label in ('long_average','guarded_average'):h=np.ones(65)/np.sqrt(65);hop=8
    else:h=aligned_fft_kernel(32,16,.25);h=h/np.sqrt(np.sum(abs(h)**2));hop=32
    k=white_filter_temporal_covariance(h,hop,nominal)[::guard,::guard]
    return k,{'nominal_time_outputs':nominal,'retained_outputs':len(k),'guard_step_outputs':guard,
        'kernel_length':len(h),'raw_stride_samples':hop,
        'known_temporal_covariance_is_identity':bool(np.allclose(k,np.eye(len(k)),rtol=1e-12,atol=1e-14))}


def experiment(source,time_label,trials=8192,seed=72):
    if isinstance(trials,bool) or not isinstance(trials,int) or not 1024<=trials<=32768:raise ValueError('integer trials1024..32768 required')
    if isinstance(seed,bool) or not isinstance(seed,int) or not 0<=seed<=2**32-1:raise ValueError('integer seed0..2^32-1 required')
    s,_=model(source);k,info=time_model(time_label);theory=common_temporal_bispectrum_mean(s,k)
    eig,vec=np.linalg.eigh(s);root_s=vec*np.sqrt(np.maximum(eig,0));root_k=np.linalg.cholesky(k)
    rng=np.random.default_rng(seed);values={'ordinary':[],'distinct':[]}
    for first in range(0,trials,64):
        count=min(64,trials-first);shape=(count,len(k),len(s))
        z=(rng.normal(size=shape)+1j*rng.normal(size=shape))/np.sqrt(2)
        x=(root_k @ z) @ root_s.T;q=distinct_sample_bispectrum(x)
        values['ordinary'].append(q['ordinary_visibility_product']);values['distinct'].append(q['distinct_sample_bispectrum'])
    methods={};target=theory['true_marginal_bispectrum']
    for name,key in [('ordinary','ordinary_bispectrum_mean'),('distinct','distinct_bispectrum_mean')]:
        sample=np.concatenate(values[name]);parts=np.stack([sample.real,sample.imag],axis=-1)
        mean=parts.mean(axis=0);se=parts.std(axis=0,ddof=1)/np.sqrt(trials)
        expected=np.c_[theory[key].real,theory[key].imag];delta=mean-expected
        target_parts=np.c_[target.real,target.imag];bias=expected-target_parts
        rounding=1e-12*max(float(np.max(abs(expected))),float(np.max(abs(target))),1)
        methods[name]={'known_mean_real_imag':expected.tolist(),'ensemble_mean_real_imag':mean.tolist(),
            'mc_mean_standard_error':se.tolist(),'bias_from_marginal_true_bispectrum':bias.tolist(),
            'all_mean_components_within_6se':bool(np.all(abs(delta)<=6*se+rounding)),
            'maximum_absolute_normalized_mean_difference':float(np.max(abs(delta)/(se+rounding))),
            'known_bias_exceeds_six_mc_se':bool(np.any(abs(bias)>6*se+rounding))}
    return {'source_model':source,'time_model':time_label,'trials':trials,'seed':seed,**info,
        'triangles':theory['triangles'].tolist(),'true_marginal_bispectrum_real_imag':np.c_[target.real,target.imag].tolist(),
        'temporal_diagonal_power':theory['temporal_diagonal_power'],'off_diagonal_pair_sum':theory['off_diagonal_pair_sum'],
        'distinct_time_cycle_sum':theory['distinct_time_cycle_sum'],
        'distinct_pair_bias_real_imag':np.c_[theory['distinct_pair_bias'].real,theory['distinct_pair_bias'].imag].tolist(),
        'distinct_cycle_bias_real_imag':np.c_[theory['distinct_cycle_bias'].real,theory['distinct_cycle_bias'].imag].tolist(),
        'methods':methods,'all_mean_components_within_6se':all(m['all_mean_components_within_6se'] for m in methods.values()),
        'gaussian_coefficients_generated_from_known_covariance':True,'common_separable_space_time_covariance_assumed':True,
        'physical_raw_filter_convolution_performed':False,'actual_temporal_independence_verified':False}


def run(output,trials=8192):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    cases=[experiment(source,time_label,trials,72+source_index*5+time_index)
        for source_index,source in enumerate(SOURCES) for time_index,time_label in enumerate(TIME_MODELS)]
    passed=all(c['all_mean_components_within_6se'] for c in cases)
    q={'type':'signal_temporal_bispectrum_validation','state':'complete' if passed else 'failed_validation',
        'trials_per_condition':trials,'cases':cases,'station_covariance_supplied':True,'temporal_covariance_supplied':True,
        'common_separable_space_time_covariance_assumed':True,'station_specific_kernels_modelled':False,
        'observed_bias_correction_performed':False,'variance_or_likelihood_calculated':False,
        'physical_raw_filter_convolution_performed':False,'physical_adc_vdif_processed':False,
        'actual_temporal_independence_verified':False,'real_hardware_validation_performed':False,
        'production_correlator_statistics_changed':False,'production_rml_noise_model_changed':False,
        'scope':'Known constant S times common stationary K proper-Gaussian voltage, with supplied signal/noise model. Means only: no observed covariance, independent hardware sample count, variable station clocks, actual raw FIR, ADC/VDIF, likelihood or image confidence.'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');plot(q,out/'bispectrum-signal-temporal.png')
    if not passed:raise RuntimeError('known signal temporal means outside fixed six MC SE criterion')
    return q


def plot(result,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(12,8));x=np.arange(5)
    source_labels={'zero':'No source','weak':'Weak source','low':'Stronger source','two_components':'Two components','rank_one':'Perfect shared signal'}
    labels=['White','Long average','FFT model','Average guard','FFT guard']
    for index,source in enumerate(SOURCES):
        cases=[c for c in result['cases'] if c['source_model']==source]
        axes[0,0].plot(x,[c['methods']['distinct']['known_mean_real_imag'][0][0] for c in cases],marker='o',label=source_labels[source])
        axes[1,0].plot(x,[c['methods']['distinct']['maximum_absolute_normalized_mean_difference'] for c in cases],marker='o',label=source_labels[source])
    axes[0,0].set(title='Known U3 mean: first triangle real part',ylabel='Model units');axes[0,0].set_yscale('symlog',linthresh=1e-9);axes[0,0].legend(fontsize=8)
    two=[c for c in result['cases'] if c['source_model']=='two_components']
    for component,label in [(0,'Real'),(1,'Imaginary')]:
        axes[0,1].plot(x,[c['methods']['distinct']['known_mean_real_imag'][0][component] for c in two],marker='o',label='U3 '+label)
        axes[0,1].plot(x,[c['true_marginal_bispectrum_real_imag'][0][component] for c in two],linestyle='--',label='True '+label)
    axes[0,1].set(title='Two components: mean is not always true B',ylabel='Model units');axes[0,1].legend(fontsize=8)
    axes[1,0].set(title='U3 ensemble mean vs known mean: all components',ylabel='Maximum absolute difference / MC SE');axes[1,0].axhline(6,color='gray',linestyle='--')
    cases=result['cases'][:5];axes[1,1].bar(x,[c['retained_outputs'] for c in cases]);axes[1,1].set(title='Known-model retained outputs',ylabel='Count, not hardware independence')
    for axis in axes.ravel():axis.set_xticks(x,labels,rotation=20,ha='right');axis.grid(alpha=.2)
    fig.suptitle('Known common Gaussian space/time covariance with signal\nExact means only; no physical FIR, ADC/VDIF, observed bias correction or image likelihood',fontsize=10)
    fig.tight_layout(rect=(0,0,1,.91));fig.savefig(path,dpi=140);plt.close(fig)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--trials',type=int,default=8192)
    q=run(**vars(p.parse_args()));print(json.dumps({'state':q['state'],'cases':len(q['cases'])}))
