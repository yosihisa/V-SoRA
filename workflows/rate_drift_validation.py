"""Deterministic rate curvature, actual VDIF, and post-integration closures."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from vsora_correlator.coherence import quadratic_coherence,centered_drift_limit
from vsora_correlator.closure_pipeline import process_closure_session
from vsora_correlator.rate import estimate_station_rates
from vsora_formats.spectral import load_spectral
from vsora_imaging.closure import form_closures
from workflows.vdif_closure_validation import make_fixture


def closure_metrics(data,predicted):
    measured=form_closures(data['visibilities'],data['weights'],data['pairs'],min_snr=10)
    model=form_closures(predicted[None,None,:],np.full((1,1,len(predicted)),1e12),data['pairs'],min_snr=10)
    result={}
    for key in ('phase','logamp'):
        valid=measured[key+'_valid'];expected=np.broadcast_to(model[key],measured[key].shape)
        residual=measured[key]-expected
        if key=='phase':residual=np.angle(np.exp(1j*residual))
        result[key]={'valid_count':int(valid.sum()),
            'measured_rms':float(np.sqrt(np.mean(measured[key][valid]**2))) if valid.any() else None,
            'predicted_rms':float(np.sqrt(np.mean(model[key]**2))),
            'rms_difference_from_predicted':float(np.sqrt(np.mean(residual[valid]**2))) if valid.any() else None}
    return result


def run(output,seed=35):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    initial=np.array([0.,17.3,-11.7,26.1]);slopes={'control':np.zeros(4),
        'moderate':np.array([0.,.1,-.05,.15]),'strong':np.array([0.,1.,-.5,1.5])}
    generating={}
    for name,a in slopes.items():
        generating[name]=make_fixture(out/name,seed=seed,frame_count=1530,
            rates_hz=np.zeros(4) if name=='control' else initial,rate_slopes_hz_per_s=a.tolist())
    configurations=[('control-3s','control',3.,1500),('control-short','control',.3,256),
                    ('moderate-3s','moderate',3.,1500),('strong-3s','strong',3.,1500),('strong-short','strong',.3,256)]
    results=[];references={}
    for label,name,integration,count in configurations:
        row={'case':label,'integration_s':integration,'pilot_span_s':count*.002,
             'generating_rate_slopes_hz_per_s':slopes[name].tolist()}
        try:
            q=process_closure_session(out/name/'manifest.json',out/name/'clock.json',out/label,
                integration_s=integration,pilot_integrations=count,correlation_only=True)
        except ValueError as exc:
            if not any(s in str(exc) for s in ('rate estimates inconsistent','rate graph is disconnected')):raise
            failure=json.loads((out/(label+'.partial')/'failure.json').read_text())
            row.update(state='incomplete',reason=str(exc),completed_steps=failure['completed_steps'])
            results.append(row);continue
        data=load_spectral(out/label/'correlation/shard-00000.npz')
        a=slopes[name];r0=np.zeros(4) if name=='control' else initial
        estimate=np.array(q['rate_estimate']['station_rates_hz']);mid=.002+integration/2
        residual_at_mid=r0+a*mid-estimate
        predicted=np.array([quadratic_coherence(a[i]-a[j],integration,residual_at_mid[i]-residual_at_mid[j])
                            for i,j in data['pairs']])
        if name=='control':references[integration]=data
        ref=references[integration];valid=(data['weights'][0]>0)&(ref['weights'][0]>0)
        ratio=np.sum(np.where(valid,abs(data['visibilities'][0]),0),axis=0)/np.sum(np.where(valid,abs(ref['visibilities'][0]),0),axis=0)
        difference=float(abs(ratio-abs(predicted)).max())
        row.update(state='complete',completed_steps=q['completed_steps'],estimated_station_rates_hz=estimate.tolist(),
            rate_reference_s=q['rate_estimate']['time_reference_s'],
            true_station_rates_at_pilot_reference_hz=(r0+a*q['rate_estimate']['time_reference_s']).tolist(),
            baseline_pairs=data['pairs'].tolist(),measured_amplitude_ratio_to_same_noise_control=ratio.tolist(),
            calculated_coherence_for_estimated_rates=abs(predicted).tolist(),
            maximum_amplitude_ratio_minus_calculated_coherence=difference,
            closures=closure_metrics(data,predicted),rate_estimate=q['rate_estimate'],
            limits='Control uses matched seed/common sky/noise and zero LO. Quantization/filter/channelization differ; ratios are validation diagnostics, unavailable for unknown real sky.')
        assert difference<.06,(label,difference)
        results.append(row)
    assert all(r['state']=='complete' for r in results if r['case'].startswith('control'))
    analytic=[{'integration_s':t,'baseline_rate_slope_hz_per_s':a,
               'best_centered_coherence':float(abs(quadratic_coherence(a,t)))}
              for t in (.1,.3,1.,3.) for a in (.01,.1,1.,10.)]
    limits=[{'integration_s':t,'baseline_drift_hz_per_s_at_90pct_centered_coherence':centered_drift_limit(t)}
            for t in (.1,.3,1.,3.)]
    summary={'type':'within_window_rate_drift_validation','seed':seed,'generating':generating,
        'phase_model_cycles':'r0*t + 0.5*a*t^2; r0 Hz, a Hz/s; supplied exact nominal sample clocks',
        'analytic_centered_cases':analytic,'analytic_centered_limits':limits,'actual_vdif_cases':results,
        'references':[{'title':'HOPS4 fringe-fitting algorithm','url':'https://mithaystack.github.io/HOPS/hops4/data_processing/algorithm_and_output/algorithm.html'},
            {'title':'Blackburn et al., Closure statistics in interferometric data','url':'https://arxiv.org/abs/1910.02062'},
            {'title':'Cappallo, fourfit file-based phase corrections','url':'https://www.haystack.mit.edu/wp-content/uploads/2020/07/docs_hops_012_fourfit_phase_by_file.pdf'}],
        'limits':'Deterministic assumed linear LO drift, point sky, one matched seed, fixed gains. Drift truth used only for generating/comparing, never in the rate fit. No actual OCXO stability, stochastic phase noise, Cas A fidelity, automatic curvature recovery or low-SNR likelihood validation. Longer integration trades coherence against thermal sensitivity.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');write_plot(summary,out);diagnose_pilots(out);return summary


def diagnose_pilots(output):
    """Exploratory four-part fits of already saved pilots; no new IQ run."""
    out=Path(output);summary=json.loads((out/'summary.json').read_text());records=[]
    for row in summary['actual_vdif_cases']:
        directory=out/(row['case'] if row['state']=='complete' else row['case']+'.partial')
        path=directory/'pilot/shard-00000.npz';data=load_spectral(path);parts=[]
        with path.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
        if row['state']=='complete':assert sha==row['rate_estimate']['input_sha256']
        for indices in np.array_split(np.arange(len(data['times_s'])),4):
            sliced={k:data[k][indices] for k in ('visibilities','weights','times_s')};sliced['pairs']=data['pairs']
            try:
                fit=estimate_station_rates(sliced)
                parts.append({'state':'complete','time_reference_s':fit['time_reference_s'],
                    'station_rates_hz':fit['station_rates_hz'],'station_covariance_hz2':fit['station_covariance_hz2'],
                    'covariance_station_order':fit['covariance_station_order'],'accepted_baselines':fit['accepted_baselines']})
            except ValueError as exc:
                if not any(s in str(exc) for s in ('rate estimates inconsistent','rate graph is disconnected')):raise
                parts.append({'state':'incomplete','reason':str(exc)})
        records.append({'case':row['case'],'pilot_sha256':sha,'four_part_fits':parts})
    result={'type':'exploratory_subpilot_rate_fits','cases':records,
        'scope':'Reuses frozen pilot arrays and records their SHA. Independent constant-rate fit to each of four time parts, no curvature correction or calibrated significance classifier. The same high-SNR noise/sky assumptions apply.'}
    (out/'subpilot.json').write_text(json.dumps(result,indent=2)+'\n');return result


def write_plot(summary,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,3.9));times=np.linspace(.05,3.,150)
    for a in (.01,.1,1.,10.):
        axes[0].plot(times,[abs(quadratic_coherence(a,t)) for t in times],label=f'{a:g} Hz/s')
    axes[0].axhline(.9,color='gray',linestyle=':');axes[0].set(xlabel='Integration (s)',ylabel='Calculated coherence',
        title='Smooth drift; linear rate centered on image',ylim=(0,1.03));axes[0].legend(fontsize=8)
    cases=[r for r in summary['actual_vdif_cases'] if not r['case'].startswith('control') and r['state']=='complete']
    for index,row in enumerate(cases):
        x=np.arange(6)+index*7
        axes[1].plot(x,row['calculated_coherence_for_estimated_rates'],'x',label=row['case']+' calculated')
        axes[1].plot(x,row['measured_amplitude_ratio_to_same_noise_control'],'o',fillstyle='none',label=row['case']+' VDIF')
    axes[1].set(xlabel='Baseline groups',ylabel='Amplitude / matched control',title='Actual constant-rate correction')
    axes[1].legend(fontsize=7);fig.tight_layout();fig.savefig(Path(out)/'coherence.png',dpi=140);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--seed',type=int,default=35)
    p.add_argument('--diagnose-only',action='store_true',help='Fit four parts of existing saved pilots, no IQ rerun')
    a=p.parse_args()
    if a.diagnose_only:
        q=diagnose_pilots(a.output);print(json.dumps(q,indent=2));raise SystemExit(0)
    q=run(a.output,a.seed);print(json.dumps([{'case':r['case'],'state':r['state'],
        'min_coherence':min(r['calculated_coherence_for_estimated_rates']) if r['state']=='complete' else None}
        for r in q['actual_vdif_cases']],indent=2))
