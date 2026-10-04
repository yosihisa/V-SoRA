"""Null-source variance and conditional planning for sample-distinct U3."""
import math
import numpy as np


def null_bispectrum_variance(samples):
    """Exact iid proper Gaussian, three independent unit-power stations."""
    if isinstance(samples,bool) or not isinstance(samples,(int,np.integer)) or not 3<=samples<=1000000:
        raise ValueError('integer independent sample count 3..1000000 required')
    m=int(samples);denominator=m*(m-1)*(m-2)
    return {'samples':m,'ordered_distinct_triples':denominator,
        'complex_variance':1/denominator,'pseudo_covariance':[0.,0.],
        'real_variance':1/(2*denominator),'imaginary_variance':1/(2*denominator),
        'real_imaginary_covariance':0.,'source_cross_covariance_zero':True,
        'independent_unit_power_proper_gaussian_assumed':True,
        'actual_temporal_independence_verified':False,'production_rml_noise_model_changed':False}


def conditional_bispectrum_plan(samples,baseline_coherence_magnitudes,windows=1,target_snr=5.,window_seconds=.3):
    """Null-variance scale only; not a phase likelihood or detection threshold.

    Magnitudes refer to a supplied known unit-power model for i-j, j-k, k-i.
    Identical sky bispectrum/normalization and independent windows assumed.
    """
    q=null_bispectrum_variance(samples)
    if np.ma.isMaskedArray(baseline_coherence_magnitudes):raise ValueError('masked model coherence unsupported')
    raw=np.asarray(baseline_coherence_magnitudes)
    if np.iscomplexobj(raw) or not np.issubdtype(raw.dtype,np.number):raise ValueError('real numeric model coherence magnitudes required')
    rho=raw.astype(float)
    if (rho.shape!=(3,) or not np.isfinite(rho).all() or np.any(rho<0) or np.any(rho>=1)
        or isinstance(windows,bool) or not isinstance(windows,(int,np.integer)) or not 1<=windows<=1000000000
        or isinstance(target_snr,(bool,np.bool_)) or isinstance(window_seconds,(bool,np.bool_))
        or not isinstance(target_snr,(int,float,np.integer,np.floating))
        or not isinstance(window_seconds,(int,float,np.integer,np.floating))
        or not np.isfinite([target_snr,window_seconds]).all()
        or not 0<target_snr<=100 or not .1<=window_seconds<=3):
        raise ValueError('three model magnitudes [0,1), windows1..1e9, target(0,100], exposure0.1..3s required')
    truth=float(np.prod(rho))
    if 1-float(np.dot(rho,rho))+2*truth < -1e-12:
        raise ValueError('coherence magnitudes cannot form a PSD station correlation matrix')
    if np.all(rho>0) and truth<1e-150:raise ValueError('model bispectrum below supported floating range')
    sigma=math.sqrt(q['real_variance']);single=truth/sigma
    required=None if single==0 else max(1,math.ceil((target_snr/single)**2))
    return {'type':'conditional_bispectrum_sensitivity','independent_samples_assumed':q['samples'],
        'known_model_baseline_coherence_magnitudes':rho.tolist(),'known_model_bispectrum_magnitude':truth,
        'windows_assumed':int(windows),'window_seconds':float(window_seconds),
        'null_model_quadrature_sigma_per_window':sigma,
        'single_window_null_variance_snr':single,'stacked_null_variance_snr':single*math.sqrt(windows),
        'target_null_variance_snr':float(target_snr),'required_identical_independent_windows':required,
        'conditional_recorded_seconds':None if required is None else required*window_seconds,
        'nonzero_source_variance_calculated':False,'same_sky_bispectrum_and_normalization_assumed':True,
        'independent_windows_assumed':True,'actual_temporal_independence_verified':False,
        'physical_adc_vdif_processed':False,'real_hardware_validation_performed':False,
        'closure_phase_unbiased_guarantee':False,'image_reconstructed':False,
        'production_rml_noise_model_changed':False,
        'scope':'Exact null Gaussian variance used as conditional scale for supplied sky coherence. Source self-noise, varying uv/gain, frequency stacking, observed normalization and detection probabilities excluded.'}
