"""Experimental exact U3 moments for known iid proper Gaussian station S."""
from itertools import combinations, permutations
import math
import numpy as np
from .bispectrum_distinct import gaussian_ordinary_bispectrum_mean


def falling(samples,order):
    return 0 if samples<order else math.prod(range(samples-order+1,samples+1))


def overlap_weights(samples):
    denominator=falling(samples,3)**2
    return [falling(samples,6-k)/denominator for k in range(4)]


def _centered_covariance(s,edges,samples,conjugate):
    right=edges[:,:,::-1] if conjugate else edges
    left_mean=s[edges[:,:,0],edges[:,:,1]]
    right_mean=s[right[:,:,0],right[:,:,1]]
    count=edges.shape[1];result=np.zeros((count,count),complex)
    coefficients=overlap_weights(samples)
    for k in range(1,4):
        coefficient=coefficients[k]
        if coefficient==0:continue
        for left_slots in combinations(range(3),k):
            for right_slots in permutations(range(3),k):
                common=np.ones((count,count),complex)
                for a in set(range(3))-set(left_slots):common*=left_mean[a,:,None]
                for b in set(range(3))-set(right_slots):common*=right_mean[b,None,:]
                pair_means=[];contractions=[]
                for a,b in zip(left_slots,right_slots):
                    i,j=edges[a].T;p,q=right[b].T
                    pair_means.append(left_mean[a,:,None]*right_mean[b,None,:])
                    contractions.append(s[i[:,None],q[None,:]]*s[p[None,:],j[:,None]])
                for subset in range(1,1<<k):
                    term=common.copy()
                    for n in range(k):term*=contractions[n] if subset&(1<<n) else pair_means[n]
                    result+=coefficient*term
    return result


def gaussian_distinct_bispectrum_moments(station_covariance,samples,triangles=None):
    """Known constant S; iid zero-mean proper Gaussian voltage samples.

    Covariance order [all real triangles, all imaginary triangles]. Exact
    finite-sample moments do not imply a Gaussian U3 likelihood or unbiased
    phase/amplitude. No observed covariance or station-gain estimator.
    """
    if np.ma.isMaskedArray(station_covariance) or np.ma.isMaskedArray(triangles):
        raise ValueError('masked station covariance/triangles unsupported')
    if isinstance(samples,bool) or not isinstance(samples,(int,np.integer)) or not 3<=samples<=1000000:
        raise ValueError('integer independent sample count 3..1000000 required')
    raw=np.asarray(station_covariance)
    if raw.ndim!=2 or raw.shape[0]!=raw.shape[1] or not 3<=len(raw)<=8:
        raise ValueError('3..8 station square covariance required')
    checked=gaussian_ordinary_bispectrum_mean(raw,samples,triangles)
    s=raw.astype(np.complex128);s=.5*s+.5*s.conj().T;t=checked['triangles']
    edges=np.stack((t[:,[0,1]],t[:,[1,2]],t[:,[2,0]]))
    with np.errstate(over='ignore',invalid='ignore',under='ignore'):
        g=_centered_covariance(s,edges,int(samples),True)
        p=_centered_covariance(s,edges,int(samples),False)
    if (not np.isfinite(g).all() or not np.isfinite(p).all()
            or np.any((s.diagonal().real[t]>0).all(axis=1)&(g.diagonal().real<=0))):
        raise ValueError('bispectrum moments outside supported numerical range')
    scale=max(float(np.max(abs(g))),float(np.max(abs(p))),np.finfo(float).tiny)
    if max(float(np.max(abs(g-g.conj().T))),float(np.max(abs(p-p.T))))>1e-10*scale:
        raise ValueError('bispectrum covariance symmetry exceeds numerical tolerance')
    g=.5*g+.5*g.conj().T;p=.5*p+.5*p.T
    real=.5*np.block([[np.real(g+p),np.imag(p-g)],[np.imag(p+g),np.real(g-p)]])
    real=.5*real+.5*real.T
    if not np.isfinite(real).all() or np.linalg.eigvalsh(real).min() < -1e-10*scale:
        raise ValueError('real bispectrum covariance exceeds PSD numerical tolerance')
    return {'triangles':t.copy(),'samples':int(samples),'mean':np.prod(s[edges[:,:,0],edges[:,:,1]],axis=0),
        'complex_covariance':g,'complex_pseudocovariance':p,'real_covariance':real,
        'real_parameter_order':'all real triangles, then all imaginary triangles',
        'possible_sample_overlap_patterns':34,'algebraic_contraction_products':105,
        'generating_covariance_supplied':True,'distribution_gaussian_assumed':False,
        'actual_temporal_independence_verified':False,'closure_phase_unbiased_guarantee':False,
        'production_rml_noise_model_changed':False,'real_hardware_validation_performed':False,
        'scope':'Exact finite-M moments under known iid proper Gaussian voltage S and constant gain. No empirical noise, filtered/quantized/variable clock data, phase likelihood or image confidence.'}
