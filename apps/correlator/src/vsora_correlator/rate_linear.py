"""Measured four-part relative rates -> smooth linear rate / quadratic phase.

Approximate Gaussian Fisher covariance, stable sky/gain. Does not recover
arbitrary phase noise, common rate, aliases or subpart oscillations.
"""
import numpy as np
from .coherence import quadratic_coherence
from .rate import validate_rate_profile
from .rate_variation import diagnose_rate_variation


def fit_linear_parts(diagnosis,max_rate_hz=100.,max_reduced_chisq=3.):
    if (not np.isfinite(max_rate_hz) or max_rate_hz<=0 or
            not np.isfinite(max_reduced_chisq) or max_reduced_chisq<=0):
        raise ValueError('positive finite linear rate limits required')
    parts=diagnosis.get('subpilots',[])
    stations=diagnosis.get('station_indices',[]);reference=diagnosis.get('reference_station')
    if len(parts)!=4 or any(p.get('state')!='complete' for p in parts):
        raise ValueError('linear rate needs four verified subpilot solutions')
    unknown=[s for s in stations if s!=reference];n=len(unknown)
    if not n or reference not in stations:raise ValueError('invalid linear rate stations')
    t=np.array([p['time_reference_s'] for p in parts],float)
    bounds=np.array([[p['start_s'],p['end_s']] for p in parts],float)
    if (not np.isfinite(t).all() or not np.isfinite(bounds).all() or np.any(np.diff(t)<=0)
            or np.any(bounds[:,0]>=t) or np.any(bounds[:,1]<=t)
            or np.any(bounds[1:,0]<bounds[:-1,1]-1e-9)):
        raise ValueError('invalid linear subpilot times')
    epoch=float((bounds[0,0]+bounds[-1,1])/2);matrix=[];values=[]
    for p,tau in zip(parts,t-epoch):
        if p['covariance_station_order']!=unknown:raise ValueError('linear covariance station order differs')
        c=np.array(p['station_covariance_hz2'],float);rates=np.array(p['station_rates_hz'],float)
        if (c.shape!=(n,n) or rates.shape!=(len(stations),) or not np.isfinite(c).all()
                or not np.isfinite(rates).all() or not np.allclose(c,c.T,rtol=1e-8,atol=1e-12)):
            raise ValueError('invalid linear rate covariance/values')
        try:l=np.linalg.cholesky(c)
        except np.linalg.LinAlgError as exc:raise ValueError('linear rate covariance must be positive definite') from exc
        matrix.append(np.linalg.solve(l,np.concatenate([np.eye(n),tau*np.eye(n)],axis=1)))
        values.append(np.linalg.solve(l,rates[[stations.index(s) for s in unknown]]-rates[stations.index(reference)]))
    a=np.concatenate(matrix);y=np.concatenate(values);parameters=np.linalg.lstsq(a,y,rcond=None)[0]
    residual=a @ parameters-y;degrees=len(y)-len(parameters);reduced=float(residual @ residual/degrees)
    if reduced>max_reduced_chisq:raise ValueError('subpilot rates inconsistent with a linear rate model')
    covariance=np.linalg.inv(a.T @ a)
    rates=np.array([0. if s==reference else parameters[unknown.index(s)] for s in stations])
    slopes=np.array([0. if s==reference else parameters[n+unknown.index(s)] for s in stations])
    endpoint=rates[None,:]+(bounds[[0,-1],[0,1]]-epoch)[:,None]*slopes[None,:]
    if np.max(abs(endpoint[:,:,None]-endpoint[:,None,:]))>=max_rate_hz:
        raise ValueError('linear rate endpoints outside supplied baseline rate bound')
    part_coherence=[abs(quadratic_coherence(float(slopes[i]-slopes[j]),float(end-start)))
                    for start,end in bounds for i in range(len(stations)) for j in range(i+1,len(stations))]
    if min(part_coherence)<.9:raise ValueError('linear rate curvature too large within subpilot; use shorter subpilots')
    return {'schema_version':1,'type':'station_rate_linear','station_indices':stations,
        'station_rates_hz':rates.tolist(),'station_rate_slopes_hz_per_s':slopes.tolist(),
        'reference_station':reference,'time_reference_s':epoch,
        'parameter_covariance':covariance.tolist(),'covariance_station_order':unknown,
        'parameter_order':'relative rates Hz, then relative rate slopes Hz/s',
        'linear_model_reduced_chisq':reduced,'linear_model_degrees_of_freedom':degrees,
        'linear_model_max_reduced_chisq':max_reduced_chisq,
        'minimum_calculated_centered_subpilot_coherence':float(min(part_coherence)),
        'absolute_common_rate_measured':False,'coherence_stability_measured':False,
        'model':'Four independent local constant-rate estimates, full station covariance; weighted smooth linear rate',
        'limits':'Approximate independent Gaussian Fisher errors, stable sky/gain. Linear adequacy is not phase stability. Subpart oscillation, alias and common drift remain invisible; no actual OCXO or low-SNR guarantee.'}


def estimate_linear_rates(data,max_rate_hz=100.,reference_station=0):
    diagnosis=diagnose_rate_variation(data,reference_station,max_rate_hz)
    result=fit_linear_parts(diagnosis,max_rate_hz)
    t=np.asarray(data['times_s']);dt=float(t[1]-t[0])
    result.update(valid_time_range_s=[float(t[0]),float(t[-1])],sample_cadence_s=dt,
        temporal_nyquist_hz=.5/dt,max_baseline_rate_hz=max_rate_hz,
        initial_baseline_rate_bound_externally_required=True,rate_consistency=diagnosis)
    return result


def estimate_linear_shard(path,max_rate_hz=100.):
    import hashlib
    from vsora_formats.spectral import load_spectral
    d=load_spectral(path);meta=d['metadata']
    if not meta.get('phase_center_corrected') or not meta.get('clock_mapping_applied') or not meta.get('time_origin_utc'):
        raise ValueError('linear rate requires aligned pilot and UTC origin')
    if np.any(np.asarray(meta.get('rate_applied_hz',[]))!=0) or np.any(np.asarray(meta.get('rate_applied_slopes_hz_per_s',[]))!=0):
        raise ValueError('linear rate estimation requires an uncorrected LO pilot')
    result=estimate_linear_rates(d,max_rate_hz)
    result.update(station_ids=[s['id'] for s in meta['config']['stations']],time_origin_utc=meta['time_origin_utc'])
    with open(path,'rb') as stream:result['input_sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
    return result


def validate_linear_profile(profile,station_ids,origin,start_s,end_s,allow_extrapolation=False):
    if allow_extrapolation:raise ValueError('linear rate extrapolation is not supported')
    if profile.get('type')!='station_rate_linear':raise ValueError('linear rate profile type required')
    rates,epoch=validate_rate_profile({**profile,'type':'station_rate_only'},station_ids,origin,start_s,end_s)
    slopes=np.asarray(profile.get('station_rate_slopes_hz_per_s'),float)
    if slopes.shape!=rates.shape or not np.isfinite(slopes).all():raise ValueError('invalid linear rate slopes')
    bound=profile.get('max_baseline_rate_hz');nyquist=profile.get('temporal_nyquist_hz')
    if (not isinstance(bound,(int,float)) or isinstance(bound,bool) or not np.isfinite(bound)
            or not isinstance(nyquist,(int,float)) or isinstance(nyquist,bool) or not np.isfinite(nyquist)
            or not 0<bound<nyquist or not np.isclose(nyquist,.5/profile['sample_cadence_s'])):
        raise ValueError('invalid linear rate bound/Nyquist')
    edge=rates[None,:]+(np.array([start_s,end_s])-epoch)[:,None]*slopes[None,:]
    if np.max(abs(edge[:,:,None]-edge[:,None,:]))>=bound:raise ValueError('linear rate correction outside baseline bound')
    return rates,slopes,epoch


def main():
    import argparse,json
    from pathlib import Path
    p=argparse.ArgumentParser(description='Estimate smooth linear relative station rate from four pilot parts')
    p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--max-rate-hz',type=float,default=100.)
    a=p.parse_args();out=Path(a.output)
    if out.exists():raise FileExistsError('choose a new linear rate output')
    result=estimate_linear_shard(a.input,a.max_rate_hz);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
