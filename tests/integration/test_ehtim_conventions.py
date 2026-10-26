"""外部形式への変換で鏡像・半画素・誤差係数・maskを失わないこと。"""
from copy import deepcopy
import numpy as np
import pytest
from workflows.ehtim_conventions_validation import image_transfer, spectral_channels, structured_time_groups, w_phase_bound, fixed_inputs
from vsora_observation.geometry import ARCSEC_RAD
from vsora_simulator.visibility import direct_visibility


@pytest.mark.parametrize('pixels',[8,9])
@pytest.mark.parametrize('offset',[(0,0),(1,0),(0,1),(-1,2)])
def test_displaced_point_matches_independent_fourier(pixels,offset):
    dx,dy=offset;image=np.zeros((pixels,pixels));image[pixels//2+dy,pixels//2+dx]=1
    uvw=np.array([[100.,200.,0.],[-700.,150.,0.],[0.,0.,0.]])
    converted,uv,correction=image_transfer(image,uvw,64.)
    y,x=np.nonzero(converted);n=pixels
    x_eht=((n-1)/2-x[0])*64*ARCSEC_RAD;y_eht=((n-1)/2-y[0])*64*ARCSEC_RAD
    sample=np.exp(2j*np.pi*(uv[:,0]*x_eht+uv[:,1]*y_eht))
    expected=np.exp(-2j*np.pi*64*ARCSEC_RAD*(uvw[:,0]*dx+uvw[:,1]*dy))
    np.testing.assert_allclose(sample*correction,expected,atol=2e-15)
    assert converted.sum()==1 and converted is not image
    if pixels%2==0:assert np.max(abs(sample-expected))>.01
    else:np.testing.assert_allclose(correction,1,atol=0)


@pytest.mark.parametrize('image,pixel',[(np.zeros((8,8)),16.),(-np.ones((8,8)),16.),(np.ones((8,9)),16.),(np.full((8,8),np.nan),16.),(np.ones((8,8)),0.),(np.ones((8,8)),float('nan')),(np.ones((8,8)),1e8)])
def test_invalid_image_reference_is_rejected(image,pixel):
    with pytest.raises(ValueError):image_transfer(image,np.ones((2,3)),pixel)


def data():
    pairs,positions,frequencies,times,uvw=fixed_inputs()
    return {'visibilities':np.full(uvw.shape[:-1],10+2j),'weights':np.full(uvw.shape[:-1],4.),'pairs':pairs,
            'times_s':times,'frequencies_hz':frequencies,'uvw_lambda':uvw}


def test_frequency_groups_mask_and_quadrature_sigma_are_preserved():
    d=data();d['weights'][0,0,0]=0.;d['weights'][1,1,2]=.01
    before=deepcopy(d);groups=spectral_channels(d,relative_scale=3.)
    assert [len(g['vis_relative']) for g in groups]==[11,11,12]
    assert [g['frequency_hz'] for g in groups]==d['frequencies_hz'].tolist()
    for f,g in enumerate(groups):
        t,b=g['time_index'],g['baseline_index']
        np.testing.assert_array_equal(g['vis_relative'],3*d['visibilities'][t,f,b])
        np.testing.assert_array_equal(g['sigma_relative_per_quadrature'],np.full(len(t),1.5))
        np.testing.assert_array_equal(g['uv_eht'],-d['uvw_lambda'][t,f,b,:2])
        np.testing.assert_array_equal(g['pairs'],d['pairs'][b])
    for k in d:np.testing.assert_array_equal(d[k],before[k])


@pytest.mark.parametrize('scale,snr',[(0,10),(-1,10),(True,10),(float('nan'),10),(1,4),(1,True),(1,float('inf'))])
def test_unsafe_relative_scale_and_snr_are_rejected(scale,snr):
    with pytest.raises(ValueError):spectral_channels(data(),relative_scale=scale,min_snr=snr)


@pytest.mark.parametrize('field',['uvw_lambda','weights'])
def test_complex_values_cannot_be_silently_cast_into_external_real_fields(field):
    d=data();d[field]=d[field].astype(complex)+1j
    with pytest.raises(ValueError,match='real spectral'):spectral_channels(d)


def test_all_masked_channel_stays_empty_and_is_not_filled():
    d=data();d['weights'][:,1,:]=0
    assert len(spectral_channels(d)[1]['vis_relative'])==0


@pytest.mark.parametrize('lengths',[(3,3),(2,3),(1,)])
def test_equal_and_ragged_structured_groups_preserve_all_bytes(lengths):
    dtype=np.dtype([('time','f8'),('pair','U4'),('value','c16')]);original=[]
    for i,n in enumerate(lengths):
        a=np.zeros(n,dtype=dtype);a['time']=i;a['pair']=[f'S{j}' for j in range(n)];a['value']=np.arange(n)+1j*(i+1);original.append(a)
    upstream=np.array(original,dtype=object);fixed=structured_time_groups(upstream,dtype)
    assert fixed.shape==(len(lengths),) and fixed.dtype==object
    for a,b in zip(original,fixed,strict=True):assert a.dtype==b.dtype and a.tobytes()==b.tobytes()


def test_unstructured_group_dtype_is_rejected():
    with pytest.raises(ValueError):structured_time_groups([],float)


@pytest.mark.parametrize('n',[8,9,16,32])
def test_w_bound_is_tight_at_farthest_corner_and_zero_without_w(n):
    uv=np.array([[200.,100.,1500.],[-10.,30.,-400.]])
    b=w_phase_bound(uv,n,512./n);image=np.zeros((n,n));image[0,0]=1
    planar=uv.copy();planar[:,2]=0
    difference=np.max(abs(direct_visibility(uv,image,512./n)-direct_visibility(planar,image,512./n)))
    np.testing.assert_allclose(difference,b['normalized_visibility_absolute_bound'],rtol=1e-8,atol=2e-10)
    assert w_phase_bound(planar,n,512./n)['maximum_phase_rad']==0


def test_large_w_bound_saturates_at_two_instead_of_wrapping():
    assert w_phase_bound(np.array([[0.,0.,1e10]]),8,64.)['normalized_visibility_absolute_bound']==2.


@pytest.mark.parametrize('pixels,pixel',[(True,16),(1,16),(8,-1),(8,float('nan')),(8,1e8)])
def test_invalid_w_geometry_rejected(pixels,pixel):
    with pytest.raises(ValueError):w_phase_bound(np.ones((2,3)),pixels,pixel)
