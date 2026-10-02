"""Three-second stable-rate VDIF reference; actual OCXO stability unmeasured."""
import argparse
import json
from pathlib import Path
import numpy as np
from vsora_correlator.closure_pipeline import process_closure_session
from workflows.vdif_closure_validation import make_fixture


def run(output):
    out=Path(output)
    if out.exists():raise FileExistsError('new output required')
    out.mkdir(parents=True)
    generating=make_fixture(out/'input',seed=32,frame_count=1520,pilot_blocks=256)
    result=process_closure_session(out/'input/manifest.json',out/'input/clock.json',out/'pipeline',
                pilot_integrations=750,integration_s=3.,starts=1,max_iterations=800)
    error=float(abs(np.array(result['rate_estimate']['station_rates_hz'])-np.array(generating['true_rates_hz'])).max())
    assert error<.02
    assert result['correlation']['recorded_span_s']==3.
    assert result['correlation']['geometry_segment_max_span_s']<=1.+1e-10
    assert max(result['correlation']['station_max_buffer_samples'])<4*4096
    assert result['closures']['phase_valid']>0 and result['closures']['logamp_valid']>0
    assert abs(result['rml']['image_sum']-1)<1e-12
    summary={'type':'three_second_vdif_reference','generating':generating,'pipeline':result,'maximum_rate_error_hz':error,
        'limits':'Four stations, Gaussian point source, supplied exact nominal clocks, constant LO and gain over 3 seconds. Not a measured OCXO stability limit or extended Cas A fidelity validation.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    s=run(a.output);print(json.dumps({'maximum_rate_error_hz':s['maximum_rate_error_hz'],
        'correlation':s['pipeline']['correlation'],'closures':s['pipeline']['closures']},indent=2))
