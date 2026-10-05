"""Conditional U3 mean for independent groups with different known pair means."""
import numpy as np
from .bispectrum_distinct import gaussian_ordinary_bispectrum_mean


def pooled_covariance_bispectrum_mean(group_covariances,samples_per_group,triangles=None):
    """Known S_g; independent samples, equal group sizes. No data coaddition.

    The mean identity needs independence and finite pair means; Gaussianity
    is not needed for this identity. Supplied S_g are validated as covariance
    matrices. This API computes no heterogeneous-group noise covariance.
    """
    if np.ma.isMaskedArray(group_covariances) or np.ma.isMaskedArray(triangles):
        raise ValueError('unmasked group covariance and triangles required')
    if isinstance(samples_per_group,bool) or not isinstance(samples_per_group,(int,np.integer)) or samples_per_group<3:
        raise ValueError('integer group sample count at least3 required')
    raw=np.asarray(group_covariances)
    if raw.ndim!=3 or not 1<=len(raw)<=64 or raw.shape[1]!=raw.shape[2] or not 3<=raw.shape[1]<=8:
        raise ValueError('1..64 square covariance groups with3..8 stations required')
    m=int(samples_per_group);n=m*len(raw)
    if n>1000000:raise ValueError('at most1000000 pooled samples required')
    checked=[gaussian_ordinary_bispectrum_mean(s,m,triangles) for s in raw]
    s=raw.astype(np.complex128);s=.5*s+.5*s.conj().transpose(0,2,1)
    t=checked[0]['triangles'];i,j,k=t.T
    try:
        with np.errstate(over='raise',invalid='raise',under='ignore'):
            a,b,c=s[:,i,j],s[:,j,k],s[:,k,i]
            sa,sb,sc=m*a.sum(axis=0),m*b.sum(axis=0),m*c.sum(axis=0)
            ab,ac,bc=m*(a*b).sum(axis=0),m*(a*c).sum(axis=0),m*(b*c).sum(axis=0)
            abc=m*(a*b*c).sum(axis=0)
            pooled=(sa*sb*sc-ab*sc-ac*sb-bc*sa+2*abc)/(n*(n-1)*(n-2))
            each=a*b*c;average=each.mean(axis=0)
            marginal_power=np.prod(s.diagonal(axis1=1,axis2=2).real[:,t],axis=-1)
    except FloatingPointError as exc:raise ValueError('known group means exceed numerical range') from exc
    positive=(s.diagonal(axis1=1,axis2=2).real[:,t]>0).all(axis=-1)
    if (not np.isfinite(pooled).all() or not np.isfinite(average).all()
        or np.any(positive & (marginal_power<=0))):raise ValueError('known group mean outside numerical range')
    return {'triangles':t.copy(),'groups':len(s),'samples_per_group':m,'pooled_samples':n,
        'per_group_bispectrum_mean':each,'equal_group_u3_mean':average,'pooled_u3_mean':pooled,
        'independent_samples_assumed':True,'constant_covariance_across_groups_assumed':False,
        'generating_covariances_supplied':True,'heterogeneous_group_covariance_calculated':False,
        'frequency_phase_alignment_performed':False,'actual_frequency_independence_verified':False,
        'production_rml_noise_model_changed':False,'real_hardware_validation_performed':False,
        'scope':'Known independent-group pair means only; no observed coaddition, delay/bandpass estimation, heterogeneous covariance or image likelihood.'}
