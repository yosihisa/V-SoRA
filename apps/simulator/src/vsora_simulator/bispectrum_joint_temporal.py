"""Finite known proper-Gaussian station/time covariance: bispectrum means only."""
from itertools import permutations,product
import numpy as np
from vsora_simulator.bispectrum_distinct import gaussian_ordinary_bispectrum_mean


def joint_temporal_bispectrum_mean(joint_covariance,triangles=None):
    """C[t,i,u,j]=E[x[t,i] conj(x[u,j])], time-major,3..32times/3..8stations.

    Sum all six proper Gaussian contractions over ordered time triples.
    Known means only; no unknown covariance, phase/rate estimate or likelihood.
    """
    if np.ma.isMaskedArray(joint_covariance) or np.ma.isMaskedArray(triangles):
        raise ValueError('unmasked joint covariance and triangles required')
    raw=np.asarray(joint_covariance)
    if (raw.ndim!=4 or raw.shape[:2]!=raw.shape[2:] or not 3<=raw.shape[0]<=32
        or not 3<=raw.shape[1]<=8 or raw.dtype.kind not in 'iufc' or not np.isfinite(raw).all()):
        raise ValueError('finite numeric covariance axes(time,station,time,station) required')
    m,n=raw.shape[:2]
    with np.errstate(over="ignore",invalid="ignore"):
        c=raw.astype(complex,copy=True).reshape(m*n,m*n)
    if not np.isfinite(c).all():raise ValueError("joint covariance outside complex128 range")
    scale=max(float(np.max(abs(c))),np.finfo(float).tiny)
    if not np.allclose(c,c.conj().T,rtol=0,atol=1e-12*scale):raise ValueError('Hermitian joint covariance required')
    c=.5*c+.5*c.conj().T
    if np.linalg.eigvalsh(c).min() < -1e-10*scale:raise ValueError('positive semidefinite joint covariance required')
    t=gaussian_ordinary_bispectrum_mean(np.eye(n),m,triangles)['triangles']
    marginal=c.diagonal().real.reshape(m,n)
    with np.errstate(over='ignore',invalid='ignore',under='ignore'):
        power=np.prod(marginal[:,t],axis=-1)
    if not np.isfinite(power).all() or np.any((marginal[:,t]>0).all(axis=-1)&(power<=0)):
        raise ValueError('joint bispectrum power product outside finite range')
    joint=c.reshape(m,n,m,n);instant=np.empty((m,len(t)),complex)
    time_index=np.arange(m)
    with np.errstate(over='ignore',invalid='ignore',under='ignore'):
        for i,(a,b,d) in enumerate(t):
            instant[:,i]=joint[time_index,a,time_index,b]*joint[time_index,b,time_index,d]*joint[time_index,d,time_index,a]
    def calculate(time_triples):
        times=np.asarray(time_triples,dtype=int);result=np.empty(len(t),complex)
        for i,triangle in enumerate(t):
            positive=times*n+triangle[None,:]
            negative=times*n+triangle[[1,2,0]][None,:]
            total=np.zeros(len(times),complex)
            with np.errstate(over='ignore',invalid='ignore',under='ignore'):
                for p in permutations(range(3)):
                    term=np.ones(len(times),complex)
                    for k in range(3):term*=c[positive[:,k],negative[:,p[k]]]
                    total+=term
                result[i]=total.mean()
        return result
    ordinary=calculate(list(product(range(m),repeat=3)))
    distinct=calculate(list(permutations(range(m),3)))
    if not all(np.isfinite(v).all() for v in (instant,ordinary,distinct)):
        raise ValueError('joint bispectrum mean outside finite range')
    return {'triangles':t.copy(),'samples':m,'stations':n,'joint_covariance_axis_order':'time,station,time,station',
        'instantaneous_population_bispectrum':instant,'mean_instantaneous_population_bispectrum':instant.mean(axis=0),
        'ordinary_bispectrum_mean':ordinary,'distinct_bispectrum_mean':distinct,
        'proper_gaussian_contractions':6,'distinct_ordered_time_triples':m*(m-1)*(m-2),'ordinary_ordered_time_triples':m**3,
        'joint_covariance_supplied':True,'common_separable_space_time_covariance_required':False,
        'variance_or_likelihood_calculated':False,'observed_gain_or_clock_estimated':False,
        'actual_temporal_independence_verified':False,'physical_adc_vdif_processed':False,
        'production_rml_noise_model_changed':False,'real_hardware_validation_performed':False,
        'scope':'Known zero-mean proper Gaussian joint station/time covariance; exact finite means only. No unknown covariance/rate, masks, quantization, empirical bias correction, variance, likelihood or image guarantee.'}
