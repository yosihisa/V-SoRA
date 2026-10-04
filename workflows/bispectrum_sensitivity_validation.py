"""Exact null variance, known-model conditional sensitivity; no image test."""
import json
from pathlib import Path
import numpy as np
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum
from vsora_simulator.bispectrum_sensitivity import null_bispectrum_variance,conditional_bispectrum_plan
from vsora_simulator.sensitivity import sefd_from_area,dish_area


def experiment(samples,trials=8192,seed=57):
    theory=null_bispectrum_variance(samples)
    if isinstance(trials,bool) or not isinstance(trials,int) or not 128<=trials<=65536:
        raise ValueError('integer trials128..65536 required')
    rng=np.random.default_rng(seed);values=[]
    for start in range(0,trials,32):
        shape=(min(32,trials-start),samples,3)
        x=(rng.normal(size=shape)+1j*rng.normal(size=shape))/np.sqrt(2)
        values.extend(distinct_sample_bispectrum(x)['distinct_sample_bispectrum'][:,0])
    u=np.array(values);parts=np.column_stack([u.real,u.imag]);mean=parts.mean(axis=0)
    mean_se=parts.std(axis=0,ddof=1)/np.sqrt(trials)
    moments=np.column_stack([u.real**2,u.imag**2,u.real*u.imag])
    second=moments.mean(axis=0);se=moments.std(axis=0,ddof=1)/np.sqrt(trials)
    expected=np.array([theory['real_variance'],theory['imaginary_variance'],0])
    criterion=bool(np.all(abs(mean)<=6*mean_se+1e-15) and np.all(abs(second-expected)<=6*se+1e-30))
    return {'samples':samples,'trials':trials,'null_complex_variance':theory['complex_variance'],
        'null_quadrature_variance':theory['real_variance'],'ensemble_mean_real_imag':mean.tolist(),
        'mean_standard_error':mean_se.tolist(),'second_moments_real_imag_cross':second.tolist(),
        'second_moment_standard_error':se.tolist(),'expected_second_moments':expected.tolist(),
        'complex_variance_ratio':float((second[0]+second[1])/theory['complex_variance']),
        'complex_variance_ratio_standard_error':float(np.std(abs(u)**2,ddof=1)/np.sqrt(trials)/theory['complex_variance']),
        'pseudo_covariance_real_imag':[float(second[0]-second[1]),float(2*second[2])],
        'means_and_second_moments_within_6se':criterion,'observed_sample_selection_used':False}


def run(output):
    out=Path(output)
    if out.exists():raise FileExistsError('new output required')
    out.mkdir(parents=True)
    cases=[experiment(m,8192 if m<=128 else 2048,57+i) for i,m in enumerate((3,8,32,128,4096))]
    dish_sefd=sefd_from_area(100,dish_area(1,.6));plans=[]
    for sefd in (10000.,100000.,dish_sefd,1000000.):
        for exposure in (.1,.3,1.,3.):
            nominal=int(round(64000*exposure));rho=1000/(sefd+1000)
            for guard in (1,5):
                retained=(nominal+guard-1)//guard
                q=conditional_bispectrum_plan(retained,[rho]*3,window_seconds=exposure)
                plans.append({'assumed_sefd_jy':sefd,'assumed_total_flux_jy':1000.,'assumed_each_baseline_flux_jy':1000.,
                    'assumed_channel_bandwidth_hz':64000.,'nominal_bandwidth_times_exposure':nominal,
                    'illustrative_guard_step':guard,'independent_samples_conditional_input':retained,
                    'bandwidth_time_count_is_assumption_not_measured':True,'point_source_optimistic_model':True,**q})
    result={'type':'bispectrum_sensitivity_validation','state':'complete','null_variance_cases':cases,
        'conditional_point_source_plans':plans,'one_m_dish_assumed_sefd_jy':dish_sefd,
        'source_total_flux_assumed_jy':1000.,'baseline_flux_for_extended_source_not_calculated':True,
        'nonzero_source_variance_calculated':False,'physical_adc_vdif_processed':False,
        'actual_temporal_independence_verified':False,'real_hardware_validation_performed':False,
        'production_rml_noise_model_changed':False,'image_reconstructed':False,
        'scope':'Exact iid null Gaussian U3 variance and conditional point-source scale. Identical sky bispectrum/normalization and independent windows assumed. No nonzero-source likelihood, actual sample count, extended Cas A, uv evolution, bandpass, hardware detectability or image guarantee.'}
    (out/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4.4))
    axes[0].errorbar([c['samples'] for c in cases],[c['complex_variance_ratio'] for c in cases],
        yerr=[6*c['complex_variance_ratio_standard_error'] for c in cases],fmt='o-',capsize=4)
    axes[0].set_xscale('log')
    axes[0].axhline(1,color='gray',linestyle='--');axes[0].set(xlabel='Known iid samples M',ylabel='MC complex variance / exact null value',title='Null complex-power mean, bars = 6 MC SE')
    for guard,style in [(1,'-'),(5,'--')]:
        for exposure in (.3,3.):
            rows=[r for r in plans if r['illustrative_guard_step']==guard and r['window_seconds']==exposure]
            axes[1].loglog([r['assumed_sefd_jy'] for r in rows],[r['conditional_recorded_seconds'] for r in rows],style,marker='o',label=f'{exposure:g}s, every {guard}')
    axes[1].set(xlabel='Assumed station SEFD (Jy)',ylabel='Conditional time for null-scale SNR 5 (s)',title='1000 Jy point model, same triangle repeated')
    axes[1].legend()
    for ax in axes:ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(out/'bispectrum-sensitivity.png',dpi=140);plt.close(fig)
    if not all(c['means_and_second_moments_within_6se'] for c in cases):raise RuntimeError('null variance outside fixed 6SE criterion')
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    q=run(**vars(p.parse_args()));print(json.dumps({'state':q['state'],'cases':len(q['null_variance_cases']),'plans':len(q['conditional_point_source_plans'])}))
