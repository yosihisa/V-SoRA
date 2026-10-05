"""Known joint station/time Gaussian covariance and supplied phase correction."""
import argparse,json
from pathlib import Path
import numpy as np
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum
from vsora_simulator.bispectrum_joint_temporal import joint_temporal_bispectrum_mean


def known_covariance(stations,kind,samples=8):
    if isinstance(stations,bool) or not isinstance(stations,(int,np.integer)) or stations not in (4,8):raise ValueError('known4/8station model required')
    if kind not in ('white','common_correlated','station_coefficients'):raise ValueError('known coefficient model required')
    if isinstance(samples,bool) or not isinstance(samples,(int,np.integer)) or not 3<=samples<=32:raise ValueError('integer3..32sample model required')
    s=np.eye(stations)+.2*np.ones((stations,stations))
    if kind!='station_coefficients':
        k=np.eye(samples) if kind=='white' else .4**abs(np.arange(samples)[:,None]-np.arange(samples)[None,:])
        return np.einsum('tu,ij->tiuj',k,s)
    coefficients=np.zeros((stations,samples,samples+2),complex)
    for i in range(stations):
        taps=np.array([1.,.2+.1j*i/(stations-1),-.1+.03j*i]);taps/=np.linalg.norm(taps)
        for t in range(samples):coefficients[i,t,t:t+3]=taps
    return np.einsum('itv,juv,ij->tiuj',coefficients,coefficients.conj(),s)


def known_phase(stations,cycles,samples=8):
    if isinstance(stations,bool) or not isinstance(stations,(int,np.integer)) or stations not in (4,8):raise ValueError('known4/8station phase model required')
    if isinstance(samples,bool) or not isinstance(samples,(int,np.integer)) or not 3<=samples<=32:raise ValueError('integer3..32sample phase model required')
    if isinstance(cycles,bool) or not isinstance(cycles,(int,float,np.number)) or not np.isfinite(cycles) or not 0<=cycles<=1:raise ValueError('finite known cycles0..1 required')
    rates=np.array([0.,.7,-.4,1.2,.2,-.7,.9,-1.1])[:stations]*cycles/.3
    times=np.linspace(0,.3,samples);return np.exp(2j*np.pi*times[:,None]*rates[None,:]),times,rates


def mean_comparison(values,known):
    parts=np.c_[values.real,values.imag];expected=np.r_[known.real,known.imag]
    ensemble=values.mean(axis=0);se=parts.std(axis=0,ddof=1)/np.sqrt(len(parts))
    passed=bool(np.all(abs(parts.mean(axis=0)-expected)<=6*se+1e-12))
    return {'known_mean_real_imag':np.c_[known.real,known.imag].tolist(),'ensemble_mean_real_imag':np.c_[ensemble.real,ensemble.imag].tolist(),
        'mean_mc_standard_error_all_real_then_imag':se.tolist(),'all_means_within_6se':passed}


def experiment(base,phase,seed,trials=8192):
    if isinstance(trials,bool) or not isinstance(trials,int) or not 1024<=trials<=32768:raise ValueError('integer trials1024..32768 required')
    if isinstance(seed,bool) or not isinstance(seed,(int,np.integer)) or not 0<=seed<=2**32-1:raise ValueError('integer seed0..2**32-1 required')
    m,n=base.shape[:2];root=np.linalg.cholesky(base.reshape(m*n,m*n));rng=np.random.default_rng(seed)
    changed=base*phase[:,:,None,None]*phase.conj()[None,None,:,:]
    known={'uncorrected':joint_temporal_bispectrum_mean(changed),'known_inverse_phase':joint_temporal_bispectrum_mean(base)}
    actual={state:{name:[] for name in ('ordinary','distinct')} for state in known};maximum_difference=0.
    for start in range(0,trials,64):
        count=min(64,trials-start);z=(rng.normal(size=(count,m*n))+1j*rng.normal(size=(count,m*n)))/np.sqrt(2)
        x=(z @ root.T).reshape(count,m,n);y=x*phase[None];corrected=y*phase.conj()[None]
        original=distinct_sample_bispectrum(x)
        for state,data in [('uncorrected',y),('known_inverse_phase',corrected)]:
            q=distinct_sample_bispectrum(data)
            for name,key in [('ordinary','ordinary_visibility_product'),('distinct','distinct_sample_bispectrum')]:
                actual[state][name].append(q[key])
                if state=='known_inverse_phase':maximum_difference=max(maximum_difference,float(np.max(abs(q[key]-original[key]))))
    result={}
    for state,theory in known.items():
        result[state]={name:mean_comparison(np.concatenate(actual[state][name]),theory[name+'_bispectrum_mean']) for name in ('ordinary','distinct')}
    instant_difference=float(np.max(abs(known['uncorrected']['instantaneous_population_bispectrum']-known['known_inverse_phase']['instantaneous_population_bispectrum'])))
    passed=all(d['all_means_within_6se'] for state in result.values() for d in state.values()) and maximum_difference<1e-12 and instant_difference<1e-12
    return {'triangles':known['uncorrected']['triangles'].tolist(),'samples':m,'trials':trials,'seed':seed,'methods':result,
        'mean_instantaneous_population_bispectrum_real_imag':np.c_[known['uncorrected']['mean_instantaneous_population_bispectrum'].real,known['uncorrected']['mean_instantaneous_population_bispectrum'].imag].tolist(),
        'maximum_instant_population_phase_difference':instant_difference,'maximum_sample_statistic_after_known_inverse_phase_difference':maximum_difference,
        'all_calculated_means_and_known_phase_invariance_checked':passed}


def run(output,trials=8192):
    if isinstance(trials,bool) or not isinstance(trials,int) or not 1024<=trials<=32768:raise ValueError('integer trials1024..32768 required')
    out=Path(output)
    if out.exists():raise FileExistsError('new joint-time validation output required')
    out.mkdir(parents=True);models=[];cases=[]
    for stations in (4,8):
        for kind in ('white','common_correlated','station_coefficients'):
            base=known_covariance(stations,kind);model_id=f'{stations}-{kind}'
            models.append({'id':model_id,'stations':stations,'kind':kind,'joint_covariance_axis_order':'time,station,time,station',
                'known_covariance_real_imag':np.stack((base.real,base.imag),axis=-1).tolist()})
            for cycles in (0.,.25,1.) if stations==4 else (.25,):
                phase,times,rates=known_phase(stations,cycles);record=experiment(base,phase,78+len(cases),trials)
                cases.append({'model_id':model_id,'stations':stations,'coefficient_model':kind,'known_phase_cycles_multiplier':cycles,
                    'model_times_s':times.tolist(),'generating_known_station_rates_hz':rates.tolist(),**record})
    passed=all(c['all_calculated_means_and_known_phase_invariance_checked'] for c in cases)
    q={'type':'joint_station_time_bispectrum_validation','state':'complete' if passed else 'failed_validation','models':models,'cases':cases,
        'trials_per_case':trials,'known_proper_gaussian_covariance_supplied':True,'known_inverse_phase_supplied':True,
        'physical_adc_vdif_processed':False,'actual_temporal_independence_verified':False,'observed_gain_or_clock_estimated':False,
        'covariance_of_bispectrum_calculated':False,'gaussian_u3_distribution_verified':False,'production_rml_noise_model_changed':False,
        'real_hardware_validation_performed':False,'scope':'Finite known joint Gaussian covariance, white/common time correlation/station-dependent coefficient examples. Supplied phase removal only; no rate estimator, observed bias correction, physical filters or image guarantee.'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');plot(q,out/'joint-time-bispectrum.png')
    if not passed:raise RuntimeError('joint known means or inverse phase outside fixed criterion')
    return q


def plot(q,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for kind in ('white','common_correlated','station_coefficients'):
        rows=[c for c in q['cases'] if c['stations']==4 and c['coefficient_model']==kind]
        x=[c['known_phase_cycles_multiplier'] for c in rows]
        for axis,name in zip(axes,('distinct','ordinary')):
            values=[]
            for c in rows:
                a=np.asarray(c['methods']['uncorrected'][name]['known_mean_real_imag']);b=np.asarray(c['methods']['known_inverse_phase'][name]['known_mean_real_imag'])
                values.append(np.median(np.linalg.norm(a,axis=1)/np.linalg.norm(b,axis=1)))
            axis.plot(x,values,'o-',label=kind)
    for axis,name in zip(axes,('U3','ordinary product')):
        axis.set(title=name,xlabel='Known phase cycles multiplier',ylabel='Median abs(mean uncorrected) / abs(mean corrected)');axis.legend(fontsize=8);axis.grid(alpha=.2)
    fig.suptitle('Known finite joint Gaussian covariance; phase supplied, no physical FFT or image guarantee',fontsize=10)
    fig.tight_layout();fig.savefig(path,dpi=140);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--trials',type=int,default=8192)
    q=run(**vars(p.parse_args()));print(json.dumps({'state':q['state'],'conditions':len(q['cases'])}))
