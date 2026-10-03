"""Fixed Gaussian voltage ensembles for noise-subtracted pilot time powers."""
import json
from pathlib import Path
import numpy as np
from vsora_correlator.time_scatter import time_power_moments


def experiment(kind,trials=2048,seed=51):
    if kind not in ('constant','periodic_phase','amplitude','weak'):
        raise ValueError('unknown time-scatter model')
    if isinstance(trials,bool) or not isinstance(trials,int) or trials<64:
        raise ValueError('at least 64 trials required')
    rng=np.random.default_rng(seed);nt=128;m=32;n=4
    rho=.001 if kind=='weak' else .3;s=rho*np.ones((n,n))+np.eye(n)
    pairs=np.array([(i,j) for i in range(n) for j in range(i+1,n)])
    gain=np.ones((nt,n),complex);angle=2*np.pi*np.arange(nt)*8/nt
    if kind=='periodic_phase':gain[:,3]=np.exp(.8j*np.sin(angle))
    elif kind=='amplitude':gain[:,3]=1+.5*np.sin(angle)
    true_mean=s[pairs[:,0],pairs[:,1]][None,:]*gain[:,pairs[:,0]]*gain[:,pairs[:,1]].conj()
    target={'time_power':np.mean(abs(true_mean)**2,axis=0),'mean_power':abs(np.mean(true_mean,axis=0))**2}
    target['excess']=target['time_power']-target['mean_power']
    samples={k:[] for k in target};ratio_nonpositive=np.zeros(len(pairs),int);ratio_outside=np.zeros(len(pairs),int)
    for first in range(0,trials,16):
        count=min(16,trials-first)
        z=(rng.normal(size=(count,nt,m,n))+1j*rng.normal(size=(count,nt,m,n)))/np.sqrt(2)
        x=(z @ np.linalg.cholesky(s).T)*gain[None,:,None,:]
        shat=np.einsum('rtmi,rtmj->rtij',x,x.conj())/m
        v=shat[:,:,pairs[:,0],pairs[:,1]];power=shat.diagonal(axis1=-2,axis2=-1).real
        nu=(m*power[:,:,pairs[:,0]]*power[:,:,pairs[:,1]]-abs(v)**2)/(m*m-1)
        for a,noise in zip(v,nu):
            q=time_power_moments(a,noise)
            for key in target:samples[key].append(q[key])
            ok=q['time_power']>0;ratio_nonpositive+=~ok
            ratio=np.divide(q['mean_power'],q['time_power'],out=np.zeros(len(pairs)),where=ok)
            ratio_outside+=ok & ((ratio<0)|(ratio>1))
    records={};passed=True
    for key,truth in target.items():
        values=np.array(samples[key]);observed=values.mean(axis=0);se=values.std(axis=0,ddof=1)/np.sqrt(trials)
        tolerance=6*se+1e-12;consistent=bool(np.all(abs(observed-truth)<=tolerance));passed &= consistent
        records[key]={'target':truth.tolist(),'ensemble_mean':observed.tolist(),'standard_error':se.tolist(),
            'all_baselines_within_6se':consistent,'maximum_normalized_mean_difference':float(np.max(abs(observed-truth)/(se+1e-15)))}
    return {'model':kind,'trials':trials,'time_cells':nt,'independent_fft_samples_per_cell':m,
        'powers':records,'all_power_means_within_6se':passed,
        'nonpositive_time_power_fraction':(ratio_nonpositive/trials).tolist(),
        'ratio_outside_zero_to_one_fraction':(ratio_outside/trials).tolist(),
        'generating_truth_used_by_power_estimator':False,'known_truth_used_only_for_validation':True,
        'ratio_unbiased_guarantee':False}


def run(output,trials=2048):
    out=Path(output)
    if out.exists():raise FileExistsError('validation output already exists')
    out.mkdir(parents=True)
    cases=[experiment(k,trials,51+i) for i,k in enumerate(('constant','periodic_phase','amplitude','weak'))]
    q={'type':'pilot_time_scatter_validation','state':'complete','cases':cases,
        'iid_gaussian_voltage_model':True,'physical_adc_vdif_processed':False,
        'observed_value_selection_used':False,'real_hardware_validation_performed':False,
        'time_cell_independence_measured':False,'confidence_interval_calibrated':False,
        'production_rml_noise_model_changed':False,
        'scope':'Ensemble power means under independent proper Gaussian raw voltage cells; estimated noise from the same samples. Ratios are not unbiased or hardware coherence.'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n')
    if not all(c['all_power_means_within_6se'] for c in cases):raise RuntimeError('power ensemble mean outside fixed 6SE criterion')
    return q


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--trials',type=int,default=2048)
    q=run(**vars(parser.parse_args()));print(json.dumps({'state':q['state'],'cases':len(q['cases'])}))


if __name__=='__main__':main()
