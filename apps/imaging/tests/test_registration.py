import numpy as np
import pytest
from scipy.ndimage import shift
from vsora_imaging.experiment import compare_relative
from vsora_imaging.registration import register_translation


def test_integer_translation_beyond_old_peak_local_search():
    a=np.zeros((32,32));a[12,15]=.7;a[18,20]=.3
    b=shift(a,[7,-8],order=0,mode='constant')
    m,*_=compare_relative(a,b,16)
    np.testing.assert_allclose(m['registration_shift_yx_arcsec'],[-112,128],atol=1e-5)
    assert m['registered_nrmse']<1e-8
    assert m['registered_flux_retained_fraction']==pytest.approx(1,abs=1e-12)
    assert not m['registration_boundary_reached']


def test_continuous_fractional_gaussian_translation():
    y,x=np.indices((48,48));d=np.array([4.35,-6.2])
    a=np.exp(-((y-22)**2+(x-24)**2)/18)
    b=np.exp(-((y-22-d[0])**2+(x-24-d[1])**2)/18)
    m,*_=compare_relative(a,b,16)
    np.testing.assert_allclose(np.array(m['registration_shift_yx_arcsec'])/16,-d,atol=.015)
    assert m['registered_nrmse']<.01
    assert m['registered_flux_retained_fraction']==pytest.approx(1,abs=1e-12)


def test_edge_flux_never_removed_from_error():
    a=np.zeros((32,32));a[16,16]=1
    b=np.zeros_like(a);b[16,16]=.5;b[0,0]=.5
    m,aa,bb,registered=compare_relative(a,b,16,common_beam_arcsec=32)
    assert m['registered_nrmse']>.6
    assert m['registered_flux_retained_fraction']==pytest.approx(1,abs=1e-12)
    assert registered.sum()<.9 # Display crop omits flux; the metric retains it.
    assert m['registration_diagnostics']['objective_identity_error']<1e-12


def test_translation_bound_and_no_translation():
    a=np.zeros((16,16));a[6,7]=1;b=shift(a,[5,0],order=0,mode='constant')
    m,*_=compare_relative(a,b,16,max_shift_pixels=2)
    assert m['registration_boundary_reached']
    assert abs(m['registration_shift_yx_arcsec'][0]+32)<1e-4
    m,*_=compare_relative(a,b,16,max_shift_pixels=0)
    assert m['registered_nrmse']==pytest.approx(m['raw_nrmse'])


@pytest.mark.parametrize('a,b,pixel,beam',[
    (np.zeros((4,4)),np.ones((4,4)),16,110),
    (np.ones((4,4)),np.full((4,4),np.nan),16,110),
    (np.ones((4,4)),np.ones((5,4)),16,110),
    (np.ones((4,4)),-np.ones((4,4)),16,110),
    (np.ones((4,4)),np.ones((4,4)),0,110),
    (np.ones((4,4)),np.ones((4,4)),16,-110),
])
def test_comparison_rejects_invalid_images_and_scales(a,b,pixel,beam):
    with pytest.raises(ValueError):compare_relative(a,b,pixel,beam)


def test_registration_matches_independent_dense_translation_grid():
    rng=np.random.default_rng(30);a=np.zeros((20,20));b=np.zeros_like(a)
    a[8:12,8:12]=rng.uniform(0,1,(4,4));b[7:11,8:12]=rng.uniform(0,1,(4,4))
    registered,info=register_translation(a,b,2)
    numerical=min(np.sum((shift(b,[y,x],order=1,mode='constant',prefilter=False)-a)**2)
        for y in np.arange(-2,2.01,.1) for x in np.arange(-2,2.01,.1))
    assert np.sum((registered-a)**2)<=numerical+1e-10
    assert info['selected_coordinate_converged']
    assert info['objective_identity_error']<1e-12
