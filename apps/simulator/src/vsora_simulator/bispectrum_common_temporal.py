"""Population bispectrum means for known separable Gaussian space/time covariance."""
import numpy as np
from .bispectrum_distinct import gaussian_ordinary_bispectrum_mean


def common_temporal_bispectrum_mean(station_covariance,temporal_covariance,triangles=None):
    """E[x_i(t) conj(x_j(u))]=S[i,j]*K[t,u], common constant-power K.

    Only exact conditional means of ordinary and distinct-index products.
    No estimator of unknown S/K, variance, likelihood or physical FIR evidence.
    """
    if any(np.ma.isMaskedArray(v) for v in (station_covariance,temporal_covariance,triangles)):
        raise ValueError('unmasked known station/time covariances and triangles required')
    raw=np.asarray(temporal_covariance)
    if raw.ndim!=2 or raw.shape[0]!=raw.shape[1] or not 3<=len(raw)<=256 or not np.isfinite(raw).all():
        raise ValueError('finite square temporal covariance with3..256 samples required')
    k=raw.astype(complex,copy=True);scale=max(float(np.max(abs(k))),np.finfo(float).tiny)
    if not np.allclose(k,k.conj().T,rtol=0,atol=1e-12*scale):raise ValueError('Hermitian temporal covariance required')
    k=.5*k+.5*k.conj().T
    if np.linalg.eigvalsh(k).min() < -1e-10*scale:raise ValueError('positive semidefinite temporal covariance required')
    r0=float(k.diagonal().real.mean())
    if r0<=0 or not np.allclose(k.diagonal().real,r0,rtol=0,atol=1e-12*scale):
        raise ValueError('positive constant temporal diagonal required')
    m=len(k);checked=gaussian_ordinary_bispectrum_mean(station_covariance,m,triangles)
    s=np.asarray(station_covariance,dtype=complex);s=.5*s+.5*s.conj().T
    t=checked['triangles'];i,j,l=t.T
    true=s[i,j]*s[j,l]*s[l,i]
    d=s[i,i].real*abs(s[j,l])**2+s[j,j].real*abs(s[i,l])**2+s[l,l].real*abs(s[i,j])**2
    p=s[i,i].real*s[j,j].real*s[l,l].real
    off=k.copy();np.fill_diagonal(off,0)
    try:
        with np.errstate(over='ignore',invalid='ignore',under='ignore'):
            marginal_power=r0*s.diagonal().real
            power_product=np.prod(marginal_power[t],axis=1)
            if np.any((marginal_power[t]>0).all(axis=1)&(power_product<=0)):
                raise ValueError('known temporal bispectrum power product underflow')
            pairs=float(np.sum(abs(off)**2));cycles=float(np.trace(off @ off @ off).real)
            target=r0**3*true
            pair_bias=r0*d*pairs/(m*(m-1))
            cycle_bias=(p+true.conj())*cycles/(m*(m-1)*(m-2))
            distinct=target+pair_bias+cycle_bias
            trace2=pairs+m*r0**2;trace3=cycles+3*r0*pairs+m*r0**3
            ordinary=target+r0*d*trace2/m**2+(p+true.conj())*trace3/m**3
    except (OverflowError,FloatingPointError) as exc:
        raise ValueError('known temporal bispectrum mean outside finite range') from exc
    if not all(np.isfinite(v).all() for v in (target,pair_bias,cycle_bias,distinct,ordinary)) or not np.isfinite(pairs+cycles):
        raise ValueError('known temporal bispectrum mean outside finite range')
    return {'triangles':t.copy(),'samples':m,'temporal_diagonal_power':r0,
        'off_diagonal_pair_sum':pairs,'distinct_time_cycle_sum':cycles,
        'true_marginal_bispectrum':target,'distinct_pair_bias':pair_bias,'distinct_cycle_bias':cycle_bias,
        'distinct_bispectrum_mean':distinct,'ordinary_bispectrum_mean':ordinary,
        'station_covariance_supplied':True,'temporal_covariance_supplied':True,
        'common_separable_space_time_covariance_assumed':True,'constant_temporal_power_required':True,
        'actual_temporal_independence_verified':False,'physical_raw_filter_convolution_performed':False,
        'real_hardware_validation_performed':False,'variance_or_likelihood_calculated':False,
        'production_correlator_statistics_changed':False,'production_rml_noise_model_changed':False,
        'scope':'Known zero-mean proper Gaussian voltage with common separable S times K, constant positive temporal power. Means only, not an observed bias correction, variance, distinct station kernels, LO estimation, masking, ADC/FIR/VDIF or image confidence.'}
