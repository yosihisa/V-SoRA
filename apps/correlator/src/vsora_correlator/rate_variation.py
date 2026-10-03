"""Four-part rate consistency; not a proof of phase coherence stability."""
from itertools import combinations
import numpy as np
from .rate import estimate_station_rates,validate_pilot_arrays


def diagnose_rate_variation(data,reference_station=0,max_rate_hz=100.,threshold_sigma=6.):
    v,w,t,pairs,dt=validate_pilot_arrays(data)
    if (not np.isfinite(max_rate_hz) or not 0<max_rate_hz<.5/dt[0]
            or not np.isfinite(threshold_sigma) or threshold_sigma<=0):raise ValueError('valid rate search and positive diagnostic threshold required')
    stations=sorted(set(pairs.ravel().tolist()))
    if reference_station not in stations:raise ValueError('reference station not present')
    result={'schema_version':1,'type':'subpilot_rate_consistency','state':'unverified',
        'parts':4,'station_indices':stations,'reference_station':reference_station,
        'threshold_sigma':threshold_sigma,'subpilots':[],'maximum_normalized_rate_difference':None,
        'absolute_common_rate_measured':False,'coherence_stability_measured':False,
        'limits':'Four constant-rate fits, >=8 times each. Fisher Gaussian independent-noise approximation. 6-sigma difference is a diagnostic rule, not calibrated false-alarm probability. Within-part phase oscillation, aliasing, stable sky/gain failure or weak data may be missed; consistency does not prove coherence.'}
    if len(t)<32:
        result['reason']='not enough times for four parts with eight samples';return result
    for index,indices in enumerate(np.array_split(np.arange(len(t)),4)):
        sliced={'visibilities':v[indices],'weights':w[indices],'times_s':t[indices],'pairs':pairs}
        part={'part_index':index,'times':len(indices),'start_s':float(t[indices[0]]-dt[0]/2),
              'end_s':float(t[indices[-1]]+dt[0]/2)}
        try:
            fit=estimate_station_rates(sliced,reference_station,max_rate_hz)
            part.update(state='complete',time_reference_s=fit['time_reference_s'],
                station_rates_hz=fit['station_rates_hz'],station_covariance_hz2=fit['station_covariance_hz2'],
                covariance_station_order=fit['covariance_station_order'],accepted_baselines=fit['accepted_baselines'])
        except ValueError as exc:
            if not any(s in str(exc) for s in ('rate graph is disconnected','rate estimates inconsistent')):raise
            part.update(state='unverified',reason='insufficient or inconsistent subpilot rate graph')
        result['subpilots'].append(part)
    if any(p['state']!='complete' for p in result['subpilots']):
        result['reason']='one or more subpilots have no valid connected rate solution';return result
    maximum=0.;worst=None;unknown=[s for s in stations if s!=reference_station]
    for first,second in combinations(result['subpilots'],2):
        order=first['covariance_station_order']
        if order!=unknown or second['covariance_station_order']!=order:raise ValueError('subpilot covariance station order differs')
        variance=np.diag(np.array(first['station_covariance_hz2'])+np.array(second['station_covariance_hz2']))
        if not np.isfinite(variance).all() or np.any(variance<=0):raise ValueError('invalid subpilot rate covariance')
        for index,station in enumerate(unknown):
            k=stations.index(station);difference=second['station_rates_hz'][k]-first['station_rates_hz'][k]
            sigma=float(np.sqrt(variance[index]));z=abs(difference)/sigma
            if worst is None or z>maximum:
                maximum=float(z);worst={'first_part':first['part_index'],'second_part':second['part_index'],
                    'station_index':station,'difference_hz':difference,'nominal_sigma_hz':sigma,'normalized_difference':float(z)}
    result.update(state='variation_detected' if maximum>threshold_sigma else 'consistent',
                  maximum_normalized_rate_difference=maximum,worst_difference=worst)
    return result


def diagnose_rate_shard(path,max_rate_hz=100.):
    import hashlib
    from vsora_formats.spectral import load_spectral
    d=load_spectral(path);meta=d['metadata']
    if not meta.get('phase_center_corrected') or not meta.get('clock_mapping_applied'):
        raise ValueError('rate diagnosis requires sample and phase-center alignment')
    if not meta.get('time_origin_utc'):raise ValueError('pilot UTC origin required')
    result=diagnose_rate_variation(d,max_rate_hz=max_rate_hz)
    result.update(station_ids=[s['id'] for s in meta['config']['stations']],time_origin_utc=meta['time_origin_utc'])
    with open(path,'rb') as stream:result['input_sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
    return result


def main():
    import argparse
    import json
    from pathlib import Path
    p=argparse.ArgumentParser(description='Four-part aligned-pilot rate diagnosis; no phase stability guarantee')
    p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--max-rate-hz',type=float,default=100.)
    a=p.parse_args();out=Path(a.output)
    if out.exists():raise FileExistsError('choose a new rate diagnosis output')
    result=diagnose_rate_shard(a.input,a.max_rate_hz);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
