"""Passive time-scatter diagnostic under nominal iid FFT and time-cell noise.

P_time estimates mean |mu_t|^2; P_mean estimates |mean mu_t|^2 only when
noise cells are independent and rotations fixed independently of the data.
Their ratio is a noisy unbounded statistic, not measured hardware coherence.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
from vsora_formats.spectral import load_spectral, validate_spectral
from .noise_diagnostics import diagnose_noise_cell
from .rate import validate_rate_profile
from .rate_linear import validate_linear_profile


def time_power_moments(visibilities, complex_noise_variances):
    """Time-average powers, conditional on independent zero-mean cell errors.

    No phase fitting occurs here. Unbiased powers under fixed rotations do
    not make their ratio unbiased or constrain it to a physical interval.
    """
    z=np.asarray(visibilities);nu=np.asarray(complex_noise_variances)
    if (z.ndim!=2 or nu.shape!=z.shape or not np.iscomplexobj(z) or np.iscomplexobj(nu)
            or not 32<=len(z)<=8192 or not np.isfinite(z).all() or not np.isfinite(nu).all() or np.any(nu<0)):
        raise ValueError('complex time/baseline values and finite nonnegative real noise variance, 32..8192 cells required')
    nt=len(z)
    with np.errstate(over='ignore',invalid='ignore'):
        mean=z.mean(axis=0);raw_time=np.mean(abs(z)**2,axis=0);raw_mean=abs(mean)**2
        mean_noise=nu.mean(axis=0);noise_of_mean=nu.sum(axis=0)/nt**2
        time_power=raw_time-mean_noise;mean_power=raw_mean-noise_of_mean;excess=time_power-mean_power
    values={'mean':mean,'raw_time':raw_time,'raw_mean':raw_mean,'mean_noise':mean_noise,
        'noise_of_mean':noise_of_mean,'time_power':time_power,'mean_power':mean_power,'excess':excess}
    if not all(np.isfinite(a).all() for a in values.values()):raise ValueError('time power exceeds finite numerical range')
    return values


def diagnose_time_scatter(data, channel_index, rate_profile=None):
    validate_spectral(data)
    v=np.asarray(data.get('visibilities',data.get('vis_jy')))
    nt,nf,b=v.shape;meta=data.get('metadata',{})
    if (isinstance(channel_index,bool) or not isinstance(channel_index,(int,np.integer))
            or not 0<=channel_index<nf):raise ValueError('integer channel index must select an existing channel')
    if not isinstance(meta,dict):raise ValueError('spectral metadata must be a mapping')
    result={'type':'pilot_time_scatter','channel_index':int(channel_index),
        'frequency_hz':float(data['frequencies_hz'][channel_index]),'time_cells':nt,
        'iid_fft_independence_verified':False,'time_cell_independence_verified':False,
        'covariance_confidence_calibrated':False,'hardware_coherence_measured':False,
        'production_rml_noise_model_changed':False,'generating_truth_used':False,
        'rate_profile_fit_dependence_calibrated':False,
        'scope':'Conditional noise-subtracted time and mean powers under common iid proper Gaussian FFT and independent time-cell noise. Center rotations only; ratios unbounded, no hardware confidence or automatic image gate.'}
    def unavailable(reason,**extra):return {**result,'state':'unverified','reason':reason,**extra}
    if not 32<=nt<=8192:return unavailable('time_cell_count_outside_32_to_8192')
    t=np.asarray(data['times_s']);integration=np.asarray(data.get('integration_s',[]))
    if (np.iscomplexobj(integration) or integration.shape not in ((nt,),(nt,b)) or not np.isfinite(integration).all()
            or np.any(integration<=0)):raise ValueError('positive real integration per time cell required')
    if integration.ndim==2:
        if not np.all(integration==integration[:,:1]):return unavailable('baseline_exposures_differ')
        integration=integration[:,0]
    start=t-integration/2;end=t+integration/2
    if np.any(start[1:]<end[:-1]-1e-9):return unavailable('overlapping_time_cells')
    means=[];noise=[];counts=[];station_ids=None
    for index in range(nt):
        q=diagnose_noise_cell(data,index,channel_index)
        if q['state']!='conditional_estimate':
            return unavailable('ineligible_time_cell',time_index=index,cell_reason=q['reason'])
        station_ids=q['station_ids'];c=np.asarray(q['estimated_visibility_covariance'])
        noise.append(np.diag(c)[:b]+np.diag(c)[b:]);counts.append(q['nominal_common_fft_blocks'])
        means.append(v[index,channel_index])
    z=np.asarray(means);nu=np.asarray(noise);pairs=np.asarray(data['pairs'])
    if not np.isfinite(nu).all() or np.any(nu<0):return unavailable('invalid_complex_noise_variance')
    profile_kind=None;epoch=None
    if rate_profile is not None:
        if not isinstance(rate_profile,dict):raise ValueError('rate profile must be a mapping')
        if 'rate_profile_type' not in meta:return unavailable('stored_rate_correction_unknown')
        stored_rates=np.asarray(meta.get('rate_applied_hz',[]))
        stored_slopes=np.asarray(meta.get('rate_applied_slopes_hz_per_s',[]))
        if (stored_rates.shape!=(len(station_ids),) or stored_slopes.shape!=stored_rates.shape
                or not np.isfinite(stored_rates).all() or not np.isfinite(stored_slopes).all()):
            return unavailable('stored_rate_correction_unknown')
        if meta['rate_profile_type'] is not None or np.any(stored_rates!=0) or np.any(stored_slopes!=0):
            raise ValueError('additional profile would double-correct stored rate; use original pilot')
        origin=meta.get('time_origin_utc');profile_kind=rate_profile.get('type')
        if not origin:raise ValueError('rate rotation requires stored UTC origin')
        if profile_kind=='station_rate_linear':
            rates,slopes,epoch=validate_linear_profile(rate_profile,station_ids,origin,float(start[0]),float(end[-1]))
        else:
            rates,epoch=validate_rate_profile(rate_profile,station_ids,origin,float(start[0]),float(end[-1]))
            slopes=np.zeros_like(rates)
        tau=t-epoch
        phase=2*np.pi*(tau[:,None]*rates[None,:]+.5*tau[:,None]**2*slopes[None,:])
        if not np.isfinite(phase).all():raise ValueError('rotation phase exceeds finite range')
        z=z*np.exp(-1j*(phase[:,pairs[:,0]]-phase[:,pairs[:,1]]))
    try:moments=time_power_moments(z,nu)
    except ValueError:return unavailable('time_power_outside_numerical_range')
    mean,raw_time,raw_mean,mean_noise,noise_of_mean,time_power,mean_power,excess=(moments[k] for k in
        ('mean','raw_time','raw_mean','mean_noise','noise_of_mean','time_power','mean_power','excess'))
    rows=[]
    for index,(i,j) in enumerate(pairs):
        ratio=float(mean_power[index]/time_power[index]) if time_power[index]>0 else None
        if ratio is not None and not np.isfinite(ratio):ratio=None
        rows.append({'pair':[int(i),int(j)],'station_ids':[station_ids[i],station_ids[j]],
            'state':'conditional_estimate' if ratio is not None else 'unverified',
            'reason':None if ratio is not None else 'nonpositive_or_unresolved_time_signal_power',
            'mean_visibility_real':float(mean[index].real),'mean_visibility_imag':float(mean[index].imag),
            'raw_time_power':float(raw_time[index]),'raw_mean_power':float(raw_mean[index]),
            'estimated_cell_noise_variance_mean':float(mean_noise[index]),
            'estimated_noise_variance_of_mean':float(noise_of_mean[index]),
            'noise_subtracted_time_power':float(time_power[index]),
            'noise_subtracted_mean_power':float(mean_power[index]),
            'excess_time_scatter':float(excess[index]),'mean_to_time_power_ratio_unbounded':ratio})
    return {**result,'state':'conditional_estimate','station_ids':station_ids,
        'visibility_unit':meta['visibility_unit'],'power_unit':'ADC^4' if meta['visibility_unit']=='ADC^2' else 'Jy^2',
        'time_origin_utc':meta.get('time_origin_utc'),'time_range_s':[float(start[0]),float(end[-1])],
        'nominal_common_fft_blocks_range':[int(min(counts)),int(max(counts))],
        'rate_profile_type':profile_kind,'rate_reference_s':epoch,
        'additional_center_rotation_applied':rate_profile is not None,
        'stored_rate_profile_type':meta.get('rate_profile_type'),
        'ratio_clipped_to_physical_interval':False,'confidence_interval_computed':False,
        'noise_subtraction_ensemble_unbiased_only_if_assumptions_hold':True,
        'power_ratio_unbiased_guarantee':False,'baselines':rows}


def _closed_input(path,reader):
    path=Path(path);before=path.stat()
    with path.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
    value=reader(path);after=path.stat()
    def identity(s):return s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns
    if identity(before)!=identity(after):raise ValueError('input changed during diagnostic; use a closed archive')
    return value,sha


def diagnose_time_file(input,output,channel_index,rate_profile=None):
    out=Path(output)
    if out.suffix!='.json':raise ValueError('time-scatter output must be JSON')
    if out.exists():raise FileExistsError('time-scatter diagnostic already exists')
    data,sha=_closed_input(input,load_spectral);profile=None;profile_sha=None
    if rate_profile is not None:
        profile,profile_sha=_closed_input(rate_profile,lambda p:json.loads(p.read_text()))
    q={**diagnose_time_scatter(data,channel_index,profile),'input_sha256':sha,'rate_profile_sha256':profile_sha}
    encoded=json.dumps(q,indent=2,allow_nan=False)+'\n';out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as stream:stream.write(encoded)
    return q


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Conditional passive pilot time-scatter diagnostic')
    parser.add_argument('--input',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--channel-index',type=int,required=True);parser.add_argument('--rate-profile')
    q=diagnose_time_file(**vars(parser.parse_args()))
    print(json.dumps({k:q[k] for k in ('state','time_cells','frequency_hz')},indent=2))


if __name__=='__main__':main()
