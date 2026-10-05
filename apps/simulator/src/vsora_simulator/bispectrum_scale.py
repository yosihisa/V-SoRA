"""Known iid nonzero-source bispectrum complex-rms scale; no detection test."""
import math
import numpy as np
from .bispectrum_moments import gaussian_distinct_bispectrum_moments


def known_bispectrum_moment_scale(station_covariance,samples,target_scale=5.):
    """|known mean| / sqrt(E|U3-mean|^2), using source-inclusive exact Gamma.

    This uses complex rms, unlike the one-quadrature null scale in stage057.
    A target scale is not a Gaussian detection probability or phase confidence.
    """
    if (isinstance(target_scale,(bool,np.bool_)) or not isinstance(target_scale,(int,float,np.integer,np.floating))
        or not np.isfinite(target_scale) or not 0<target_scale<=100):raise ValueError('finite target complex-rms scale(0,100] required')
    q=gaussian_distinct_bispectrum_moments(station_covariance,samples)
    s=np.asarray(station_covariance)
    if np.any(s.diagonal().real<=0):raise ValueError('positive known station total power required')
    power=np.prod(s.diagonal().real[q['triangles']],axis=1)
    with np.errstate(over='ignore',invalid='ignore',under='ignore'):
        null=power**2/(samples*(samples-1)*(samples-2))
        variance=q['complex_covariance'].diagonal().real
        ratio=np.divide(abs(q['mean']),np.sqrt(variance),out=np.zeros(len(variance)),where=variance>0)
        relative=np.divide(variance,null,out=np.ones(len(variance)),where=null>0)
    if not np.isfinite(ratio).all() or not np.isfinite(relative).all() or np.any((power>0)&(null<=0)):
        raise ValueError('known bispectrum scales outside supported numerical range')
    required=[];states=[]
    for r in ratio:
        if r==0:required.append(None);states.append("zero_numeric_mean")
        else:
            if r<float(target_scale)/1e9:
                required.append(None);states.append("above_supported_count_limit");continue
            count=(float(target_scale)/float(r))**2
            if not np.isfinite(count) or count>1e18:raise ValueError('conditional window count outside supported range')
            required.append(max(1,math.ceil(count)));states.append("finite")
    return {**q,'known_complex_rms_scale':ratio,'complex_to_null_variance_ratio':relative,
        'required_identical_independent_windows':required,'conditional_window_count_state':states,'conditional_count_limit':10**18,'target_complex_rms_scale':float(target_scale),
        'same_sky_covariance_and_uv_repeated_assumed':True,'window_independence_assumed':True,
        'observed_noise_estimation_performed':False,'gaussian_detection_probability_calculated':False,
        'scale_definition':'abs(known B)/sqrt(E abs(U3-B)^2); not a one-quadrature SNR',
        'scope':'Conditional exact known-S iid Gaussian voltage moments including source self-noise; repeated identical independent sky/gain windows only. No actual observation duration, detection probability, phase likelihood or image confidence.'}
