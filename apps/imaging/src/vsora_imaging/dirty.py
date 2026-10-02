"""Direct Fourier dirty image and PSF with natural weighting.

Output is Jy/dirty-beam for an unresolved source, PSF normalized to one.
"""
import numpy as np
from vsora_observation.geometry import tangent_grid


def dirty_image(uvw_lambda, vis, pixels, pixel_arcsec, weights=None, block_size=128):
    uvw = np.asarray(uvw_lambda,dtype=np.float64).reshape(-1,3)
    visibility = np.asarray(vis,dtype=np.complex128).reshape(-1)
    w = np.ones(len(uvw)) if weights is None else np.asarray(weights,dtype=np.float64).reshape(-1)
    if len(visibility) != len(uvw) or len(w) != len(uvw):
        raise ValueError("visibility and uvw lengths differ")
    if not np.isfinite(uvw).all() or not np.isfinite(visibility).all() or not np.isfinite(w).all() or np.any(w < 0) or w.sum() <= 0:
        raise ValueError("invalid visibility or weights")
    l, m = tangent_grid(pixels, pixel_arcsec)
    dirs = np.column_stack([l.ravel(), m.ravel(), np.sqrt(1-l.ravel()**2-m.ravel()**2)-1])
    dirty = np.zeros(pixels*pixels)
    psf = np.zeros_like(dirty)
    for start in range(0,len(uvw),block_size):
        phase = np.exp(2j*np.pi*(uvw[start:start+block_size] @ dirs.T))
        dirty += np.real((w[start:start+block_size]*visibility[start:start+block_size]) @ phase)
        psf += np.real(w[start:start+block_size] @ phase)
    return dirty.reshape(pixels,pixels)/w.sum(), psf.reshape(pixels,pixels)/w.sum()


def point_response(uvw_lambda,weights,pixels,pixel_arcsec,y,x,block_size=128):
    """Exact normal-operator column, including w and full image boundaries."""
    uvw=np.asarray(uvw_lambda,dtype=np.float64).reshape(-1,3)
    w=np.asarray(weights,dtype=np.float64).reshape(-1)
    l,m=tangent_grid(pixels,pixel_arcsec)
    dirs=np.column_stack([l.ravel(),m.ravel(),np.sqrt(1-l.ravel()**2-m.ravel()**2)-1])
    displacement=dirs-dirs[y*pixels+x]
    image=np.zeros(pixels*pixels)
    for first in range(0,len(uvw),block_size):
        phase=np.exp(2j*np.pi*(uvw[first:first+block_size]@displacement.T))
        image+=np.real(w[first:first+block_size]@phase)
    return image.reshape(pixels,pixels)/w.sum()
