"""Forward known-sky station covariance; no observed normalization or beam model."""
import numpy as np
from vsora_observation.geometry import tangent_grid


def sky_station_covariance(station_uvw_lambda,image,pixel_arcsec,receiver_sefd_jy):
    """Same scalar sky at every station, independent background receiver noise.

    Receiver SEFD excludes target source power. Visibility convention uses
    baseline r_j-r_i and exp(-2pi i b.d); station response has positive phase.
    All supplied sky pixels are nonnegative Jy/pixel model values.
    """
    if any(np.ma.isMaskedArray(x) for x in (station_uvw_lambda,image,receiver_sefd_jy)):
        raise ValueError('unmasked known station coordinates, sky and SEFD required')
    coords=np.asarray(station_uvw_lambda);sky=np.asarray(image);noise=np.asarray(receiver_sefd_jy)
    if (coords.ndim!=2 or coords.shape[1]!=3 or not 3<=len(coords)<=8
        or np.iscomplexobj(coords) or not np.issubdtype(coords.dtype,np.number) or not np.isfinite(coords).all()):
        raise ValueError('finite real3..8 station uvw wavelength coordinates required')
    if (sky.ndim!=2 or sky.shape[0]!=sky.shape[1] or not 2<=len(sky)<=128
        or np.iscomplexobj(sky) or not np.issubdtype(sky.dtype,np.number) or not np.isfinite(sky).all() or np.any(sky<0)):
        raise ValueError('nonnegative finite real square2..128 Jy/pixel sky required')
    if (noise.shape!=(len(coords),) or np.iscomplexobj(noise) or not np.issubdtype(noise.dtype,np.number)
        or not np.isfinite(noise).all() or np.any(noise<=0)):
        raise ValueError('positive finite real receiver/background SEFD per station required')
    if (isinstance(pixel_arcsec,(bool,np.bool_)) or not isinstance(pixel_arcsec,(int,float,np.integer,np.floating))
        or not np.isfinite(pixel_arcsec) or pixel_arcsec<=0):raise ValueError('positive finite model pixel size required')
    l,m=tangent_grid(len(sky),float(pixel_arcsec));select=sky>0
    lm=np.c_[l[select],m[select]]
    directions=np.c_[lm,np.sqrt(1-(lm**2).sum(axis=1))-1]
    try:
        with np.errstate(over='raise',invalid='raise',under='ignore'):
            relative=coords.astype(float)-coords[0].astype(float)
            phase=2*np.pi*(relative @ directions.T)
            response=np.exp(1j*phase)*np.sqrt(sky[select])[None,:]
            source=response @ response.conj().T
            s=source+np.diag(noise.astype(float))
            power=s.diagonal().real
            root=np.sqrt(power);normal=s/root[:,None]/root[None,:]
            total=float(sky.sum())
    except FloatingPointError as exc:raise ValueError('known sky covariance outside numerical range') from exc
    if not np.isfinite(s).all() or not np.isfinite(normal).all() or not np.isfinite(total) or np.any(power<=0):
        raise ValueError('known sky covariance outside finite positive-power range')
    s=.5*s+.5*s.conj().T;normal=.5*normal+.5*normal.conj().T
    np.fill_diagonal(normal,1.)
    return {'station_covariance_jy':s,'normalized_station_covariance':normal,'source_covariance_jy':source,
        'known_station_total_power_jy':power.copy(),'assumed_source_total_flux_jy':total,
        'receiver_background_sefd_jy':noise.astype(float).copy(),'voltage_model':'zero-mean proper Gaussian, supplied known covariance',
        'target_source_power_added_to_receiver_background':True,'common_scalar_beam_assumed':True,
        'observed_power_normalization_performed':False,'actual_hardware_data':False,
        'scope':'Forward nonnegative discrete sky and independent receiver/background power; no measured SEFD, beam/polarization differences, bandpass, clocks, quantization or image inference.'}
