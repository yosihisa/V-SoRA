"""Independent receiver stations, known coloured Gaussian time covariance."""
import json
from pathlib import Path
import numpy as np
from vsora_simulator.bispectrum_temporal import white_filter_temporal_covariance,temporal_receiver_bispectrum_mean
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum
from vsora_simulator.filtered_noise import aligned_fft_kernel


def experiment(label,trials=8192,seed=55):
    if isinstance(trials,bool) or not isinstance(trials,int) or trials<64:raise ValueError('at least 64 trials required')
    models={'white':('white',1),'long_average':('box',1),'reference_fft':('reference',1),
        'guarded_average':('box',9),'guarded_reference':('reference',5)}
    if label not in models:raise ValueError('unknown temporal bispectrum model')
    kind,guard=models[label];nominal=128
    if kind=='white':h=np.ones(1);hop=1
    elif kind=='box':h=np.ones(65)/np.sqrt(65);hop=8
    else:h=aligned_fft_kernel(32,16,.25);h=h/np.sqrt(np.sum(abs(h)**2));hop=32
    k=white_filter_temporal_covariance(h,hop,nominal)[::guard,::guard];m=len(k)
    theory=temporal_receiver_bispectrum_mean(np.repeat(k[None],3,axis=0))
    root=np.linalg.cholesky(k);rng=np.random.default_rng(seed);values={'ordinary':[],'distinct':[]}
    for first in range(0,trials,64):
        count=min(64,trials-first)
        z=(rng.normal(size=(count,m,3))+1j*rng.normal(size=(count,m,3)))/np.sqrt(2)
        x=root @ z;q=distinct_sample_bispectrum(x)
        values['ordinary'].extend(q['ordinary_visibility_product'][:,0]);values['distinct'].extend(q['distinct_sample_bispectrum'][:,0])
    methods={}
    for name,target in [('ordinary',theory['ordinary_bispectrum_mean']),('distinct',theory['distinct_bispectrum_mean'])]:
        sample=np.array(values[name]);components=np.stack([sample.real,sample.imag],axis=-1)
        mean=components.mean(axis=0);cov=np.cov(components,rowvar=False,ddof=1);se=np.sqrt(np.diag(cov)/trials)
        expected=np.array([target.real,target.imag]);difference=mean-expected
        methods[name]={'known_coloured_model_mean':expected.tolist(),'ensemble_mean':mean.tolist(),
            'mean_standard_error':se.tolist(),'sample_covariance_real_imag':cov.tolist(),
            'all_mean_components_within_6se':bool(np.all(abs(difference)<=6*se+1e-12)),
            'normalized_mean_difference':(difference/(se+1e-15)).tolist()}
    target=theory['distinct_bispectrum_mean'];se=np.linalg.norm(methods['distinct']['mean_standard_error'])
    return {'model':label,'trials':trials,'nominal_time_outputs':nominal,'retained_outputs':m,'guard_step_outputs':guard,
        'kernel_length':len(h),'raw_stride_samples':hop,'output_station_power_model':float(k[0,0].real),
        'true_astronomical_bispectrum':[0.,0.],'methods':methods,
        'conditional_temporal_covariance_is_identity':bool(np.allclose(k,np.eye(m),rtol=1e-12,atol=1e-14)),
        'known_distinct_bias_above_six_mc_se':bool(abs(target)>6*se),
        'all_mean_components_within_6se':all(r['all_mean_components_within_6se'] for r in methods.values()),
        'temporal_covariance_supplied':True,'actual_temporal_independence_verified':False,
        'gaussian_coefficients_generated_from_known_covariance':True,'physical_raw_filter_convolution_performed':False}


def run(output,trials=8192):
    out=Path(output)
    if out.exists():raise FileExistsError('temporal bispectrum validation output already exists')
    out.mkdir(parents=True)
    cases=[experiment(label,trials,55+i) for i,label in enumerate(('white','long_average','reference_fft','guarded_average','guarded_reference'))]
    q={'type':'temporal_bispectrum_validation','state':'complete','trials_per_case':trials,'cases':cases,
        'zero_astronomical_cross_covariance':True,'independent_receiver_stations_assumed':True,
        'physical_adc_vdif_processed':False,'physical_raw_filter_convolution_performed':False,
        'actual_temporal_independence_verified':False,'real_hardware_validation_performed':False,
        'production_correlator_statistics_changed':False,'production_rml_noise_model_changed':False,
        'scope':'Known zero-source independent receiver Gaussian temporal covariances. Distinct-index bias and conditional disjoint-support guard; no observed covariance, clock/gain drift, actual ADC or sensitivity recommendation.'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(14,4.8));labels=['White','Long avg','FFT model','Avg guard','FFT guard'];positions=np.arange(5)
    for name,offset in [('ordinary',-.15),('distinct',.15)]:
        axes[0].bar(positions+offset,[c['methods'][name]['known_coloured_model_mean'][0] for c in cases],width=.28,label=name)
    axes[0].set(title='Known mean, true sky bispectrum = 0',ylabel='Bispectrum (model units)');axes[0].legend()
    for component,offset in [(0,-.15),(1,.15)]:
        axes[1].bar(positions+offset,[c['methods']['distinct']['normalized_mean_difference'][component] for c in cases],width=.28,label='Real' if component==0 else 'Imag')
    axes[1].set(title='Distinct: MC vs coloured-model mean',ylabel='Difference / MC standard error');axes[1].legend();axes[1].axhline(6,color='gray',linestyle='--');axes[1].axhline(-6,color='gray',linestyle='--')
    axes[2].bar(positions,[c['retained_outputs'] for c in cases]);axes[2].set(title='Retained model outputs',ylabel='Output count, not measured independence')
    for axis in axes:axis.set_xticks(positions,labels,rotation=25,ha='right');axis.axhline(0,color='k',linewidth=.7);axis.grid(axis='y',alpha=.2)
    fig.tight_layout();fig.savefig(out/'bispectrum-temporal.png',dpi=140);plt.close(fig)
    if not all(c['all_mean_components_within_6se'] for c in cases):raise RuntimeError('temporal model mean outside fixed 6SE criterion')
    return q


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--trials',type=int,default=8192)
    q=run(**vars(p.parse_args()));print(json.dumps({'state':q['state'],'cases':len(q['cases'])}))
