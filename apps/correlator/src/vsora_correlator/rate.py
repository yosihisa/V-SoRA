"""Short-pilot rate estimation without a known sky or station gain model.

Each baseline/channel has its own unknown constant complex visibility.
Only a common temporal phase slope per baseline is fitted. Assumes uniform
pilot cadence, independent circular thermal errors, and stable sky/response.
"""
import numpy as np
from scipy.optimize import minimize_scalar


def estimate_station_rates(data, reference_station=0, max_rate_hz=100., min_snr=8., min_peak_z=8., max_reduced_chisq=3.):
    v = np.asarray(data.get('visibilities', data.get('vis_jy')))
    w, t, pairs = (np.asarray(data[k]) for k in ('weights','times_s','pairs'))
    if (v.ndim != 3 or w.shape != v.shape or t.shape != (v.shape[0],) or len(t) < 8
            or pairs.shape != (v.shape[-1],2) or not np.iscomplexobj(v)
            or not np.isfinite(v).all() or not np.isfinite(w).all() or np.any(w < 0)
            or not np.isfinite(t).all() or not np.issubdtype(pairs.dtype,np.integer)
            or np.any(pairs < 0) or np.any(pairs[:,0]>=pairs[:,1])
            or len(np.unique(pairs,axis=0)) != len(pairs)):
        raise ValueError('invalid short-pilot spectral data')
    dt = np.diff(t)
    if np.any(dt <= 0) or not np.allclose(dt,dt[0],rtol=1e-8,atol=1e-10):
        raise ValueError('uniform increasing pilot times required')
    if t[-1]-t[0]+dt[0] > 3.+1e-9:
        raise ValueError('reference rate pilot is limited to three seconds of stable sky/gain')
    if (not np.isfinite(max_rate_hz) or not 0 < max_rate_hz < .5/dt[0]
            or any(not np.isfinite(x) or x <= 0 for x in (min_snr,min_peak_z,max_reduced_chisq))):
        raise ValueError('rate search must be below the temporal Nyquist limit')
    stations = sorted(set(pairs.ravel().tolist()))
    if reference_station not in stations: raise ValueError('reference station not present')
    reference_time = float((t[0]+t[-1])/2); tau = t-reference_time
    nfft = 4*len(t); frequency = np.fft.fftfreq(nfft,dt[0]); step = 1/(nfft*dt[0])
    records = []
    for b,(i,j) in enumerate(pairs):
        valid_channels = (w[:,:,b] > 0).sum(axis=0) >= 8
        wb, vb = w[:,valid_channels,b], v[:,valid_channels,b]
        den = wb.sum(axis=0); channels = len(den)
        record = {'pair':[int(i),int(j)],'accepted':False}
        if not channels:
            records.append({**record,'reason':'no channels with eight valid samples'}); continue
        weighted = wb*vb
        score = (abs(np.fft.fft(weighted,n=nfft,axis=0))**2/den).sum(axis=1)
        peak = int(np.argmax(score)); coarse = float(frequency[peak])
        if abs(coarse) >= max_rate_hz-step:
            records.append({**record,'reason':'peak outside search or on search boundary','coarse_rate_hz':coarse}); continue
        def power(rate):
            coherent = (weighted*np.exp(-2j*np.pi*rate*tau[:,None])).sum(axis=0)
            return float(np.sum(abs(coherent)**2/den))
        fit = minimize_scalar(lambda r:-power(r),bounds=(coarse-step,coarse+step),method='bounded',
                              options={'xatol':1e-9})
        rate = float(fit.x)
        for _ in range(6):
            phase = np.exp(-2j*np.pi*rate*tau[:,None])
            coherent = (weighted*phase).sum(axis=0)
            derivative = (weighted*phase*(-2j*np.pi*tau[:,None])).sum(axis=0)
            second = (weighted*phase*(-(2*np.pi*tau[:,None])**2)).sum(axis=0)
            slope = float(np.sum(2*np.real(derivative*coherent.conj())/den))
            curvature = float(np.sum(2*np.real(second*coherent.conj()+abs(derivative)**2)/den))
            if curvature >= 0: break
            correction = slope/curvature
            candidate = rate-correction
            if not coarse-step < candidate < coarse+step: break
            rate = candidate
            if abs(correction) < 1e-10: break
        q = power(rate)
        snr = float(np.sqrt(max(0,q-2*channels)))
        peak_z = float((q-2*channels)/np.sqrt(4*channels))
        record.update(rate_hz=rate,coherent_snr=snr,noise_peak_z=peak_z,channels=channels)
        if not fit.success or snr < min_snr or peak_z < min_peak_z:
            records.append({**record,'reason':'insufficient coherent detection'}); continue
        amplitude = (weighted*np.exp(-2j*np.pi*rate*tau[:,None])).sum(axis=0)/den
        center = (wb*tau[:,None]).sum(axis=0)/den
        information = np.sum(wb*abs(amplitude)[None,:]**2*(2*np.pi*(tau[:,None]-center))**2)
        sigma = max(float(1/np.sqrt(information)),1e-6)
        record.update(accepted=True,rate_sigma_hz=sigma); records.append(record)
    accepted = [r for r in records if r['accepted']]
    unknown = [s for s in stations if s != reference_station]
    matrix = np.zeros((len(accepted),len(unknown)))
    for row,record in enumerate(accepted):
        for station,sign in zip(record['pair'],[1,-1]):
            if station != reference_station: matrix[row,unknown.index(station)] = sign
    if not len(accepted) or np.linalg.matrix_rank(matrix) < len(unknown):
        raise ValueError('detected rate graph is disconnected; use a longer/stronger pilot or fewer stations')
    errors = np.array([r['rate_sigma_hz'] for r in accepted])
    measured = np.array([r['rate_hz'] for r in accepted])
    solution = np.linalg.lstsq(matrix/errors[:,None], measured/errors, rcond=None)[0]
    residual = (matrix@solution-measured)/errors
    degrees = len(accepted)-len(unknown)
    reduced = float(residual@residual/degrees) if degrees else None
    if reduced is not None and reduced > max_reduced_chisq:
        raise ValueError('baseline rate estimates inconsistent with station rates')
    covariance = np.linalg.inv((matrix/errors[:,None]).T@(matrix/errors[:,None]))
    rates = [0. if s == reference_station else float(solution[unknown.index(s)]) for s in stations]
    return {'schema_version':1,'type':'station_rate_only','station_indices':stations,'station_rates_hz':rates,
            'reference_station':int(reference_station),'time_reference_s':reference_time,
            'valid_time_range_s':[float(t[0]),float(t[-1])],'sample_cadence_s':float(dt[0]),
            'max_baseline_rate_hz':max_rate_hz,'temporal_nyquist_hz':float(.5/dt[0]),
            'initial_baseline_rate_bound_externally_required':True,'baseline_estimates':records,
            'station_covariance_hz2':covariance.tolist(),'covariance_station_order':unknown,
            'reduced_rate_chisq':reduced,'accepted_baselines':len(accepted),
            'absolute_common_rate_measured':False,'amplitude_or_sky_phase_calibration':False,
            'model':'Unknown constant complex visibility per baseline/channel; temporal phase rate only',
            'limits':'Short stable sky/gain; circular independent baseline/channel noise; no low SNR or clock drift inference; out-of-Nyquist rates can alias undetectably; initial LO bound is an external assumption'}


def main():
    import argparse
    import json
    from pathlib import Path
    p = argparse.ArgumentParser(description='Estimate station rates only, without a sky/gain calibration model')
    p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    p.add_argument('--max-rate-hz',type=float,default=100.);p.add_argument('--reference-station',type=int,default=0)
    a=p.parse_args();out=Path(a.output)
    if out.exists():raise FileExistsError('rate output already exists')
    result=estimate_rate_shard(a.input,a.reference_station,a.max_rate_hz)
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


def estimate_rate_shard(path,reference_station=0,max_rate_hz=100.):
    import hashlib
    from vsora_formats.spectral import load_spectral
    d=load_spectral(path);meta=d['metadata']
    if not meta.get('phase_center_corrected') or not meta.get('clock_mapping_applied'):
        raise ValueError('rate-only production profile requires sample and phase-center alignment')
    if not meta.get('time_origin_utc'):raise ValueError('pilot UTC origin required')
    result=estimate_station_rates(d,reference_station,max_rate_hz)
    previous=np.asarray(meta.get('rate_applied_hz',np.zeros(len(result['station_indices']))),float)
    if previous.shape!=(len(result['station_indices']),) or not np.isfinite(previous).all():
        raise ValueError('invalid prior rate correction')
    total=np.array(result['station_rates_hz'])+previous
    total-=total[reference_station]
    result['residual_station_rates_hz']=result['station_rates_hz']
    result['station_rates_hz']=total.tolist()
    result['station_ids']=[s['id'] for s in meta['config']['stations']]
    result['time_origin_utc']=meta['time_origin_utc']
    with open(path,'rb') as stream:result['input_sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
    return result


def validate_rate_profile(profile,station_ids,origin,start_s,end_s,allow_extrapolation=False):
    from astropy.time import Time
    if (isinstance(profile.get('schema_version'),bool) or profile.get('schema_version')!=1 or profile.get('type')!='station_rate_only'
            or profile.get('station_ids')!=station_ids
            or profile.get('station_indices')!=list(range(len(station_ids)))):
        raise ValueError('rate-only profile type or station order differs')
    if not profile.get('time_origin_utc') or abs((Time(profile['time_origin_utc'])-Time(origin)).sec)>1e-7:
        raise ValueError('rate-only profile UTC origin differs')
    rates=np.asarray(profile.get('station_rates_hz'),float)
    limits=np.asarray(profile.get('valid_time_range_s'),float)
    cadence=profile.get('sample_cadence_s')
    if (rates.shape!=(len(station_ids),) or limits.shape!=(2,) or not np.isfinite(rates).all()
            or not np.isfinite(limits).all() or limits[1]<=limits[0]
            or not isinstance(cadence,(int,float)) or not np.isfinite(cadence) or cadence<=0):
        raise ValueError('invalid rate-only values/time coverage')
    if not allow_extrapolation and (start_s<limits[0]-cadence/2-1e-9 or end_s>limits[1]+cadence/2+1e-9):
        raise ValueError('rate-only extrapolation requires explicit permission')
    epoch=profile.get('time_reference_s')
    if not isinstance(epoch,(int,float)) or not np.isfinite(epoch):raise ValueError('invalid rate reference time')
    if not limits[0]<=epoch<=limits[1]:raise ValueError('rate reference time outside pilot range')
    return rates,float(epoch)


if __name__=='__main__':main()
