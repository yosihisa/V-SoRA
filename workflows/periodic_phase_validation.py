"""Periodic phase, physical IQ/VDIF, unknown sky/gain rate processing."""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.integrate import quad
from vsora_correlator.closure_pipeline import process_closure_session
from vsora_formats.spectral import load_spectral
from workflows.vdif_closure_validation import make_fixture
from workflows.rate_drift_validation import closure_metrics


def predicted_coherence(amplitude,frequency,rate=0.,slope=0.,start=.002,duration=3.,epoch=1.502):
    def phase(t):return amplitude*np.cos(2*np.pi*frequency*t)-2*np.pi*(rate*(t-epoch)+.5*slope*(t-epoch)**2)
    real=quad(lambda t:np.cos(phase(t)),start,start+duration,epsabs=1e-9,limit=2000)[0]
    imaginary=quad(lambda t:np.sin(phase(t)),start,start+duration,epsabs=1e-9,limit=2000)[0]
    return complex(real,imaginary)/duration


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);amplitudes=np.array([0.,.2,-.3,.5]);generating={};rows=[]
    for case,freq,amps in [('control',0.,np.zeros(4)),('fast',32.,amplitudes),('slow',.5,amplitudes)]:
        generating[case]=make_fixture(out/(case+'-input'),seed=35,frame_count=1530,rates_hz=[0.,0.,0.,0.],
            phase_modulation_hz=freq,phase_modulation_amplitudes_rad=amps.tolist())
    control=None
    for case,model in [('control','constant'),('fast','constant'),('fast','linear'),('slow','linear')]:
        label=case+'-'+model;row={'case':case,'rate_model':model,'integration_s':3.}
        try:
            q=process_closure_session(out/(case+'-input')/'manifest.json',out/(case+'-input')/'clock.json',out/label,
                pilot_integrations=1500,integration_s=3.,correlation_only=True,rate_model=model)
        except ValueError as exc:
            if not any(s in str(exc) for s in ('rate estimates inconsistent','rate graph is disconnected',
                    'four verified subpilot','inconsistent with a linear rate model','curvature too large')):raise
            failure=json.loads((out/(label+'.partial')/'failure.json').read_text())
            row.update(state='incomplete',reason=str(exc),completed_steps=failure['completed_steps'],
                diagnosis=failure.get('rate_consistency'));rows.append(row);continue
        d=load_spectral(out/label/'correlation/shard-00000.npz')
        if case=='control':control=d
        assert control is not None
        r=np.array(q['rate_estimate']['station_rates_hz']);a=np.array(q['rate_estimate'].get('station_rate_slopes_hz_per_s',np.zeros(4)))
        g=generating[case];amp=np.array(g['phase_modulation_amplitudes_rad']);f=g['phase_modulation_hz']
        prediction=np.array([predicted_coherence(amp[i]-amp[j],f,r[i]-r[j],a[i]-a[j],epoch=q['rate_estimate']['time_reference_s'])
                            for i,j in d['pairs']])
        valid=(d['weights'][0]>0)&(control['weights'][0]>0)
        ratio=np.sum(np.where(valid,abs(d['visibilities'][0]),0),axis=0)/np.sum(np.where(valid,abs(control['visibilities'][0]),0),axis=0)
        assert np.max(abs(ratio-abs(prediction)))<.05
        row.update(state='complete',diagnosis=q['rate_consistency'],rate_estimate=q['rate_estimate'],
            measured_amplitude_ratio_to_same_noise_control=ratio.tolist(),calculated_coherence=abs(prediction).tolist(),
            maximum_amplitude_ratio_minus_calculated_coherence=float(np.max(abs(ratio-abs(prediction)))),
            closures=closure_metrics(d,prediction))
        rows.append(row)
    assert rows[0]['state']=='complete'
    summary={'type':'periodic_phase_validation','generating':generating,'cases':rows,
        'truth_in_fit':False,'actual_hardware_data':False,
        'scope':'Deterministic assumed periodic phase on matched point/noise physical IQ -> VDIF. Nominal linear sample clocks, one seed, fixed unknown gains, no real OCXO phase-noise spectrum or Cas A image fidelity. Model consistency is not measured coherence. Controls and analytic ratios are validation-only quantities.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');plot(summary,out);return summary


def plot(summary,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,3.8))
    for row in summary['cases']:
        if row['case']=='control' or row['state']!='complete':continue
        label=row['case']+' '+row['rate_model']
        axes[0].plot(np.arange(6),row['measured_amplitude_ratio_to_same_noise_control'],'o-',label=label)
        axes[0].plot(np.arange(6),row['calculated_coherence'],'x',markersize=9)
        axes[1].bar(label,row['closures']['logamp']['measured_rms'])
    axes[0].set(xlabel='Baseline index',ylabel='Amplitude / matched control',title='Periodic phase left after measured model',ylim=(.7,1.03));axes[0].legend(fontsize=7)
    axes[1].axhline(summary['cases'][0]['closures']['logamp']['measured_rms'],color='gray',linestyle=':',label='Control noise')
    axes[1].set(ylabel='Log closure amplitude RMS',title='Completion is not unbiased closure');axes[1].legend(fontsize=7)
    fig.tight_layout();fig.savefig(out/'periodic-coherence.png',dpi=140);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);q=run(**vars(p.parse_args()))
    print(json.dumps([{'case':r['case'],'model':r['rate_model'],'state':r['state'],
        'diagnosis':(r['diagnosis'] or {}).get('state'),'minimum_amplitude_ratio':min(r['measured_amplitude_ratio_to_same_noise_control']) if r['state']=='complete' else None} for r in q['cases']],indent=2))
