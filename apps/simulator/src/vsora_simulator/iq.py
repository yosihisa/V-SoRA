"""Gaussian voltage generator for stationary FFT-periodic snapshots.

This deliberately tests covariance/quantization/FX before continuous tracking.
"""
import numpy as np
from .visibility import direct_visibility


def generate_iq(uvw_lambda,pairs,image,pixel_arcsec,sefd_jy,sample_rate_hz,
                frequency_hz,fft_length=64,blocks=256,seed=1,delay_s=None):
    sefd=np.asarray(sefd_jy,float)
    if np.any(sefd<0) or fft_length<2 or blocks<1: raise ValueError('invalid IQ conditions')
    n=len(sefd)
    freq=frequency_hz+np.fft.fftfreq(fft_length,d=1/sample_rate_hz)
    uvw=np.asarray(uvw_lambda)[None,:,:]*(freq/frequency_hz)[:,None,None]
    vis=direct_visibility(uvw,image,pixel_arcsec)
    cov=np.zeros((fft_length,n,n),complex)
    for b,(i,j) in enumerate(pairs):
        cov[:,i,j]=vis[:,b];cov[:,j,i]=vis[:,b].conj()
    for i in range(n): cov[:,i,i]=image.sum()+sefd[i]
    # Semidefinite source-only matrices are allowed. Clip roundoff, reject a
    # scientifically inconsistent covariance instead of adding silent noise.
    eigen,vec=np.linalg.eigh(cov)
    if eigen.min() < -max(image.sum()+sefd.max(),1)*1e-10:
        raise ValueError('sky covariance not positive semidefinite')
    root=vec*np.sqrt(np.maximum(eigen,0))[:,None,:]
    rng=np.random.default_rng(seed)
    random=(rng.normal(size=(blocks,fft_length,n))+1j*rng.normal(size=(blocks,fft_length,n)))/np.sqrt(2)
    spectrum=np.einsum('kij,bkj->bki',root,random)
    if delay_s is not None:
        # Independently expressed forward delay, separate from correlator code.
        spectrum*=np.exp(2j*np.pi*freq[None,:,None]*np.asarray(delay_s)[None,None,:])
    data=np.fft.ifft(spectrum,axis=1,norm='ortho').transpose(2,0,1).reshape(n,-1)
    return data,vis
