"""Band-limited fractional sample alignment and a coherent-test clock solver.

Clock mapping is distinct from RF phase/rate calibration. Input bandwidth must
have guard space; this finite sinc is not a general antialias/downsample filter.
"""
import numpy as np
from scipy.signal import correlate,correlation_lags
from scipy.optimize import least_squares


def interpolate_samples(samples,positions,valid=None,radius=32,chunk_size=2048):
    x=np.asarray(samples);p=np.asarray(positions,float)
    if x.ndim!=1 or not np.iscomplexobj(x) or not np.isfinite(x).all(): raise ValueError('finite complex samples required')
    if p.ndim!=1 or len(p)==0 or not np.isfinite(p).all() or np.any(np.diff(p)<=0): raise ValueError('increasing finite query positions required')
    if not isinstance(radius,int) or radius<8 or radius>128: raise ValueError('sinc radius must be 8..128')
    if p.min()<radius or p.max()>=len(x)-radius-1: raise ValueError('queries need input guard samples; extrapolation forbidden')
    mask=np.ones(len(x),bool) if valid is None else np.asarray(valid,dtype=bool)
    if mask.shape!=x.shape: raise ValueError('valid shape mismatch')
    result=np.empty(len(p),complex);good=np.empty(len(p),bool);offset=np.arange(-radius,radius+1)
    for first in range(0,len(p),chunk_size):
        stop=min(first+chunk_size,len(p));q=p[first:stop]
        indexes=np.floor(q).astype(int)[:,None]+offset
        distance=q[:,None]-indexes
        coeff=np.sinc(distance)*np.where(abs(distance)<=radius,.5*(1+np.cos(np.pi*distance/radius)),0)
        coeff/=coeff.sum(axis=1)[:,None]
        result[first:stop]=np.sum(x[indexes]*coeff,axis=1)
        # Conservative support: no filled gap is treated as measured signal.
        good[first:stop]=mask[indexes].all(axis=1)
    result[~good]=0
    return result,good


def resample_station(samples,input_start_s,actual_sample_rate_hz,query_times_s,
                     output_sample_rate_hz,max_abs_baseband_hz,valid=None,radius=32):
    values=np.array([input_start_s,actual_sample_rate_hz,output_sample_rate_hz,max_abs_baseband_hz],float)
    if not np.isfinite(values).all() or np.any(values[1:]<=0): raise ValueError('invalid sampling coordinates')
    if max_abs_baseband_hz>.4*min(actual_sample_rate_hz,output_sample_rate_hz):
        raise ValueError('bandwidth needs 20 percent Nyquist guard for this reference interpolator')
    positions=(np.asarray(query_times_s)-input_start_s)*actual_sample_rate_hz
    return interpolate_samples(samples,positions,valid,radius)


def estimate_clock_mapping(reference,station,nominal_sample_rate_hz,max_offset_samples=24.,
                           max_drift_ppm=200.,radius=32,min_coherence=.8):
    """Infer station positions = offset + (1+ppm*1e-6)*reference index.

    Requires a strongly coherent, rate-corrected common signal. This is a test
    estimator, not a faint-source VLBI clock recovery algorithm. Geometry and
    clock offset are degenerate unless geometry is independently supplied.
    """
    r=np.asarray(reference);x=np.asarray(station)
    if r.shape!=x.shape or r.ndim!=1 or len(r)<4096 or not np.iscomplexobj(r) or not np.iscomplexobj(x):
        raise ValueError('equal complex vectors with >=4096 samples required')
    if not np.isfinite(r).all() or not np.isfinite(x).all() or nominal_sample_rate_hz<=0:
        raise ValueError('invalid clock input')
    limit=int(np.ceil(max_offset_samples+len(r)*max_drift_ppm*1e-6+2))
    centers=[];lags=[];window=1024
    for start in np.linspace(0,len(r)-window,16,dtype=int):
        cross=correlate(r[start:start+window],x[start:start+window],method='fft')
        axis=correlation_lags(window,window);ok=abs(axis)<=limit
        index=np.flatnonzero(ok)[np.argmax(abs(cross[ok]))]
        y=abs(cross[index-1:index+2]);den=y[0]-2*y[1]+y[2]
        fraction=.5*(y[0]-y[2])/den if den!=0 else 0
        centers.append(start+window/2);lags.append(axis[index]+fraction)
    slope,intercept=np.polyfit(centers,lags,1)
    initial=np.array([-intercept,-slope*1e6])
    lower=np.array([-max_offset_samples,-max_drift_ppm]);upper=-lower
    if np.any(initial<=lower) or np.any(initial>=upper): raise ValueError('clock estimate outside search limits')
    guard=radius+limit+2
    indexes=np.linspace(guard,len(r)-guard-2,min(4096,len(r)-2*guard-2)).astype(int)
    target=r[indexes]
    def evaluate(parameters):
        positions=parameters[0]+(1+parameters[1]*1e-6)*indexes
        aligned,_=interpolate_samples(x,positions,radius=radius)
        gain=np.vdot(aligned,target)/np.vdot(aligned,aligned)
        return aligned*gain,gain
    norm=np.sqrt(np.mean(abs(target)**2))
    if norm==0: raise ValueError('zero clock reference')
    def residual(parameters):
        z=(evaluate(parameters)[0]-target)/norm
        return np.r_[z.real,z.imag]
    fit=least_squares(residual,initial,bounds=(lower,upper),x_scale=[1,100],
                      diff_step=1e-4,ftol=1e-10,xtol=1e-10,gtol=1e-10,max_nfev=50)
    aligned,gain=evaluate(fit.x)
    coherence=float(abs(np.vdot(target,aligned))/np.sqrt(np.vdot(target,target).real*np.vdot(aligned,aligned).real))
    if not fit.success or np.any(fit.active_mask) or coherence<min_coherence:
        raise ValueError('clock mapping not detected or outside limits')
    actual=nominal_sample_rate_hz*(1+fit.x[1]*1e-6)
    return {'schema_version':1,'position_offset_samples':float(fit.x[0]),'sample_rate_error_ppm':float(fit.x[1]),
            'actual_sample_rate_hz':float(actual),'effective_start_s':float(-fit.x[0]/actual),
            'coherence':coherence,'relative_residual':float(np.linalg.norm(aligned-target)/np.linalg.norm(target)),
            'coarse_lag_samples':np.asarray(lags).tolist(),'coarse_center_samples':np.asarray(centers).tolist(),
            'constant_correction_gain':[float(gain.real),float(gain.imag)],
            'assumption':'Strong common signal after LO/rate correction; effective offset includes source geometry'}
