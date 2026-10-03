"""Experimental sample-distinct bispectrum; iid samples required, no RML use."""
from itertools import combinations
import numpy as np
from .visibility_moments import visibility_noise_moments


def _triangles(stations,triangles):
    t=np.array(list(combinations(range(stations),3)),dtype=int) if triangles is None else np.asarray(triangles)
    if (t.ndim!=2 or t.shape[1]!=3 or not len(t) or not np.issubdtype(t.dtype,np.integer)
            or np.any(t<0) or np.any(t>=stations) or np.any(t[:,0]>=t[:,1]) or np.any(t[:,1]>=t[:,2])
            or len(np.unique(t,axis=0))!=len(t)):
        raise ValueError('unique canonical integer triangles i<j<k required')
    return t


def distinct_sample_bispectrum(voltages,triangles=None):
    """Use distinct ordered sample indices for each of three baseline products.

    Input [..., M, N] complex voltage, 3<=M<=1e6, 3<=N<=8.
    Constant pair means and iid M samples with finite moments are required.
    Gaussianity is not needed for unbiasedness. Leading dimensions are
    separate ensembles/windows, not combined samples. No data selection.
    """
    if np.ma.isMaskedArray(voltages):raise ValueError('masked voltages require a verified common sample set')
    x=np.asarray(voltages)
    if (x.ndim<2 or not np.iscomplexobj(x) or not 3<=x.shape[-2]<=1000000
            or not 3<=x.shape[-1]<=8 or not x.size or x.size>8000000 or not np.isfinite(x).all()):
        raise ValueError('finite complex [...,M,N] voltages, M3..1e6, N3..8, at most 8 million values required')
    x=x.astype(np.complex128,copy=False)
    m=x.shape[-2];t=_triangles(x.shape[-1],triangles);naive=[];distinct=[]
    with np.errstate(over='ignore',invalid='ignore'):
        for i,j,k in t:
            a=x[...,i]*x[...,j].conj();b=x[...,j]*x[...,k].conj();c=x[...,k]*x[...,i].conj()
            sa=a.sum(axis=-1);sb=b.sum(axis=-1);sc=c.sum(axis=-1)
            total=sa*sb*sc
            same_ab=(a*b).sum(axis=-1)*sc;same_ac=(a*c).sum(axis=-1)*sb;same_bc=(b*c).sum(axis=-1)*sa
            same_abc=(a*b*c).sum(axis=-1)
            naive.append(total/m**3)
            distinct.append((total-same_ab-same_ac-same_bc+2*same_abc)/(m*(m-1)*(m-2)))
    ordinary=np.stack(naive,axis=-1);u=np.stack(distinct,axis=-1)
    if not np.isfinite(ordinary).all() or not np.isfinite(u).all():raise ValueError('bispectrum exceeds finite numerical range')
    return {'triangles':t,'samples':m,'ordinary_visibility_product':ordinary,'distinct_sample_bispectrum':u,
        'input_sample_independence_verified':False,'ensemble_unbiased_only_if_iid_constant_means':True,
        'closure_phase_unbiased_guarantee':False,'real_hardware_validation_performed':False,
        'production_rml_noise_model_changed':False,'generating_truth_used':False}


def gaussian_ordinary_bispectrum_mean(station_covariance,samples,triangles=None):
    """Exact mean of the ordinary product under iid zero-mean proper Gaussian x."""
    s=np.asarray(station_covariance)
    if s.ndim!=2 or not 3<=len(s)<=8:raise ValueError('3..8 station covariance required')
    visibility_noise_moments(s,samples)
    t=_triangles(len(s),triangles);i,j,k=t.T
    true=s[i,j]*s[j,k]*s[k,i]
    d=s[i,i].real*abs(s[j,k])**2+s[j,j].real*abs(s[i,k])**2+s[k,k].real*abs(s[i,j])**2
    p=s[i,i].real*s[j,j].real*s[k,k].real
    with np.errstate(over='ignore',invalid='ignore'):
        expected=true+d/samples+(p+true.conj())/samples**2
    if not np.isfinite(expected).all():raise ValueError('Gaussian bispectrum mean exceeds finite numerical range')
    return {'triangles':t,'true_bispectrum':true,'ordinary_product_mean':expected,
        'ordinary_product_bias':expected-true,'samples':int(samples),'generating_covariance_supplied':True}
