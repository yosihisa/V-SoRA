"""Known Gaussian independent receiver stations with temporal covariance."""
import numpy as np
from scipy.linalg import toeplitz


def white_filter_temporal_covariance(kernel,stride,samples):
    """Exact covariance of y[a]=sum_r h[r] x[aH+r] for iid unit white x."""
    if np.ma.isMaskedArray(kernel):raise ValueError('masked filter coefficients are unsupported')
    h=np.asarray(kernel)
    if (h.ndim!=1 or not 1<=len(h)<=4096 or not np.isfinite(h).all()
            or isinstance(stride,bool) or not isinstance(stride,(int,np.integer)) or stride<1
            or isinstance(samples,bool) or not isinstance(samples,(int,np.integer)) or not 3<=samples<=256):
        raise ValueError('finite 1..4096 tap kernel, positive integer stride, integer samples 3..256 required')
    h=h.astype(np.complex128,copy=False);r=np.zeros(samples,complex)
    with np.errstate(over='ignore',invalid='ignore'):
        r[0]=np.sum(abs(h)**2)
        for d in range(1,min(samples,(len(h)-1)//stride+1)):
            offset=d*stride;r[d]=np.sum(h[:-offset]*h[offset:].conj())
    if not np.isfinite(r).all() or r[0].real<=0:raise ValueError('positive finite filter energy and covariance required')
    return toeplitz(r)


def temporal_receiver_bispectrum_mean(temporal_covariances):
    """Zero astronomical cross-covariance, independent Gaussian stations only.

    K_i[a,b]=E[y_i[a] conj(y_i[b])], arbitrary PSD Hermitian temporal K.
    Reports exact mean under supplied known covariance, not an observation
    noise correction. Cross-station independence is an imposed assumption.
    """
    if np.ma.isMaskedArray(temporal_covariances):raise ValueError('masked temporal covariance is unsupported')
    raw=np.asarray(temporal_covariances)
    if (raw.ndim!=3 or raw.shape[0]!=3 or raw.shape[1]!=raw.shape[2]
            or not 3<=raw.shape[1]<=256 or not np.isfinite(raw).all()):
        raise ValueError('three finite square temporal covariances, samples 3..256 required')
    k=raw.astype(np.complex128,copy=True)
    for index,matrix in enumerate(k):
        scale=max(float(np.max(abs(matrix))),np.finfo(float).tiny)
        if not np.allclose(matrix,matrix.conj().T,rtol=1e-10,atol=1e-12*scale):
            raise ValueError('temporal covariance must be Hermitian')
        k[index]=.5*matrix+.5*matrix.conj().T
        if np.linalg.eigvalsh(k[index]).min() < -1e-10*scale:
            raise ValueError('temporal covariance must be positive semidefinite')
    m=k.shape[1];diag=k.diagonal(axis1=-2,axis2=-1)
    with np.errstate(over='ignore',invalid='ignore'):
        p02=k[0] @ k[2];p21=k[2] @ k[1];p10=k[1] @ k[0]
        total=np.trace(p02 @ k[1]);ab=np.sum(diag[1]*np.diag(p02))
        ac=np.sum(diag[0]*np.diag(p21));bc=np.sum(diag[2]*np.diag(p10));abc=np.sum(np.prod(diag,axis=0))
        ordinary=total/m**3;distinct=(total-ab-ac-bc+2*abc)/(m*(m-1)*(m-2))
    if not np.isfinite(ordinary) or not np.isfinite(distinct):raise ValueError('temporal bispectrum mean exceeds finite range')
    return {'samples':m,'ordinary_bispectrum_mean':complex(ordinary),'distinct_bispectrum_mean':complex(distinct),
        'true_astronomical_bispectrum':0j,'temporal_covariance_supplied':True,
        'station_noise_independence_assumed':True,'actual_temporal_independence_verified':False,
        'real_hardware_validation_performed':False,'production_rml_noise_model_changed':False}
