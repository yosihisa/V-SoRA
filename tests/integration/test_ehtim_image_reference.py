"""実optimizerの状態、入力の分離、人工参照のSNR/maskを検証する。"""
from copy import deepcopy
import sys
import numpy as np
import pytest
from scipy.optimize import minimize,rosen,rosen_der
from workflows.ehtim_conventions_validation import fixed_inputs
from workflows.ehtim_image_reference import initial_images,capture_minimize,matched_reference
from vsora_imaging.closure import form_closures


def test_shared_initial_images_are_reproducible_positive_unit_flux():
    prior,images=initial_images();again=initial_images()[1]
    np.testing.assert_array_equal(images,again);np.testing.assert_allclose(images.sum(axis=(1,2)),1.,atol=2e-16)
    np.testing.assert_allclose(images[0],prior,rtol=1e-14,atol=1e-16)
    assert np.all(images>0) and not np.array_equal(images[0],images[1])


@pytest.mark.parametrize('kwargs',[{'starts':0},{'starts':True},{'pixel_arcsec':0}])
def test_invalid_shared_start_parameters_rejected(kwargs):
    with pytest.raises(ValueError):initial_images(**kwargs)


def test_actual_optimizer_return_and_input_are_not_modified():
    previous=sys.getprofile();dummy=lambda frame,event,arg:None;sys.setprofile(dummy)
    x=np.array([3.,-2.]);before=x.copy()
    try:
        result,records,inputs=capture_minimize(lambda:minimize(lambda z:float(z@z),x,jac=lambda z:2*z,method='L-BFGS-B'),1)
        assert sys.getprofile() is dummy
        assert result.success and records[0]['optimizer_success'] is True and records[0]['objective']==result.fun
        assert records[0]['optimizer_status']==result.status and records[0]['iterations']==result.nit
        np.testing.assert_array_equal(x,before);np.testing.assert_array_equal(inputs[0],before)
    finally:sys.setprofile(previous)


def test_actual_iteration_limit_is_recorded_as_nonconvergence():
    value,records,_=capture_minimize(lambda:minimize(rosen,[-1.2,1.],jac=rosen_der,method='L-BFGS-B',options={'maxiter':1}),1)
    assert not value.success and records[0]['optimizer_success'] is False and records[0]['iterations']==1


def test_unknown_exception_propagates_and_profile_is_restored():
    previous=sys.getprofile()
    def broken():raise RuntimeError('reference failure')
    with pytest.raises(RuntimeError,match='reference failure'):capture_minimize(broken,1)
    assert sys.getprofile() is previous


def test_missing_actual_optimizer_call_is_not_assumed_successful():
    with pytest.raises(ValueError,match='actual minimize'):capture_minimize(lambda:None,1)


@pytest.mark.parametrize('count',[0,True,1.5])
def test_invalid_capture_count_is_rejected(count):
    with pytest.raises(ValueError):capture_minimize(lambda:None,count)


def source_data():
    pairs,_,frequency,times,uvw=fixed_inputs();v=np.full(uvw.shape[:-1],10+1j);w=np.full(v.shape,4.)
    w[0,0,0]=0.;w[1,1,2]=.01
    return {'uvw_lambda':uvw,'visibilities':v,'weights':w,'pairs':pairs,'frequencies_hz':frequency,'times_s':times}


def test_matched_reference_preserves_masks_snr_gain_invariance_and_original():
    d=source_data();before=deepcopy(d);truth=np.zeros((8,8));truth[4,4]=1
    reference,gains,diff=matched_reference(d,truth,64.)
    original=form_closures(d['visibilities'],d['weights'],d['pairs'],10.)
    actual=form_closures(reference['visibilities'],reference['weights'],reference['pairs'],10.)
    np.testing.assert_array_equal(original['baseline_valid'],actual['baseline_valid'])
    np.testing.assert_allclose(actual['baseline_snr'],original['baseline_snr'],atol=1e-13)
    assert max(diff.values())<1e-12 and np.all(reference['uvw_lambda'][...,2]==0.)
    assert gains.shape==(2,4) and not np.array_equal(gains,np.ones_like(gains))
    assert 'truth' not in reference and 'gains' not in reference
    for key in d:np.testing.assert_array_equal(d[key],before[key])


@pytest.mark.parametrize('invalid',['weight','geometry','truth'])
def test_nonphysical_reference_input_is_rejected(invalid):
    d=source_data();truth=np.zeros((8,8));truth[4,4]=1
    if invalid=='weight':d['weights'][0,0,0]=-1
    elif invalid=='geometry':d['uvw_lambda']=d['uvw_lambda'].astype(complex)+1j
    else:truth[0,0]=-1
    with pytest.raises(ValueError):matched_reference(d,truth,64.)


def test_reference_integration_metadata_is_preserved_without_aliasing():
    d=source_data();d['integration_s']=np.full((2,6),3.)
    truth=np.zeros((8,8));truth[4,4]=1
    reference,_,_=matched_reference(d,truth,64.)
    np.testing.assert_array_equal(reference['integration_s'],d['integration_s'])
    assert reference['integration_s'] is not d['integration_s']


@pytest.mark.parametrize('integration',[np.zeros((2,6)),np.ones(2)])
def test_invalid_integration_metadata_is_rejected(integration):
    d=source_data();d['integration_s']=integration;truth=np.zeros((8,8));truth[4,4]=1
    with pytest.raises(ValueError,match='integration seconds'):matched_reference(d,truth,64.)
