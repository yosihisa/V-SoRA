"""Small CPU reference station fringe solver for uniform time/frequency grids.

Requires a known, nonzero sky model and usable baselines to the reference.
Delay and fringe rate are relative values within explicitly sampled aliases.
"""
import json
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares


def _axis(values, name):
    x=np.asarray(values,float)
    if x.ndim!=1 or len(x)<8 or not np.isfinite(x).all():
        raise ValueError(f'{name} needs >=8 finite samples')
    step=np.diff(x)
    if step[0]<=0 or not np.allclose(step,step[0],rtol=1e-6,atol=1e-10):
        raise ValueError(f'{name} must be increasing and uniform')
    return x,float(step[0])


def _inputs(observed,model,weights,pairs,times_s,frequencies_hz):
    t,dt=_axis(times_s,'times_s');f,df=_axis(frequencies_hz,'frequencies_hz')
    v=np.asarray(observed,complex);m=np.asarray(model,complex);w=np.asarray(weights,float)
    p=np.asarray(pairs)
    if p.ndim!=2 or p.shape[1]!=2 or not np.issubdtype(p.dtype,np.integer):
        raise ValueError('integer station pairs required')
    if np.any(p<0) or np.any(p[:,0]>=p[:,1]) or len(np.unique(p,axis=0))!=len(p):
        raise ValueError('invalid or repeated station pair')
    if v.shape!=(len(t),len(f),len(p)) or m.shape!=v.shape or w.shape!=v.shape:
        raise ValueError('visibility must be time/channel/baseline')
    if any(not np.isfinite(a).all() for a in (v,m,w)) or np.any(w<0):
        raise ValueError('invalid complex values/weights')
    return v,m,w,p,t,f,dt,df


def station_gains(calibration,times_s,frequencies_hz,allow_extrapolation=False):
    c=calibration;t=np.asarray(times_s,float);f=np.asarray(frequencies_hz,float)
    if not np.isfinite(t).all() or not np.isfinite(f).all(): raise ValueError('nonfinite gain coordinates')
    if not allow_extrapolation:
        if t.min()<c['time_range_s'][0]-1e-9 or t.max()>c['time_range_s'][1]+1e-9:
            raise ValueError('calibration time extrapolation requires explicit permission')
        if f.min()<c['frequency_range_hz'][0] or f.max()>c['frequency_range_hz'][1]:
            raise ValueError('calibration frequency extrapolation requires explicit permission')
    phase=(np.asarray(c['phase_rad'])[None,None,:]
           +2*np.pi*(t[:,None,None]-c['time_reference_s'])*np.asarray(c['rate_hz'])[None,None,:]
           +2*np.pi*(f[None,:,None]-c['frequency_reference_hz'])*np.asarray(c['delay_s'])[None,None,:])
    return np.asarray(c['amplitude'])[None,None,:]*np.exp(1j*phase)


def apply_calibration(observed,weights,pairs,calibration,times_s,frequencies_hz,
                      allow_extrapolation=False):
    g=station_gains(calibration,times_s,frequencies_hz,allow_extrapolation)
    p=np.asarray(pairs)
    factors=g[...,p[:,0]]*g[...,p[:,1]].conj()
    v=np.asarray(observed);w=np.asarray(weights)
    if v.shape!=factors.shape or w.shape!=v.shape: raise ValueError('calibration dimensions differ')
    if not np.isfinite(factors).all() or np.any(abs(factors)<1e-12): raise ValueError('invalid station gain')
    return v/factors,w*abs(factors)**2


def solve_fringe(observed,model,weights,pairs,times_s,frequencies_hz,reference_station=0,
                 min_coherence=.25,min_peak_ratio=8.,delay_limit_s=None,rate_limit_hz=None):
    v,m,w,p,t,f,dt,df=_inputs(observed,model,weights,pairs,times_s,frequencies_hz)
    n=int(p.max())+1;ref=reference_station
    if not isinstance(ref,int) or not 0<=ref<n or n<3: raise ValueError('need >=3 stations and a valid reference')
    dl=.45/df if delay_limit_s is None else float(delay_limit_s)
    rl=.45/dt if rate_limit_hz is None else float(rate_limit_hz)
    if not 0<dl<.5/df or not 0<rl<.5/dt:
        raise ValueError('search window must lie inside sampled delay/rate alias interval')
    valid=(w>0)&(abs(m)>max(float(abs(m).max())*.001,1e-12))
    if not valid.any(): raise ValueError('no usable model/weights')
    w=np.where(valid,w,0.)
    # Absolute amplitudes require a known flux model and a graph with enough
    # information (e.g. a triangle); a two-station amplitude split is ambiguous.
    good=np.array([valid[...,b].sum()>=16 for b in range(len(p))])
    design=np.zeros((int(good.sum()),n))
    for row,(i,j) in enumerate(p[good]): design[row,i]=design[row,j]=1
    if np.linalg.matrix_rank(design)<n: raise ValueError('amplitude graph is not identifiable')
    ratio=[]
    for b in np.flatnonzero(good):
        ratio.append(np.log(np.sum(w[...,b]*abs(v[...,b])*abs(m[...,b]))/
                            np.sum(w[...,b]*abs(m[...,b])**2)))
    amp=np.linalg.lstsq(design,np.array(ratio),rcond=None)[0]
    phase=np.zeros(n);delay=np.zeros(n);rate=np.zeros(n);detections=[]
    tc=t-t.mean();fc=f-f.mean()
    os=4;shape=(len(t)*os,len(f)*os)
    rg=np.fft.fftfreq(shape[0],dt);dg=np.fft.fftfreq(shape[1],df)
    window=(abs(rg[:,None])<rl)&(abs(dg[None,:])<dl)
    for j in range(n):
        if j==ref: continue
        match=np.flatnonzero(((p[:,0]==ref)&(p[:,1]==j))|((p[:,0]==j)&(p[:,1]==ref)))
        if len(match)!=1: raise ValueError('every station needs a baseline to the reference')
        b=int(match[0]);cross=v[...,b]*m[...,b].conj()*w[...,b]
        if p[b,0]!=ref: cross=cross.conj()
        if valid[...,b].sum()<16: raise ValueError('too few usable reference-baseline samples')
        plane=abs(np.fft.ifft2(cross,s=shape))
        peak=np.unravel_index(np.argmax(np.where(window,plane,-np.inf)),shape)
        delay[j]=dg[peak[1]];rate[j]=rg[peak[0]]
        coherent=np.sum(cross*np.exp(2j*np.pi*(tc[:,None]*rate[j]+fc[None,:]*delay[j])))
        denom=np.sum(w[...,b]*abs(v[...,b])*abs(m[...,b]))
        coherence=float(abs(coherent)/denom) if denom>0 else 0.
        peak_ratio=float(plane[peak]/max(float(np.median(plane)),1e-30))
        if coherence<min_coherence or peak_ratio<min_peak_ratio:
            raise ValueError(f'fringe not detected for station {j}')
        phase[j]=-np.angle(coherent)
        detections.append({'station':j,'coarse_coherence':coherence,'peak_to_median':peak_ratio})
    others=np.array([j for j in range(n) if j!=ref]);spanf=np.ptp(f);spant=np.ptp(t)
    initial=np.r_[amp,phase[others],delay[others]*spanf,rate[others]*spant]
    sw=np.sqrt(w);norm=max(float(np.sqrt(np.mean(abs(m)**2*w))),1e-30)
    sw/=norm
    def unpack(x):
        ph=np.zeros(n);de=np.zeros(n);ra=np.zeros(n)
        ph[others]=x[n:n+n-1];de[others]=x[n+n-1:n+2*(n-1)]/spanf;ra[others]=x[n+2*(n-1):]/spant
        return np.exp(x[:n]),ph,de,ra
    def prediction(x):
        a,ph,de,ra=unpack(x)
        theta=(ph[None,None,:]+2*np.pi*(fc[None,:,None]*de[None,None,:]+tc[:,None,None]*ra[None,None,:]))
        gain=a[None,None,:]*np.exp(1j*theta)
        return m*gain[...,p[:,0]]*gain[...,p[:,1]].conj()
    def residual(x):
        z=(prediction(x)-v)*sw
        return np.r_[z.real.ravel(),z.imag.ravel()]
    # Scaled parameters and an analytic Jacobian keep the reference solve small.
    def jacobian(x):
        pred=prediction(x)*sw;rows=pred.size;columns=len(x)
        jac=np.zeros((2*rows,columns))
        for j in range(n):
            z=pred*((p[:,0]==j)|(p[:,1]==j))[None,None,:]
            jac[:,j]=np.r_[z.real.ravel(),z.imag.ravel()]
        for index,j in enumerate(others):
            sign=((p[:,0]==j).astype(int)-(p[:,1]==j).astype(int))[None,None,:]
            for offset,term in [(n,1.),(n+n-1,2*np.pi*fc[None,:,None]/spanf),
                                (n+2*(n-1),2*np.pi*tc[:,None,None]/spant)]:
                z=1j*pred*sign*term
                jac[:,offset+index]=np.r_[z.real.ravel(),z.imag.ravel()]
        return jac
    lower=np.r_[np.full(n,-10.),np.full(n-1,-4*np.pi),np.full(n-1,-dl*spanf),np.full(n-1,-rl*spant)]
    upper=-lower
    result=least_squares(residual,initial,jac=jacobian,bounds=(lower,upper),
                         ftol=1e-10,xtol=1e-10,gtol=1e-10,max_nfev=100)
    a,ph,de,ra=unpack(result.x)
    if not result.success or np.any(result.active_mask): raise ValueError('fringe solve did not converge inside search window')
    relative=float(np.linalg.norm((prediction(result.x)-v)*sw)/max(np.linalg.norm(v*sw),1e-30))
    dof=2*int((w>0).sum())-len(result.x)
    chi=float(np.sum(abs(prediction(result.x)-v)**2*w)/max(dof,1))
    # Low per-channel SNR can give a large relative residual even when the
    # combined fringe is detected. Account for the supplied noise variance.
    if relative>.7 and chi>3: raise ValueError('station model does not explain measured visibility within noise')
    return {'schema_version':1,'reference_station':ref,'amplitude':a.tolist(),
            'phase_rad':np.angle(np.exp(1j*ph)).tolist(),'delay_s':de.tolist(),'rate_hz':ra.tolist(),
            'time_reference_s':float(t.mean()),'frequency_reference_hz':float(f.mean()),
            'time_range_s':[float(t.min()),float(t.max())],
            'frequency_range_hz':[float(f.min()),float(f.max())],
            'delay_alias_period_s':1/df,'rate_alias_period_hz':1/dt,
            'weighted_fit_relative_residual':relative,'reduced_noise_chi_square':chi,'evaluations':int(result.nfev),
            'reference_detections':detections,
            'assumptions':'Known sky flux/model; constant amplitude, phase, delay and rate over this interval'}


def save_calibration(path,calibration):
    p=Path(path)
    if p.exists(): raise FileExistsError(p.name)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(calibration,indent=2,allow_nan=False)+'\n')
