"""Three stable windows with continuous phase and different unknown LO rates."""
import argparse
import json
from pathlib import Path
import numpy as np
from vsora_correlator.sequence import process_sequence
from vsora_formats.spectral import load_spectral
from workflows.vdif_closure_validation import make_fixture


RATES=[[0.,17.3,-11.7,26.1],[0.,31.2,-6.3,14.4],[0.,-20.5,13.7,4.3]]


def write_plot(summary,output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out=Path(output);q=summary['sequence']
    fig,axes=plt.subplots(1,2,figsize=(10,3.6))
    times=[w['rate_estimate']['time_reference_s'] for w in q['windows']]
    for station in range(1,4):
        color=f'C{station-1}'
        axes[0].scatter(times,[r[station] for r in summary['true_window_rates_hz']],s=45,marker='x',color=color,label=f'ST{station+1:02d} generating')
        axes[0].scatter(times,[w['rate_estimate']['station_rates_hz'][station] for w in q['windows']],s=20,facecolors='none',edgecolors=color)
    axes[0].set(title='Local LO rates, relative to ST01',xlabel='Reference time from file sample0 (s)',ylabel='Rate (Hz)');axes[0].legend(fontsize=7)
    axes[1].imshow(np.load(out/'sequence/synthesis/rml/relative-model.npy'),origin='lower',cmap='inferno')
    converged=q['rml']['runs'][q['rml']['selected_start']]['optimizer_success']
    axes[1].set_title('Relative RML; '+('optimizer stopped' if converged else 'iteration limit reached'))
    fig.tight_layout();fig.savefig(out/'rates-and-image.png',dpi=140);plt.close(fig)


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    changes=[{'start_s':.514,'rates_hz':RATES[1]},{'start_s':1.026,'rates_hz':RATES[2]}]
    generating=make_fixture(out/'input',seed=32,frame_count=800,rate_changes=changes)
    result=process_sequence(out/'input/manifest.json',out/'input/clock.json',out/'sequence',
        window_count=3,step_s=.512,integration_s=.3,starts=3,max_iterations=800)
    errors=[float(abs(np.array(w['rate_estimate']['station_rates_hz'])-true).max()) for w,true in zip(result['windows'],RATES)]
    data=load_spectral(out/'sequence/synthesis/visibility.npz')
    assert max(errors)<.05
    assert data['visibilities'].shape[0]==3 and data['metadata']['visibility_unit']=='ADC^2'
    assert np.allclose(data['integration_s'].sum(axis=0),.9,atol=1e-12)
    assert result['rml']['amplitude_constraints_available'] and abs(result['rml']['image_sum']-1)<1e-12
    summary={'type':'short_window_sequence_validation','generating':generating,'true_window_rates_hz':RATES,
        'maximum_station_rate_error_per_window_hz':errors,'sequence':result,
        'limits':'Same four-station point-noise VDIF, exact nominal sample clocks. LO changes are at configured pilot boundaries with continuous phase; this is not recovery of curvature/noise within an arbitrary window or Cas A fidelity/real hardware.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');write_plot(summary,out);return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();s=run(a.output)
    print(json.dumps({'errors_hz':s['maximum_station_rate_error_per_window_hz'],
                     'exposure_s':s['sequence']['nominal_image_exposure_per_station_s']},indent=2))
