"""Direct Fourier dirty image and PSF with natural weighting.

Output is Jy/dirty-beam for an unresolved source, PSF normalized to one.
"""
import numpy as np
from vsora_observation.geometry import tangent_grid


def dirty_image(uvw_lambda, vis, pixels, pixel_arcsec, weights=None, block_size=128):
    uvw = np.asarray(uvw_lambda).reshape(-1,3)
    visibility = np.asarray(vis).reshape(-1)
    w = np.ones(len(uvw)) if weights is None else np.asarray(weights).reshape(-1)
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
