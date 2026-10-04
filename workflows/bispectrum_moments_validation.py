"""Known iid Gaussian U3 joint moments, not an observed noise estimator."""
import json
from pathlib import Path
import numpy as np
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum
from vsora_simulator.bispectrum_moments import gaussian_distinct_bispectrum_moments


def model(label):
    phase=np.exp(1j*np.array([0,.7,1.9,-.5]));identity=np.eye(4)
    if label=='zero':return identity,128
    if label=='weak':return identity+.001*np.ones((4,4)),128
    if label=='low':return identity+.1*np.ones((4,4)),128
    if label=='two_components':return identity+.2*np.ones((4,4))+.15*phase[:,None]*phase.conj()[None,:],32
    if label=='rank_one':return np.ones((4,4)),32
    raise ValueError('unknown known-Gaussian bispectrum model')


def experiment(label,trials=8192,seed=59):
    if isinstance(trials,bool) or not isinstance(trials,int) or not 128<=trials<=65536:
        raise ValueError('integer trials128..65536 required')
    s,m=model(label);theory=gaussian_distinct_bispectrum_moments(s,m)
    rng=np.random.default_rng(seed);values=[]
    root=None if label=='rank_one' else np.linalg.cholesky(s)
    for start in range(0,trials,64):
        n=min(64,trials-start)
        if label=='rank_one':
            z=(rng.normal(size=(n,m,1))+1j*rng.normal(size=(n,m,1)))/np.sqrt(2)
            x=np.repeat(z,4,axis=-1)
        else:
            z=(rng.normal(size=(n,m,4))+1j*rng.normal(size=(n,m,4)))/np.sqrt(2);x=z @ root.T
        values.extend(distinct_sample_bispectrum(x)['distinct_sample_bispectrum'])
    u=np.array(values);residual=u-theory['mean'];parts=np.c_[residual.real,residual.imag]
    mean=parts.mean(axis=0);mean_se=parts.std(axis=0,ddof=1)/np.sqrt(trials)
    products=parts[:,:,None]*parts[:,None,:];observed=products.mean(axis=0)
    se=products.std(axis=0,ddof=1)/np.sqrt(trials);target=theory['real_covariance'];scale=max(1.,float(np.max(abs(target))))
    within=bool(np.all(abs(mean)<=6*mean_se+1e-12*scale) and np.all(abs(observed-target)<=6*se+1e-12*scale))
    diagonal=np.diag(target);den=np.sqrt(np.maximum(diagonal[:,None]*diagonal[None,:],0));floor=max(float(diagonal.max()),np.finfo(float).tiny)*1e-14
    normalized=abs(observed-target)/np.maximum(den,floor)
    nonzero=den>floor;correlation=np.divide(target,den,out=np.zeros_like(target),where=nonzero);np.fill_diagonal(correlation,0)
    triangle_power=np.prod(s.diagonal().real[theory['triangles']],axis=1)
    null_variance=triangle_power**2/(m*(m-1)*(m-2))
    ratio=theory['complex_covariance'].diagonal().real/null_variance
    return {'model':label,'samples':m,'trials':trials,'triangles':theory['triangles'].tolist(),
        'true_bispectrum_real_imag':np.c_[theory['mean'].real,theory['mean'].imag].tolist(),
        'mean_residual_real_imag_order':mean.tolist(),'mean_standard_error':mean_se.tolist(),
        'real_covariance_model':target.tolist(),'real_covariance_mc':observed.tolist(),'real_covariance_mc_standard_error':se.tolist(),
        'exact_complex_to_null_variance_ratio_range':[float(ratio.min()),float(ratio.max())],
        'maximum_absolute_offdiagonal_real_correlation':float(np.max(abs(correlation))),
        'maximum_normalized_covariance_difference':float(np.max(normalized[nonzero])),
        'all_means_and_real_covariances_within_6se':within,'generating_covariance_supplied':True,
        'observed_sample_selection_used':False,'gaussian_bispectrum_likelihood_assumed':False,
        'physical_adc_vdif_processed':False,'actual_temporal_independence_verified':False}


def run(output,trials=8192):
    out=Path(output)
    if out.exists():raise FileExistsError('new output required')
    out.mkdir(parents=True)
    cases=[experiment(label,trials,59+i) for i,label in enumerate(('zero','weak','low','two_components','rank_one'))]
    passed=all(c['all_means_and_real_covariances_within_6se'] for c in cases)
    q={'type':'joint_bispectrum_moments_validation','state':'complete' if passed else 'failed_validation','trials_per_case':trials,'cases':cases,
        'real_parameter_order':'all real triangles, then all imaginary triangles',
        'possible_sample_overlap_patterns':34,'algebraic_contraction_products':105,
        'generating_covariance_supplied':True,'physical_adc_vdif_processed':False,
        'actual_temporal_independence_verified':False,'real_hardware_validation_performed':False,
        'production_rml_noise_model_changed':False,'gaussian_bispectrum_likelihood_assumed':False,
        'scope':'Exact iid proper Gaussian voltage U3 mean/covariance with known station S and constant gain. Not a Gaussian bispectrum distribution, observed noise estimator, sample-power normalization, actual receiver independence or image confidence.'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(13,4.4));labels=['Zero','Weak','Low','Two comp','Rank1'];x=np.arange(5)
    for c,a in zip(cases,x):
        lo,hi=c['exact_complex_to_null_variance_ratio_range'];axes[0].plot([a,a],[lo,hi],'o-')
    axes[0].set_yscale('log');axes[0].axhline(1,color='gray',linestyle='--');axes[0].set(title='Exact source variance / null scale',ylabel='Complex variance ratio')
    axes[1].bar(x,[c['maximum_absolute_offdiagonal_real_correlation'] for c in cases]);axes[1].set(title='Shared-triangle real correlation',ylabel='Maximum |off-diagonal correlation|')
    axes[2].bar(x,[c['maximum_normalized_covariance_difference'] for c in cases]);axes[2].set(title='MC vs exact joint covariance',ylabel='Maximum standardized difference')
    for ax in axes:ax.set_xticks(x,labels,rotation=25,ha='right');ax.grid(axis='y',alpha=.2)
    fig.tight_layout();fig.savefig(out/'bispectrum-moments.png',dpi=140);plt.close(fig)
    if not passed:raise RuntimeError('joint bispectrum mean/covariance outside fixed 6SE criterion')
    return q


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--trials',type=int,default=8192)
    q=run(**vars(p.parse_args()));print(json.dumps({'state':q['state'],'cases':len(q['cases'])}))
