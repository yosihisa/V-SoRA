"""Wide constant LO offsets through dense pilots and actual VDIF; no sky input."""
import argparse
import json
from pathlib import Path
import time
import numpy as np
from vsora_correlator.closure_pipeline import process_closure_session
from vsora_correlator.rate import estimate_station_rates
from workflows.vdif_closure_validation import make_fixture


def run(output):
    out=Path(output)
    if out.exists():raise FileExistsError('new output required')
    out.mkdir(parents=True)
    generating=make_fixture(out/'input',seed=29,frame_count=530,pilot_blocks=512,
                            rates_hz=[0.,420.,-375.,810.],fft_length=8)
    start=time.perf_counter()
    pipeline=process_closure_session(out/'input/manifest.json',out/'input/clock.json',out/'pipeline',
        pilot_integrations=4096,pilot_integration_s=.00025,max_rate_hz=1500,
        integration_s=1.,starts=1,max_iterations=800)
    elapsed=time.perf_counter()-start
    error=float(abs(np.array(pipeline['rate_estimate']['station_rates_hz'])-generating['true_rates_hz']).max())
    assert error<.05
    assert pipeline['closures']['phase_valid']>0 and pipeline['closures']['logamp_valid']>0
    assert abs(pipeline['rml']['image_sum']-1)<1e-12
    pairs=np.array([(i,j) for i in range(4) for j in range(i+1,4)])
    times=(np.arange(1024)+.5)*.00025;true=np.array([0.,4100.,-4075.,8210.])
    slope=true[pairs[:,0]]-true[pairs[:,1]]
    v=np.exp(2j*np.pi*times[:,None,None]*slope[None,None,:])
    alias=estimate_station_rates({'visibilities':v,'weights':np.full(v.shape,1e4),'times_s':times,'pairs':pairs},max_rate_hz=1500)
    assert max(abs(np.array(alias['station_rates_hz'])-[0.,100.,-75.,210.]))<1e-7
    summary={'type':'dense_pilot_wide_rate_validation','generating':generating,'pipeline':pipeline,
        'maximum_rate_error_hz':error,'pipeline_elapsed_s':elapsed,
        'maximum_true_baseline_rate_hz':float(abs(np.array(generating['true_rates_hz'])[:,None]-generating['true_rates_hz']).max()),
        'alias_counterexample':{'true_rates_hz':true.tolist(),'estimated':alias,
            'scope':'Analytic temporal visibility only, unknown constant complex baseline response; not real VDIF/hardware'},
        'limits':'Four-station point, known exact sample clocks, stable LO/gain; no extended Cas A fidelity or real oscillator/RFI demonstration. SK ineligible for the short pilot is explicitly reported.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    s=run(a.output);print(json.dumps({k:s[k] for k in ('maximum_rate_error_hz','pipeline_elapsed_s','maximum_true_baseline_rate_hz')},indent=2))
