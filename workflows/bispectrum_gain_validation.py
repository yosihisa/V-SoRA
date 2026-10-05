"""Complete-array population bispectrum mean constraints, no noisy logarithms."""
import json
from pathlib import Path
import numpy as np
from vsora_imaging.bispectrum_gain import bispectrum_gain_design
from vsora_simulator.bispectrum_moments import gaussian_distinct_bispectrum_moments


def four_station_example():
    q=bispectrum_gain_design(4);base=np.ones((4,4));np.fill_diagonal(base,10)
    changed=base.copy();changed[0,1]=changed[1,0]=2
    v0=base[tuple(q['pairs'].T)];v1=changed[tuple(q['pairs'].T)]
    log_gain=np.linalg.solve(q['triangle_station_gain_matrix'],-q['triangle_amplitude_matrix'] @ np.log(v1/v0))
    gains=np.exp(log_gain);matched=changed*gains[:,None]*gains[None,:]
    v2=matched[tuple(q['pairs'].T)]
    a=q['triangle_amplitude_matrix'];h=q['conventional_logamp_matrix']
    b0=np.exp(a @ np.log(v0));b2=np.exp(a @ np.log(v2));c0=h @ np.log(v0);c2=h @ np.log(v2)
    m0=gaussian_distinct_bispectrum_moments(base,128);m2=gaussian_distinct_bispectrum_moments(matched,128)
    identical=bool(np.allclose(m0['mean'],m2['mean'],rtol=1e-12,atol=1e-12) and np.allclose(b0,b2,rtol=1e-12,atol=1e-12))
    return {'stations':4,'samples_per_window_for_conditional_moments':128,
        'base_station_covariance':base.tolist(),'changed_station_covariance':changed.tolist(),
        'matched_station_covariance':matched.tolist(),'matching_station_gain_amplitudes':gains.tolist(),
        'base_population_bispectrum_amplitudes':b0.tolist(),'matched_population_bispectrum_amplitudes':b2.tolist(),
        'population_means_identical':identical,'base_conventional_logamps':c0.tolist(),'matched_conventional_logamps':c2.tolist(),
        'conventional_logamp_difference':(c2-c0).tolist(),
        'all_covariances_positive_definite':all(np.linalg.eigvalsh(s).min()>0 for s in (base,changed,matched)),
        'base_station_powers':base.diagonal().tolist(),'matched_station_powers':matched.diagonal().tolist(),
        'station_powers_identical':bool(np.allclose(base.diagonal(),matched.diagonal())),
        'conditional_u3_covariances_identical':bool(np.allclose(m0['real_covariance'],m2['real_covariance'],rtol=1e-12,atol=1e-12)),
        'scope':'Two positive-definite proper-Gaussian station models have the same four population bispectrum means and different conventional closure amplitudes. Powers and finite-sample covariance are allowed to differ. This is not full distributional nonidentifiability, a sky image, or a four-station imaging impossibility proof.'}


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);cases=[]
    for n in range(3,9):
        design=bispectrum_gain_design(n)
        row={k:v for k,v in design.items() if not isinstance(v,np.ndarray)}
        row['gain_null_maximum_residual']=float(np.max(abs(design['gain_invariant_triangle_weights'] @ design['triangle_station_gain_matrix']),initial=0))
        if n>=5:
            stacked=np.vstack([design['gain_invariant_baseline_operator'],design['conventional_logamp_matrix']])
            row['same_gain_invariant_baseline_row_span']=bool(np.linalg.matrix_rank(stacked,tol=1e-10)==row['gain_invariant_amplitude_rank'])
        else:row['same_gain_invariant_baseline_row_span']=False if n==4 else True
        cases.append(row)
    example=four_station_example()
    passed=all(c['gain_null_maximum_residual']<1e-12 for c in cases) and example['population_means_identical'] and example['all_covariances_positive_definite'] and np.max(abs(np.asarray(example['conventional_logamp_difference'])))>.5
    q={'type':'population_bispectrum_gain_validation','state':'complete' if passed else 'failed_validation',
        'cases':cases,'four_station_example':example,'observed_statistic_logarithms_taken':False,
        'extra_station_powers_or_higher_moments_used_as_constraints':False,'noise_likelihood_implemented':False,
        'physical_adc_vdif_processed':False,'real_hardware_validation_performed':False,'production_rml_noise_model_changed':False,
        'scope':'Population-mean, complete nonzero baseline topology, freely unknown station gain amplitudes per cell. No noisy observed ratios, array layout, detectability, image uniqueness, or recommendation for a minimum practical station count.'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');plot(q,out/'bispectrum-gain.png')
    if not passed:raise RuntimeError('population gain design validation failed')
    return q


def plot(result,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cases=result['cases'];n=[c['stations'] for c in cases]
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    axes[0].plot(n,[c['triangle_count'] for c in cases],marker='o',label='All triangle means')
    axes[0].plot(n,[c['gain_invariant_amplitude_rank'] for c in cases],marker='o',label='Triangle amplitude constraints')
    axes[0].plot(n,[c['conventional_logamp_rank'] for c in cases],marker='x',linestyle='--',label='Conventional closure amplitudes')
    axes[0].plot(n,[c['closure_phase_rank'] for c in cases],marker='.',label='Closure phases')
    axes[0].set(xlabel='Stations: complete nonzero baseline set',ylabel='Algebraic rank / raw row count',xticks=n);axes[0].legend(fontsize=8)
    axes[1].bar(n,[c['left_null_weight_rows'] for c in cases],label='Gain-null rows')
    axes[1].bar(n,[c['gain_invariant_amplitude_rank'] for c in cases],label='Nontrivial amplitude rank')
    axes[1].set(xlabel='Stations',ylabel='Rows vs nontrivial rank',xticks=n);axes[1].legend(fontsize=8)
    fig.suptitle('Unknown station amplitudes: constraints of population bispectrum means only\nNo noisy logs, full likelihood, geometry, hardware or image feasibility',fontsize=10)
    fig.tight_layout(rect=(0,0,1,.88));fig.savefig(path,dpi=140);plt.close(fig)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);result=run(**vars(p.parse_args()))
    print(json.dumps({'state':result['state'],'cases':len(result['cases'])}))
