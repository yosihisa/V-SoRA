"""Small-field Högbom CLEAN reference; no wrapping of PSF at image edges."""
import numpy as np
from scipy.signal import fftconvolve


def shifted_psf(psf, y, x, shape):
    out = np.zeros(shape)
    dy, dx = y-psf.shape[0]//2, x-psf.shape[1]//2
    y0,y1=max(0,dy),min(shape[0],dy+psf.shape[0])
    x0,x1=max(0,dx),min(shape[1],dx+psf.shape[1])
    if y1 > y0 and x1 > x0:
        out[y0:y1,x0:x1]=psf[y0-dy:y1-dy,x0-dx:x1-dx]
    return out


def clean(dirty, psf, gain=.1, threshold=1e-3, max_iterations=2000, mask=None, beam_fwhm_pixels=4.0):
    if dirty.shape != psf.shape or not 0 < gain <= 1 or threshold <= 0 or max_iterations <= 0 or beam_fwhm_pixels <= 0:
        raise ValueError("invalid CLEAN inputs")
    if not np.isfinite(dirty).all() or not np.isfinite(psf).all():
        raise ValueError("nonfinite image")
    if abs(psf[psf.shape[0]//2,psf.shape[1]//2]-1) > 1e-8:
        raise ValueError("PSF center must equal one")
    allowed = np.ones(dirty.shape,dtype=bool) if mask is None else np.asarray(mask,dtype=bool)
    if allowed.shape != dirty.shape or not allowed.any():
        raise ValueError("invalid CLEAN mask")
    residual = dirty.copy()
    model = np.zeros_like(dirty)
    iterations=0
    for k in range(max_iterations):
        abs_residual=np.where(allowed,np.abs(residual),-1)
        y,x=np.unravel_index(np.argmax(abs_residual),dirty.shape)
        if abs(residual[y,x]) <= threshold:
            break
        component=gain*residual[y,x]
        model[y,x]+=component
        residual-=component*shifted_psf(psf,y,x,dirty.shape)
        iterations=k+1
    # Odd-sized, peak-normalized Gaussian: unit point-source flux gives unit peak.
    n=dirty.shape[0]
    axis=np.arange(-n//2,n//2+1)
    yy,xx=np.meshgrid(axis,axis,indexing="ij")
    beam=np.exp(-4*np.log(2)*(xx*xx+yy*yy)/beam_fwhm_pixels**2)
    restored=fftconvolve(model,beam,mode="same")+residual
    return {"model_jy_pixel":model,"residual_jy_dirty_beam":residual,"restored_jy_clean_beam":restored,
            "iterations":iterations,"peak_residual_jy":float(np.max(np.abs(residual[allowed]))),
            "converged":bool(np.max(np.abs(residual[allowed]))<=threshold),"beam_fwhm_pixels":beam_fwhm_pixels,
            "residual_scaling":"Unscaled dirty-beam residual; do not sum restored pixels as total flux"}
