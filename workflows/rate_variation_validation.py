"""Finite synthetic-noise cases, archived pilots, and consistency policy."""
from itertools import combinations
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.special import j0
from vsora_correlator.rate_variation import diagnose_rate_variation,diagnose_rate_shard
from vsora_correlator.closure_pipeline import process_closure_session
from vsora_formats.spectral import load_spectral


def pilot(seed=0,count=128,slopes=None,noise=.1,oscillation=None):
    """Conditional complex-visibility model, not a physical sky/IQ simulator."""
    rng=np.random.default_rng(seed);t=(np.arange(count)+.5)*.004;pairs=np.array(list(combinations(range(4),2)))
    rates=np.array([0.,17.,-11.,26.]);phase=2*np.pi*t[:,None]*rates
    if slopes is not None:phase+=np.pi*t[:,None]**2*np.array(slopes)
    if oscillation is not None:phase+=np.cos(2*np.pi*4*t[:,None]/(count*.004))*np.array(oscillation)
    constant=(.7+rng.random((8,6)))*np.exp(1j*rng.uniform(-np.pi,np.pi,(8,6)))
    values=constant[None]*np.exp(1j*(phase[:,pairs[:,0]]-phase[:,pairs[:,1]]))[:,None,:]
    values+=noise*(rng.normal(size=values.shape)+1j*rng.normal(size=values.shape))
    return {'visibilities':values,'weights':np.full(values.shape,1/max(noise,.01)**2),'times_s':t,'pairs':pairs}


def run(reference_run,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);base=Path(reference_run)
    groups={}
    for kind,seeds,slopes in [('constant',range(64),None),('linear_drift',range(16),[0.,2.,-1.,3.])]:
        rows=[]
        for seed in seeds:
            q=diagnose_rate_variation(pilot(seed,slopes=slopes))
            rows.append({'seed':seed,'state':q['state'],'maximum_normalized_rate_difference':q['maximum_normalized_rate_difference']})
        groups[kind]={'counts':{s:sum(r['state']==s for r in rows) for s in ('consistent','variation_detected','unverified')},'cases':rows}
    amplitudes=np.array([0.,.2,-.3,.5]);counterexample=diagnose_rate_variation(pilot(count=256,noise=0.,oscillation=amplitudes))
    counterexample['assumed_phase_oscillation_amplitudes_rad']=amplitudes.tolist()
    counterexample['calculated_minimum_coherence']=float(j0(max(amplitudes)-min(amplitudes)))
    assert counterexample['state']=='consistent' and counterexample['calculated_minimum_coherence']<.9
    assert not counterexample['coherence_stability_measured']
    original=json.loads((base/'summary.json').read_text());archived=[]
    for row in original['actual_vdif_cases']:
        directory=base/(row['case'] if row['state']=='complete' else row['case']+'.partial')
        q=diagnose_rate_shard(directory/'pilot/shard-00000.npz')
        if row['state']=='complete':assert q['input_sha256']==row['rate_estimate']['input_sha256']
        archived.append({'case':row['case'],'diagnosis':q})
    assert next(r['diagnosis']['state'] for r in archived if r['case']=='moderate-3s')=='variation_detected'
    manifest=base/'moderate/manifest.json';clock=base/'moderate/clock.json'
    result=process_closure_session(manifest,clock,out/'report-policy',pilot_integrations=1500,integration_s=3.,correlation_only=True)
    assert result['rate_consistency']['state']=='variation_detected' and result['rate_consistency_policy']=='report'
    expected=load_spectral(base/'moderate-3s/correlation/shard-00000.npz')
    observed=load_spectral(out/'report-policy/correlation/shard-00000.npz');diffs={}
    for key,value in expected.items():
        if not isinstance(value,np.ndarray):continue
        np.testing.assert_array_equal(value,observed[key])
        if np.issubdtype(value.dtype,np.inexact):diffs[key]=float(abs(value-observed[key]).max())
    try:
        process_closure_session(manifest,clock,out/'required-policy',pilot_integrations=1500,integration_s=3.,
                                correlation_only=True,require_rate_consistency=True)
    except ValueError as exc:assert 'required subpilot rate consistency' in str(exc)
    else:raise AssertionError('required policy did not stop')
    failure=json.loads((out/'required-policy.partial/failure.json').read_text())
    assert failure['completed_steps']==['aligned_pilot'] and failure['rate_consistency']['state']=='variation_detected'
    assert not (out/'required-policy').exists() and not (out/'required-policy.partial/correlation').exists()
    summary={'type':'subpilot_rate_diagnostic_validation','threshold_sigma':6.,'mathematical_cases':groups,
        'counterexample':counterexample,'archived_vdif_pilots':archived,
        'report_policy':{'state':result['state'],'diagnosis':result['rate_consistency'],
            'maximum_absolute_reference_array_differences':diffs},
        'required_policy':failure,
        'limits':'Diagnostic comparison to approximate Gaussian Fisher noise, not calibrated false-alarm probability. Finite conditional independent-noise visibilities differ from real filtered/shared-sky covariance. Archived radio cases reuse one seed and assumed deterministic drift. Consistency misses periodic phase oscillation. No automatic phase correction or actual hardware/Cas A image fidelity claim.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference-run',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();q=run(a.reference_run,a.output)
    print(json.dumps({'mathematical_counts':{k:v['counts'] for k,v in q['mathematical_cases'].items()},
        'archived_states':[(r['case'],r['diagnosis']['state']) for r in q['archived_vdif_pilots']]},indent=2))
