"""Discrete sky in Jy/pixel on an east/north direction-cosine grid."""
import numpy as np
from vsora_observation.geometry import tangent_grid, ARCSEC_RAD


def synthetic_sky(config):
    size = config["image"]["pixels"]
    pixel = config["image"]["pixel_arcsec"]
    l, m = tangent_grid(size, pixel)
    image = np.zeros((size, size))
    source = config["source"]
    model = source["model"]
    if model == "point":
        image[size//2, size//2] = 1
    elif model == "double":
        # Two on-grid point sources with a reproducible flux ratio.
        offset = max(1, round(80/pixel))
        if offset >= size//2:
            raise ValueError("double source outside field")
        image[size//2, size//2-offset] = .6
        image[size//2, size//2+offset] = .4
    elif model == "shell":
        radius = np.hypot(l, m) / ARCSEC_RAD
        image[(radius >= 95) & (radius <= 150)] = 1
    else:
        return casa_sky(config)
    if image.sum() == 0:
        raise ValueError("model contains no flux in the field")
    return image / image.sum() * source["total_flux_jy"]


def components(image, pixel_arcsec):
    l, m = tangent_grid(image.shape[0], pixel_arcsec)
    select = image != 0
    return np.column_stack([l[select], m[select]]), image[select]


def casa_sky(config):
    """Flux-conserving nearest-pixel binning with FK5 -> ICRS conversion.

    Use a 200 arcsec circular region, discard negative noise pixels, then
    normalize the shape to the explicitly assumed total flux.
    """
    import astropy.units as u
    from astropy.coordinates import SkyCoord, FK5
    from astropy.time import Time
    from astropy.io import fits
    from astropy.wcs import WCS
    from vsora_observation.reference import reference_path
    data,h=fits.getdata(reference_path(),header=True)
    if h['BUNIT']!='Jy/pixel': raise ValueError('reference unit mismatch')
    yy,xx=np.indices(data.shape)
    ra,dec=WCS(h).celestial.pixel_to_world_values(xx,yy)
    sky=SkyCoord(ra*u.deg,dec*u.deg,frame=FK5(equinox=Time('J2000'))).icrs
    ra0,dec0=np.deg2rad([config['source']['ra_deg'],config['source']['dec_deg']])
    delta=sky.ra.rad-ra0
    l=np.cos(sky.dec.rad)*np.sin(delta)
    m=np.sin(sky.dec.rad)*np.cos(dec0)-np.cos(sky.dec.rad)*np.sin(dec0)*np.cos(delta)
    n=config['image']['pixels'];pixel=config['image']['pixel_arcsec']*ARCSEC_RAD
    ix=np.rint(l/pixel+n//2).astype(int);iy=np.rint(m/pixel+n//2).astype(int)
    selected=(np.hypot(l,m)<=200*ARCSEC_RAD)&(data>0)&(ix>=0)&(ix<n)&(iy>=0)&(iy<n)
    image=np.zeros((n,n))
    np.add.at(image,(iy[selected],ix[selected]),data[selected])
    if image.sum()<=0: raise ValueError('Cas A outside image field')
    return image/image.sum()*config['source']['total_flux_jy']
