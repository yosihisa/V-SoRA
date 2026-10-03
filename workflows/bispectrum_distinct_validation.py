"""Fixed Gaussian ensembles: shared-sample bispectrum bias and distinct indices."""
import json
from pathlib import Path
import numpy as np
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum,gaussian_ordinary_bispectrum_mean
from vsora_simulator.visibility_moments import visibility_noise_moments


def experiment(label,trials=16384,seed=53):
    if isinstance(trials,bool) or not isinstance(trials,int) or trials<64:raise ValueError('at least 64 trials required')
    phase=np.exp(1j*np.array([0.,.7,1.9]))
    models={'zero_source':(np.eye(3),32),'weak_unresolved':(.001*np.ones((3,3))+np.eye(3),128),
        'low_snr':(.1*np.ones((3,3))+np.eye(3),128),
        'two_components':(.2*np.ones((3,3))+.15*phase[:,None]*phase.conj()[None,:]+np.eye(3),32),
        'rank_one':(np.ones((3,3)),32)}
    if label not in models:raise ValueError('unknown bispectrum model')
    s,m=models[label];theory=gaussian_ordinary_bispectrum_mean(s,m);truth=theory['true_bispectrum'][0]
    expected=theory['ordinary_product_mean'][0];rng=np.random.default_rng(seed);values={'ordinary':[],'distinct':[]}
    root=None if label=='rank_one' else np.linalg.cholesky(s)
    for first in range(0,trials,64):
        count=min(64,trials-first)
        z=(rng.normal(size=(count,m,3))+1j*rng.normal(size=(count,m,3)))/np.sqrt(2)
        x=np.repeat(z[:,:,:1],3,axis=-1) if root is None else z @ root.T
        q=distinct_sample_bispectrum(x)
        values['ordinary'].extend(q['ordinary_visibility_product'][:,0]);values['distinct'].extend(q['distinct_sample_bispectrum'][:,0])
    results={}
    for name,target in [('ordinary',expected),('distinct',truth)]:
        sample=np.asarray(values[name]);components=np.stack([sample.real,sample.imag],axis=-1)
        mean=components.mean(axis=0);covariance=np.cov(components,rowvar=False,ddof=1);se=np.sqrt(np.diag(covariance)/trials)
        target_components=np.array([target.real,target.imag]);difference=mean-target_components
        consistent=bool(np.all(abs(difference)<=6*se+1e-12))
        results[name]={'target_mean':target_components.tolist(),'ensemble_mean':mean.tolist(),
            'mean_standard_error':se.tolist(),'sample_covariance_real_imag':covariance.tolist(),
            'all_mean_components_within_6se':consistent,
            'normalized_mean_difference':(difference/(se+1e-15)).tolist()}
    moments=visibility_noise_moments(s,m);snr=abs(moments['mean'])/np.sqrt(np.diag(moments['complex_covariance']).real/2)
    distinct_se=np.linalg.norm(results['distinct']['mean_standard_error'])
    return {'model':label,'trials':trials,'samples_per_window':m,'station_covariance_real':s.real.tolist(),
        'station_covariance_imag':s.imag.tolist(),'triangle':[0,1,2],'true_bispectrum':[truth.real,truth.imag],
        'ordinary_analytic_bias':[(expected-truth).real,(expected-truth).imag],
        'known_quadrature_rms_baseline_snr_range':[float(snr.min()),float(snr.max())],
        'methods':results,'all_mean_components_within_6se':all(r['all_mean_components_within_6se'] for r in results.values()),
        'known_true_mean_above_six_mc_standard_errors':bool(abs(truth)>6*distinct_se),
        'estimator_generating_truth_used':False,'truth_used_only_for_validation':True,
        'closure_phase_unbiased_guarantee':False,'mean_confidence_calibrated':False}


def run(output,trials=16384):
    out=Path(output)
    if out.exists():raise FileExistsError('bispectrum validation output already exists')
    out.mkdir(parents=True)
    cases=[experiment(name,trials,53+i) for i,name in enumerate(('zero_source','weak_unresolved','low_snr','two_components','rank_one'))]
    q={'type':'distinct_sample_bispectrum_validation','state':'complete','trials_per_case':trials,'cases':cases,
        'iid_gaussian_voltage_model':True,'physical_adc_vdif_processed':False,'filter_correlation_included':False,
        'observed_sample_selection_used':False,'real_hardware_validation_performed':False,
        'production_correlator_statistics_changed':False,'production_rml_noise_model_changed':False,
        'scope':'Experimental iid fixed-gain voltage bispectrum means; sample-distinct indices remove shared-sample bias under assumptions. No unbiased phase, actual sensitivity or image guarantee.'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(14,4.8));labels=['No source','Unresolved','Low SNR','Two modes','Rank one'];positions=np.arange(len(cases))
    for component,offset,color in [(0,-.15,'C0'),(1,.15,'C1')]:
        for axis,name in zip(axes[:2],('ordinary','distinct')):
            axis.bar(positions+offset,[c['methods'][name]['normalized_mean_difference'][component] for c in cases],width=.28,label='Real' if component==0 else 'Imag',color=color)
        axes[2].bar(positions+offset,[c['ordinary_analytic_bias'][component]/(c['methods']['ordinary']['mean_standard_error'][component]+1e-15) for c in cases],width=.28,label='Real' if component==0 else 'Imag',color=color)
    for axis,title in zip(axes,['Ordinary: MC vs analytic mean','Distinct: MC vs true bispectrum','Ordinary bias vs MC mean SE']):
        axis.set_title(title);axis.set_xticks(positions,labels,rotation=25,ha='right');axis.axhline(0,color='k',linewidth=.7);axis.set_ylabel('Difference / MC standard error');axis.legend();axis.grid(axis='y',alpha=.2)
    for axis in axes[:2]:axis.axhline(6,color='gray',linestyle='--');axis.axhline(-6,color='gray',linestyle='--')
    fig.tight_layout();fig.savefig(out/'bispectrum-distinct.png',dpi=140);plt.close(fig)
    if not all(c['all_mean_components_within_6se'] for c in cases):raise RuntimeError('ensemble mean outside fixed 6SE criterion')
    return q


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--trials',type=int,default=16384)
    q=run(**vars(p.parse_args()));print(json.dumps({'state':q['state'],'cases':len(q['cases'])}))


if __name__=='__main__':main()
