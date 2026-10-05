"""Known population closure signatures relative to an unresolved point source."""
import numbers
import numpy as np
from vsora_imaging.closure import closure_design, wrap_phase


def population_closure_signature(visibilities, pairs, total_flux_jy):
    """No noise weights, detection threshold, likelihood, or image information rank.

    The numerical floor is 1e-12 of the supplied sky flux. Closures requiring
    an edge at/below this floor have no reported phase/log amplitude value.
    A phase-centred point source has zero phase and zero log closure amplitude.
    """
    if any(np.ma.isMaskedArray(x) for x in (visibilities, pairs, total_flux_jy)):
        raise ValueError('unmasked known population visibility and flux required')
    v=np.asarray(visibilities)
    p=np.asarray(pairs)
    if (v.ndim!=1 or not np.iscomplexobj(v) or not np.isfinite(v).all()
        or p.ndim!=2 or p.shape!=(len(v),2)):
        raise ValueError('finite complex baseline vector and matching pairs required')
    if (isinstance(total_flux_jy,(bool,np.bool_)) or not isinstance(total_flux_jy,numbers.Real)
        or not np.isfinite(total_flux_jy) or total_flux_jy<=0):
        raise ValueError('positive finite supplied sky flux required')
    design=closure_design(p)
    if len(set(p.ravel().tolist()))>8:
        raise ValueError('reference population signature supports up to8 stations')
    flux=float(total_flux_jy);floor=flux*1e-12
    if not np.isfinite(flux) or floor<=0:
        raise ValueError('sky flux outside numerical range')
    try:
        with np.errstate(over='raise',invalid='raise',divide='raise',under='ignore'):
            amplitude=np.abs(v);fraction=amplitude/flux
    except FloatingPointError as exc:
        raise ValueError('population visibility outside numerical range') from exc
    if not np.isfinite(fraction).all():raise ValueError('population visibility outside numerical range')
    baseline_valid=amplitude>floor
    result={'numerical_visibility_floor_jy':floor,
        'baseline_above_numerical_floor':baseline_valid.tolist(),
        'correlated_flux_fraction':fraction.tolist(),
        'phase_unit':'rad','logamp_unit':'1',
        'population_only':True,'noise_or_detection_threshold_applied':False,
        'rows_assumed_statistically_independent':False,
        'image_information_or_confidence_calculated':False}
    for kind,values in [('phase',np.angle(v)),('logamp',np.log(np.where(baseline_valid,amplitude,1.)))]:
        matrix=design[kind+'_matrix']
        valid=np.all(baseline_valid[None,:] | (matrix==0),axis=1)
        output=matrix @ values
        if kind=='phase': output=wrap_phase(output)
        selected=output[valid]
        result[kind+'_values']=[float(x) if ok else None for x,ok in zip(output,valid)]
        result[kind+'_valid']=valid.tolist()
        result[kind+'_valid_rows']=int(valid.sum())
        result[kind+'_rms_from_point']=None if not len(selected) else float(np.sqrt(np.mean(selected**2)))
        result[kind+'_maximum_abs_from_point']=None if not len(selected) else float(np.max(abs(selected)))
    result['triangles']=design['triangles'].tolist()
    result['quadrangles']=design['quadrangles'].tolist()
    return result
