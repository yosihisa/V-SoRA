import numpy as np
from vsora_simulator.visibility import direct_visibility
from vsora_imaging.dirty import dirty_image
from vsora_imaging.clean import clean, shifted_psf


def test_point_location_amplitude_and_clean_flux():
    rng=np.random.default_rng(9)
    uvw=np.column_stack([rng.uniform(-3000,3000,size=(500,2)),np.zeros(500)])
    image=np.zeros((32,32));image[18,13]=12
    vis=direct_visibility(uvw,image,16)
    dirty,psf=dirty_image(uvw,vis,32,16)
    assert np.unravel_index(dirty.argmax(),dirty.shape)==(18,13)
    assert abs(dirty[18,13]-12)<1e-10
    assert abs(psf[16,16]-1)<1e-12
    mask=np.zeros_like(image,dtype=bool);mask[18,13]=True
    result=clean(dirty,psf,threshold=1e-6,mask=mask,beam_fwhm_pixels=3)
    assert abs(result['model_jy_pixel'].sum()-12)<1e-5
    assert np.unravel_index(result['restored_jy_clean_beam'].argmax(),image.shape)==(18,13)
    assert result['converged']


def test_two_sources_with_complete_dft_grid():
    # Integer Fourier grid, independent expected dirty=image exactly.
    n=32;pix=16
    from vsora_observation.geometry import ARCSEC_RAD
    freqs=np.fft.fftfreq(n,d=pix*ARCSEC_RAD)
    u,v=np.meshgrid(freqs,freqs)
    uvw=np.column_stack([u.ravel(),v.ravel(),np.zeros(n*n)])
    image=np.zeros((n,n));image[16,12]=6;image[16,20]=4
    dirty,psf=dirty_image(uvw,direct_visibility(uvw,image,pix),n,pix)
    np.testing.assert_allclose(dirty,image,atol=1e-12)
    result=clean(dirty,psf,threshold=1e-6)
    np.testing.assert_allclose(result['model_jy_pixel'],image,atol=1e-6)


def test_psf_shift_has_no_wrap():
    psf=np.zeros((8,8));psf[4,4]=1;psf[0,0]=.5
    shifted=shifted_psf(psf,0,0,(8,8))
    assert shifted[0,0]==1
    assert np.count_nonzero(shifted)==1


def test_float32_weights_psf_normalization():
    uvw=np.ones((448,3))
    weights=np.full(448,.00433333,dtype='float32')
    _,psf=dirty_image(uvw,np.ones(448,complex),32,16,weights)
    assert abs(psf[16,16]-1)<1e-12
