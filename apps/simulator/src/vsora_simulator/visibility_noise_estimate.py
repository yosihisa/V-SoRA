"""Conditional finite-sample covariance estimate from station sample moments."""
import numpy as np
from .visibility_moments import visibility_noise_moments


def estimate_visibility_noise(station_sample_covariance, samples, pairs=None):
    """Estimate mean-visibility noise under iid proper Gaussian voltages.

    S_hat = sum_m x_m x_m^H / M, with known zero mean, no sample-mean
    subtraction and the same M samples for every entry. M >= station count
    ensures PSD of this formula for any valid PSD S_hat. The ensemble mean
    is unbiased under these assumptions; an individual estimate is not the
    true covariance. Quantization, filter correlation, masks and gain drift
    require another model. No generating sky or receiver truth is passed.
    """
    raw=np.asarray(station_sample_covariance)
    if (raw.ndim!=2 or raw.shape[0]!=raw.shape[1] or not 2<=len(raw)<=32
            or isinstance(samples,bool) or not isinstance(samples,(int,np.integer))
            or not len(raw)<=samples<=2**53):
        raise ValueError('square 2..32 station covariance and integer independent samples in station_count..2**53 required')
    q=visibility_noise_moments(raw,int(samples),pairs)
    mean=q['mean'];real_mean=np.r_[mean.real,mean.imag]
    inverse_square=1./float(samples)**2;normalization=1-inverse_square
    with np.errstate(over='ignore',invalid='ignore'):
        gamma=(q['complex_covariance']-np.outer(mean,mean.conj())*inverse_square)/normalization
        pseudo=(q['complex_pseudocovariance']-np.outer(mean,mean)*inverse_square)/normalization
        c=(q['real_covariance']-np.outer(real_mean,real_mean)*inverse_square)/normalization
    if not all(np.isfinite(a).all() for a in (gamma,pseudo,c)):
        raise ValueError('estimated visibility covariance exceeds finite numerical range')
    return {'pairs':q['pairs'],'mean':mean,'complex_covariance':gamma,
        'complex_pseudocovariance':pseudo,'real_covariance':c*.5+c.T*.5,
        'plug_in_real_covariance':q['real_covariance'],
        'real_parameter_order':q['real_parameter_order'],'samples':int(samples),
        'conditional_ensemble_unbiased':True,'generating_truth_used':False,
        'distribution_gaussian_assumed':False,'covariance_inverted':False,
        'model':'Finite-sample correction from station sample covariance of iid zero-mean proper complex Gaussian voltages',
        'limits':'Common independent sample set, known zero mean, no empirical mean subtraction. Conditional ensemble-unbiased estimate, not a true covariance per observation or a calibrated confidence region. ADC/filter/time-channel correlation, masks, gain variation and hardware unverified.'}
