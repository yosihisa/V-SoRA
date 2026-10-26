"""点fluxの集約と、既存SNRを借りた同格子対照の成立条件。"""
from itertools import combinations
import numpy as np
import pytest
from workflows.matched_grid_image_validation import quantize_truth8,point_sum_visibility,transport_diagnostic
from workflows.image_grid_validation import embed_on_32
from workflows.image_control_validation import idealize_visibility
from vsora_simulator.visibility import direct_visibility


def test_quantization_conserves_flux_coordinates_and_positive_ties():
    image=np.zeros((32,32));image[16,16]=2.;image[14,14]=3.;image[12,18]=4.;image[4,4]=1.;before=image.copy();q=quantize_truth8(image)
    assert q.sum()==10. and q[4,4]==5. and q[3,5]==4. and q[1,1]==1. and np.count_nonzero(q)==3
    np.testing.assert_array_equal(image,before)


def test_points_already_on_coarse_grid_roundtrip_exactly():
    coarse=np.zeros((8,8));coarse[0,0]=2.;coarse[7,7]=3.;coarse[3,5]=7.
    np.testing.assert_array_equal(quantize_truth8(embed_on_32(coarse)),coarse)


@pytest.mark.parametrize('position',[(30,16),(16,31),(31,31)])
def test_positive_outside_grid_is_rejected_instead_of_clipped(position):
    image=np.zeros((32,32));image[position]=1.
    with pytest.raises(ValueError,match='leave'):quantize_truth8(image)


@pytest.mark.parametrize('image',[np.zeros((32,32)),-np.ones((32,32)),np.full((32,32),np.nan),np.ones((31,32)),np.ones((32,32),complex),np.full((32,32),'bad')])
def test_invalid_generating_sky_is_rejected(image):
    with pytest.raises(ValueError):quantize_truth8(image)


def test_independent_point_sum_has_correct_phase_sign_and_w_term():
    coarse=np.zeros((8,8));coarse[4,5]=3.;coarse[3,4]=2.;coarse[4,4]=1.
    uvw=np.array([[[[17.,-31.,100.],[1100.,500.,-900.]]]])
    a=direct_visibility(uvw,coarse,64.);b=point_sum_visibility(uvw,coarse);np.testing.assert_allclose(a,b,rtol=2e-14,atol=1e-14)
    center=np.zeros((8,8));center[4,4]=7.;np.testing.assert_array_equal(point_sum_visibility(uvw,center),np.full((1,1,2),7+0j))
    one=np.zeros((8,8));one[4,5]=1.;delta=64*np.pi/(180*3600);probe=np.array([[[[1/(4*delta),0.,0.]]]])
    np.testing.assert_allclose(point_sum_visibility(probe,one),-1j,atol=1e-14)


def test_transport_preserves_masks_covariance_counts_and_original_arrays():
    pairs=np.array(list(combinations(range(4),2)));v=np.exp(1j*np.linspace(-.1,.1,6))[None,None]*100.;w=np.ones(v.shape);uvw=np.zeros((*v.shape,3));old={'visibilities':v,'weights':w,'pairs':pairs,'uvw_lambda':uvw}
    model=(2+3j)*np.ones(v.shape);values,weights=idealize_visibility(v,w,model);q,arrays=transport_diagnostic(old,{**old,'visibilities':values,'weights':weights})
    assert q['independent_counts']=={'phase':3,'logamp':2} and q['valid_baseline_cells']==6 and q['maximum_relative_snr_difference']<1e-12
    assert not q['physical_noise_calibration_measured']
    np.testing.assert_array_equal(v,old['visibilities']);np.testing.assert_array_equal(arrays['old_snr'],arrays['new_snr'])


def test_changed_noise_scale_cannot_pass_fixed_transport_check():
    pairs=np.array(list(combinations(range(4),2)));old={'visibilities':np.ones((1,1,6),complex)*100,'weights':np.ones((1,1,6)),'pairs':pairs}
    with pytest.raises(AssertionError):transport_diagnostic(old,{**old,'weights':old['weights']*2})


def test_off_axis_point_checks_grouped_direction_cosine_with_large_w():
    # sqrt(1-(l²+m²))と逐次減算にはulp差があり、large wで増幅する。
    sky=np.zeros((8,8));sky[3,5]=1.3;sky[2,6]=2.7
    uvw=np.array([[[[17.,-31.,3000.],[1100.,500.,-900.]]]])
    np.testing.assert_allclose(point_sum_visibility(uvw,sky),direct_visibility(uvw,sky,64.),rtol=2e-14,atol=1e-14)
