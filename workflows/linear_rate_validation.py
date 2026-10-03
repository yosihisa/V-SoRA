"""Measured smooth LO model, actual archived VDIF, matched point-noise control."""
import argparse
import json
from pathlib import Path
import numpy as np
from vsora_correlator.closure_pipeline import process_closure_session
from vsora_correlator.coherence import quadratic_coherence
from vsora_formats.spectral import load_spectral
from workflows.rate_drift_validation import closure_metrics


def run(reference_run,output):
    base=Path(reference_run);out=Path(output);out.mkdir(parents=True,exist_ok=False)
    control=load_spectral(base/'control-3s/correlation/shard-00000.npz')
    initial=np.array([0.,17.3,-11.7,26.1]);rows=[]
    for name,truth in [('control',[0.,0.,0.,0.]),('moderate',[0.,.1,-.05,.15]),('strong',[0.,1.,-.5,1.5])]:
        result=process_closure_session(base/name/'manifest.json',base/name/'clock.json',out/name,
            pilot_integrations=1500,integration_s=3.,correlation_only=True,rate_model='linear')
        q=result['rate_estimate'];data=load_spectral(out/name/'correlation/shard-00000.npz')
        a=np.array(truth)-np.array(q['station_rate_slopes_hz_per_s']);r0=np.zeros(4) if name=='control' else initial
        r=r0+np.array(truth)*q['time_reference_s']-np.array(q['station_rates_hz'])
        predicted=np.array([quadratic_coherence(a[i]-a[j],3.,r[i]-r[j]) for i,j in data['pairs']])
        valid=(data['weights'][0]>0)&(control['weights'][0]>0)
        ratio=np.sum(np.where(valid,abs(data['visibilities'][0]),0),axis=0)/np.sum(np.where(valid,abs(control['visibilities'][0]),0),axis=0)
        assert ratio.min()>.98 and np.max(abs(ratio-abs(predicted)))<.03
        row={'case':name,'state':result['state'],'rate_model':result['rate_model'],
            'rate_profile_sha256':data['metadata']['rate_only_profile_sha256'],
            'generating_rate_slopes_hz_per_s':truth,'measured_rate_model':q,
            'maximum_absolute_rate_slope_error_hz_per_s':float(np.max(abs(a))),
            'maximum_absolute_rate_error_at_reference_hz':float(np.max(abs(r))),
            'measured_amplitude_ratio_to_matched_control':ratio.tolist(),
            'calculated_residual_coherence':abs(predicted).tolist(),
            'closures':closure_metrics(data,predicted),
            'effective_exposure_s_range':[float(data['integration_s'].min()),float(data['integration_s'].max())]}
        if name!='strong':
            old=load_spectral(base/(name+'-3s')/'correlation/shard-00000.npz')
            row['constant_model_closures']=closure_metrics(old,np.ones(len(data['pairs']),complex))
        rows.append(row)
    summary={'type':'measured_linear_rate_correction_validation','actual_vdif_cases':rows,
        'truth_in_fit':False,'source_seed':35,'physical_iq_to_vdif':True,
        'scope':'Four stations, point sky, assumed fixed gains/SEFD and smooth deterministic drift, one matched noise seed, supplied nominal sample clocks. Actual hardware/Cas A fidelity and random phase noise untested; full station covariance is still an approximate independent Fisher model.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');plot(summary,out);return summary


def plot(summary,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,3.8))
    for row in summary['actual_vdif_cases']:
        if row['case']=='control':continue
        q=row['measured_rate_model'];times=[p['time_reference_s'] for p in q['rate_consistency']['subpilots']]
        for i in (1,2,3):
            y=[p['station_rates_hz'][i] for p in q['rate_consistency']['subpilots']]
            axes[0].plot(times,y,'o',label=f"{row['case']} ST{i+1}")
            axes[0].plot(times,np.array(q['station_rates_hz'])[i]+(np.array(times)-q['time_reference_s'])*q['station_rate_slopes_hz_per_s'][i],'-',linewidth=.7)
        axes[1].plot(np.arange(6),row['measured_amplitude_ratio_to_matched_control'],'o-',label=row['case'])
    axes[0].set(xlabel='Seconds from UTC origin',ylabel='Relative station rate (Hz)',title='Measured subparts and fitted smooth lines');axes[0].legend(fontsize=6,ncol=2)
    axes[1].set(xlabel='Baseline index',ylabel='Amplitude / matched zero-LO control',title='IQ corrected with measured quadratic phase',ylim=(.98,1.02));axes[1].legend(fontsize=8)
    fig.tight_layout();fig.savefig(Path(out)/'correction.png',dpi=140);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference-run',required=True);p.add_argument('--output',required=True)
    q=run(**vars(p.parse_args()));print(json.dumps([{'case':r['case'],'slope_error':r['maximum_absolute_rate_slope_error_hz_per_s'],
        'minimum_amplitude_ratio':min(r['measured_amplitude_ratio_to_matched_control']),
        'logamp_rms':r['closures']['logamp']['measured_rms']} for r in q['actual_vdif_cases']],indent=2))
