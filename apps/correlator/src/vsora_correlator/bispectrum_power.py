"""Dimensionless ratios from finite raw sums on each triangle's common samples."""
import numpy as np


def normalize_common_power_bispectrum(result):
    """Use the SAME triangle-common FFT set for U3 and all three powers.

    Zero fills are unavailable unless the corresponding boolean is true.
    This array helper does not verify a file, IID modes, ignorable masks,
    within-window station gain constancy, or an image/noise likelihood.
    Raw sums have a narrower numerical range than preconditioned voltages.
    """
    keys=('triangles','common_sample_count','common_station_power_sums',
          'distinct_sample_bispectrum','ordinary_common_sample_product')
    if not isinstance(result,dict) or any(k not in result for k in keys):
        raise ValueError('triangle-common raw products, counts and power sums required')
    if any(np.ma.isMaskedArray(result[k]) for k in keys):raise ValueError('unmasked common sums required')
    t,m,p,u,o=(np.asarray(result[k]) for k in keys)
    if (t.ndim!=2 or t.shape[1]!=3 or not 1<=len(t)<=56 or not np.issubdtype(t.dtype,np.integer)
        or np.any(t<0) or np.any(t>=8) or np.any(t[:,0]>=t[:,1]) or np.any(t[:,1]>=t[:,2])
        or len(np.unique(t,axis=0))!=len(t)):
        raise ValueError('unique canonical station triangles i<j<k, up to8 stations required')
    if (m.shape!=(len(t),) or not np.issubdtype(m.dtype,np.integer) or np.any(m<0) or np.any(m>1000000)):
        raise ValueError('integer common sample counts0..1e6 required')
    if (p.ndim!=3 or p.shape[1:]!=(len(t),3) or not 1<=len(p)<=4096
        or not np.issubdtype(p.dtype,np.number) or np.iscomplexobj(p) or not np.isfinite(p).all() or np.any(p<0)):
        raise ValueError('finite nonnegative real [channel,triangle,3] common power sums required')
    if any(a.shape!=p.shape[:2] or not np.iscomplexobj(a) or not np.isfinite(a).all() for a in (u,o)):
        raise ValueError('finite complex raw products with [channel,triangle] shape required')
    with np.errstate(over='ignore',invalid='ignore'):
        pf=p.astype(np.float64,copy=False);uf=u.astype(np.complex128,copy=False);of=o.astype(np.complex128,copy=False)
    if (not np.isfinite(pf).all() or not np.isfinite(uf).all() or not np.isfinite(of).all()
        or np.any((p!=0)&(pf==0)) or np.any((u.real!=0)&(uf.real==0)) or np.any((u.imag!=0)&(uf.imag==0))
        or np.any((o.real!=0)&(of.real==0)) or np.any((o.imag!=0)&(of.imag==0))):
        raise ValueError('raw components must remain finite and nonzero when converted to float64')
    zero=m==0
    if np.any(pf[:,zero]!=0) or np.any(uf[:,zero]!=0) or np.any(of[:,zero]!=0):
        raise ValueError('zero-count common sums must be zero')
    if np.any(uf[:,m<3]!=0):raise ValueError('unavailable M<3 raw U3 must use zero fill')
    quality=result.get('channel_triangle_usable')
    if quality is not None:
        if np.ma.isMaskedArray(quality):raise ValueError('unmasked boolean existing quality mask required')
        quality=np.asarray(quality)
        if quality.dtype!=np.bool_ or quality.shape!=pf.shape[:2]:raise ValueError('boolean existing quality mask must match channel and triangle axes')
    positive=np.all(pf>0,axis=-1)
    if np.any((~positive)&((uf!=0)|(of!=0))):raise ValueError('zero empirical power is inconsistent with nonzero products')
    available=positive&(m[None,:]>=3);ordinary_available=positive&(m[None,:]>0)
    # Frexp avoids forming a potentially overflowing or underflowing product
    # of three empirical powers, even when the final ratio is representable.
    mantissa,exponents=np.frexp(np.where(pf>0,pf,1.))
    denominator_mantissa=np.prod(mantissa,axis=-1);denominator_exponent=exponents.sum(axis=-1)
    factor=m.astype(float)[None,:]**3/denominator_mantissa
    def divide(value,valid):
        components=[]
        for component in (value.real,value.imag):
            f,e=np.frexp(component)
            with np.errstate(over='ignore',under='ignore',invalid='ignore'):
                v=np.ldexp(f*factor,e-denominator_exponent)
            if np.any(valid&(~np.isfinite(v)|((component!=0)&(v==0)))):
                raise ValueError('normalized raw ratio outside representable float64 range')
            components.append(np.where(valid,v,0.))
        return components[0]+1j*components[1]
    return {'triangles':t.copy(),'common_sample_count':m.copy(),
        'observed_power_normalized_u3':divide(uf,available),
        'observed_power_normalized_ordinary_product':divide(of,ordinary_available),
        'u3_available':available,'ordinary_available':ordinary_available,
        'triangle_common_power_positive':positive,
        'existing_quality_mask_supplied':quality is not None,
        'channel_triangle_usable':None if quality is None else quality.copy(),
        'normalized_u3_existing_quality_usable':None if quality is None else available&quality,
        'normalization_uses_triangle_common_samples':True,'same_fixed_mask_gain_cancels_algebraically':True,
        'input_sample_independence_verified':False,'input_mask_independence_verified':False,
        'source_file_identity_verified':False,'raw_voltage_preconditioning_applied':False,
        'finite_sample_unbiased_guarantee':False,'known_power_moment_formula_applied':False,
        'unknown_lo_estimated':False,'production_rml_noise_model_changed':False,
        'real_hardware_validation_performed':False,
        'scope':'Dimensionless finite-data ratio from matching triangle-common raw sums; '
                'zero fills require explicit availability booleans. Fixed masks and gains '
                'constant within a window are algebraic assumptions, not verified observing conditions. '
                'Raw underflow or overflow cannot be recovered; no phase or image likelihood.'}
