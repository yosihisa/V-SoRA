"""Complex-Gaussian spectral kurtosis and explicit channel exclusion.

Fixed thresholds are diagnostic defaults, not a calibrated false-alarm rate.
"""
import numpy as np


def validate_quality(config):
    required={'channel_weights','min_sk_blocks','sk_bounds','exclude_rf_ranges_hz'}
    if not isinstance(config,dict) or set(config)!=required:
        raise ValueError('spectral_quality keys differ')
    if not isinstance(config['channel_weights'],bool): raise ValueError('channel_weights bool required')
    m=config['min_sk_blocks']
    if not isinstance(m,int) or isinstance(m,bool) or m<24: raise ValueError('min_sk_blocks >=24 required')
    bounds=config['sk_bounds']
    if not isinstance(bounds,list) or len(bounds)!=2 or not all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in bounds):
        raise ValueError('two finite SK bounds required')
    if not np.isfinite(bounds).all() or not 0<bounds[0]<1<bounds[1]: raise ValueError('SK bounds must bracket 1')
    ranges=config['exclude_rf_ranges_hz']
    if not isinstance(ranges,list): raise ValueError('RF ranges list required')
    for r in ranges:
        if not isinstance(r,list) or len(r)!=2 or not all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in r):
            raise ValueError('RF interval pair required')
        if not np.isfinite(r).all() or not 0<r[0]<r[1]: raise ValueError('positive increasing RF range required')
    return config


def channel_diagnostics(spectrum,block_valid,frequencies_hz,config):
    validate_quality(config)
    x=np.asarray(spectrum);ok=np.asarray(block_valid,bool);f=np.asarray(frequencies_hz)
    if x.ndim!=3 or ok.shape!=(x.shape[0],x.shape[2]) or f.shape!=(x.shape[1],):
        raise ValueError('spectrum must have block/channel/station axes')
    if not np.isfinite(x).all(): raise ValueError('finite spectra required')
    channels,stations=x.shape[1:];power=np.zeros((channels,stations));sk=np.ones_like(power)
    eligible=np.zeros_like(power,bool);reason=np.zeros_like(power,dtype=np.uint8)
    counts=ok.sum(axis=0)
    for s in range(stations):
        m=int(counts[s])
        if m==0:
            reason[:,s]|=1;continue
        p=abs(x[ok[:,s],:,s])**2
        power[:,s]=p.mean(axis=0);positive=power[:,s]>0
        reason[~positive,s]|=1
        if m>=config['min_sk_blocks']:
            normalized=np.divide(p,power[:,s],out=np.zeros_like(p),where=positive)
            sk[positive,s]=(m+1)/(m-1)*(np.mean(normalized[:,positive]**2,axis=0)-1)
            sk[:,s]=np.maximum(sk[:,s],0)
            eligible[positive,s]=True
            reason[positive&(sk[:,s]<config['sk_bounds'][0]),s]|=2
            reason[positive&(sk[:,s]>config['sk_bounds'][1]),s]|=4
    for lo,hi in config['exclude_rf_ranges_hz']:
        reason[(f>=lo)&(f<=hi),:]|=8
    return {'diagnostic_station_power':power,'diagnostic_station_sk':sk,
            'diagnostic_station_sk_eligible':eligible,'diagnostic_station_flags':reason,
            'diagnostic_station_valid_fft_count':counts}
