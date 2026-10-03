"""Short sequence with measured per-window smooth LO models."""
import argparse
import json
from pathlib import Path
import numpy as np
from vsora_correlator.sequence import process_sequence
from workflows.vdif_closure_validation import make_fixture


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);slopes=np.array([0.,1.,-.5,1.5]);rates=np.array([0.,17.3,-11.7,26.1])
    make_fixture(out/'input',seed=38,frame_count=800,rate_slopes_hz_per_s=slopes.tolist())
    result=process_sequence(out/'input/manifest.json',out/'input/clock.json',out/'sequence',rate_model='linear',
        window_count=3,starts=1,max_iterations=100)
    models=[]
    for row in result['windows']:
        q=row['rate_estimate'];assert q['type']=='station_rate_linear'
        models.append({'window_index':row['window_index'],'model':q,
            'maximum_rate_slope_error_hz_per_s':float(np.max(abs(np.array(q['station_rate_slopes_hz_per_s'])-slopes))),
            'maximum_rate_error_hz':float(np.max(abs(np.array(q['station_rates_hz'])-(rates+slopes*q['time_reference_s']))))})
    summary={'type':'linear_sequence_protocol_validation','state':result['state'],'rate_model':result['rate_model'],
        'window_models':models,'nominal_image_exposure_per_station_s':result['nominal_image_exposure_per_station_s'],
        'input_identity':result['input_identity'],'rml':result['rml'],
        'scope':'Actual synthetic point-noise VDIF, deterministic assumed smooth LO, four stations, seed38, supplied nominal clocks. One RML start100 iterations for protocol; no Cas A fidelity or hardware performance claim.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    q=run(**vars(p.parse_args()));print(json.dumps({'state':q['state'],'models':[(r['maximum_rate_error_hz'],r['maximum_rate_slope_error_hz_per_s']) for r in q['window_models']]},indent=2))
