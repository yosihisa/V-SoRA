"""Single-cell noise diagnostic, with explicit nominal iid FFT assumptions."""
import hashlib
from itertools import combinations
import json
from pathlib import Path
import numpy as np
from vsora_formats.spectral import load_spectral,validate_spectral
from vsora_simulator.visibility_noise_estimate import estimate_visibility_noise
from vsora_imaging.closure_noise import joint_closure_noise


def diagnose_noise_cell(data,time_index,channel_index):
    validate_spectral(data)
    v=np.asarray(data.get('visibilities',data.get('vis_jy')));p=np.asarray(data['pairs']);nt,nf,b=v.shape
    if (isinstance(time_index,bool) or not isinstance(time_index,(int,np.integer)) or not 0<=time_index<nt
            or isinstance(channel_index,bool) or not isinstance(channel_index,(int,np.integer)) or not 0<=channel_index<nf):
        raise ValueError('integer time/channel indices must select an existing cell')
    meta=data.get('metadata',{})
    if not isinstance(meta,dict):raise ValueError('spectral metadata must be a mapping')
    result={'type':'spectral_noise_diagnostic','time_index':int(time_index),
        'channel_index':int(channel_index),'time_s':float(data['times_s'][time_index]),
        'frequency_hz':float(data['frequencies_hz'][channel_index]),
        'iid_fft_independence_verified':False,'stationary_gaussian_model_verified':False,
        'real_hardware_validation_performed':False,'production_rml_noise_model_changed':False,
        'covariance_confidence_calibrated':False,
        'scope':'Conditional iid proper Gaussian model with nominal FFT block count. Actual independence, filtering, quantization, masks, gain variation and hardware confidence unverified.'}
    def unavailable(reason,state='unverified'):
        return {**result,'state':state,'reason':reason}
    w=data['weights'][time_index,channel_index]
    if not np.any(w>0):return unavailable('no_positive_baseline_weights','inactive')
    if not np.all(w>0):return unavailable('partial_baseline_mask')
    required=('valid_fft_count','diagnostic_station_power','diagnostic_station_valid_fft_count','diagnostic_station_flags')
    if any(k not in data for k in required):return unavailable('missing_station_power_flags_or_fft_counts')
    power=np.asarray(data['diagnostic_station_power']);counts=np.asarray(data['diagnostic_station_valid_fft_count'])
    paircounts=np.asarray(data['valid_fft_count']);flags=np.asarray(data['diagnostic_station_flags'])
    if np.iscomplexobj(power) or power.ndim!=3 or power.shape[:2]!=(nt,nf):raise ValueError('real station channel power shape differs')
    n=power.shape[2]
    if (counts.shape!=(nt,n) or paircounts.shape!=(nt,b) or flags.shape!=power.shape
            or not np.issubdtype(counts.dtype,np.integer) or not np.issubdtype(paircounts.dtype,np.integer)
            or not np.issubdtype(flags.dtype,np.integer) or np.any(counts<0) or np.any(paircounts<0)
            or not np.isfinite(power).all() or np.any(power<0)):
        raise ValueError('finite nonnegative power, integer FFT counts and station flags required')
    if not 2<=n<=8:return unavailable('station_count_outside_reference_range')
    if set(map(tuple,p.tolist()))!=set(combinations(range(n),2)):return unavailable('incomplete_baseline_set')
    identities=meta.get('config',{}).get('stations',[])
    if (len(identities)!=n or any(not isinstance(s,dict) or not isinstance(s.get('id'),str) for s in identities)
            or len({s['id'] for s in identities})!=n):return unavailable('missing_or_invalid_station_identity')
    unit=meta.get('visibility_unit')
    if unit not in ('ADC^2','Jy') or meta.get('diagnostic_power_unit')!=unit:return unavailable('power_visibility_units_differ_or_missing')
    if np.any(flags[time_index,channel_index]!=0):return unavailable('station_quality_flag')
    m=int(counts[time_index,0])
    if m<n:return unavailable('insufficient_common_fft_blocks')
    if m>2**53:return unavailable('unsupported_fft_count')
    if not np.all(counts[time_index]==m) or not np.all(paircounts[time_index]==m):
        return unavailable('station_and_baseline_fft_sets_differ')
    s=np.diag(power[time_index,channel_index]).astype(complex)
    s[p[:,0],p[:,1]]=v[time_index,channel_index];s[p[:,1],p[:,0]]=v[time_index,channel_index].conj()
    try:q=estimate_visibility_noise(s,m,p)
    except ValueError:return unavailable('invalid_station_sample_covariance')
    try:closure=joint_closure_noise(q['mean'],q['real_covariance'],p)
    except ValueError:return unavailable('closure_noise_outside_numerical_range')
    if not np.isfinite(closure['baseline_snr']).all():return unavailable('noise_snr_outside_numerical_range')
    return {**result,'state':'conditional_estimate','station_ids':[station['id'] for station in identities],
        'nominal_common_fft_blocks':m,'visibility_unit':unit,'covariance_unit':'ADC^4' if unit=='ADC^2' else 'Jy^2',
        'station_sample_covariance_real':s.real.tolist(),'station_sample_covariance_imag':s.imag.tolist(),
        'real_parameter_order':q['real_parameter_order'],'estimated_visibility_covariance':q['real_covariance'].tolist(),
        'baseline_snr_conditional':closure['baseline_snr'].tolist(),'closure_joint_parameter_order':closure['joint_parameter_order'],
        'closure_joint_valid':closure['joint_valid'].tolist(),'estimated_joint_closure_covariance':closure['joint_covariance'].tolist(),
        'phase_count':closure['phase_count'],'logamp_count':closure['logamp_count'],
        'visibility_covariance_ensemble_unbiased_only_if_assumptions_hold':True,
        'closure_covariance_first_order_not_unbiased_guarantee':True,'generating_truth_used':False}


def diagnose_noise_file(input,output,channel_index,time_index=0):
    source=Path(input);out=Path(output)
    if out.suffix!='.json':raise ValueError('noise diagnostic output must be JSON')
    if out.exists():raise FileExistsError('noise diagnostic already exists')
    before=source.stat()
    with source.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
    data=load_spectral(source);after=source.stat()
    if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
        raise ValueError('input changed during diagnostic; use a closed archive')
    q={**diagnose_noise_cell(data,time_index,channel_index),'input_sha256':sha}
    encoded=json.dumps(q,indent=2,allow_nan=False)+'\n';out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as stream:stream.write(encoded)
    return q


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Conditional one-cell visibility/Closure noise from station moments')
    parser.add_argument('--input',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--time-index',type=int,default=0);parser.add_argument('--channel-index',type=int,required=True)
    q=diagnose_noise_file(**vars(parser.parse_args()))
    print(json.dumps({k:q[k] for k in ('state','time_index','channel_index','frequency_hz')},indent=2))


if __name__=='__main__':main()
