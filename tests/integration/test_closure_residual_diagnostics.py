"""保存済み画像の独立残差分解が、共有共分散・不足・wrapを保つこと。"""
from copy import deepcopy
from itertools import combinations
import numpy as np
import pytest
from workflows.closure_residual_diagnostics import diagnose_image,common_baseline_mask
from vsora_imaging.closure import closure_design


def data():
    pairs=np.array(list(combinations(range(4),2)))
    phase=np.array([.03,-.01,.05,.02,-.04,.01]);logamp=np.array([.01,-.02,.03,.02,-.01,.04])
    v=(np.exp(logamp+1j*phase))[None,None];w=np.full(v.shape,1e4)
    return {'visibilities':v,'weights':w,'pairs':pairs,'uvw_lambda':np.zeros((*v.shape,3)),'times_s':np.array([.15]),'frequencies_hz':np.array([1.42e9])}


def point():
    image=np.zeros((8,8));image[4,4]=1.;return image


def test_whitened_energy_matches_full_singular_covariance_pseudoinverse():
    d=data();result,arrays=diagnose_image(d,point());design=closure_design(d['pairs']);variance=1/(np.abs(d['visibilities'][0,0])**2*d['weights'][0,0]);expected=0.
    for kind,x in [('phase',np.angle(d['visibilities'][0,0])),('logamp',np.log(np.abs(d['visibilities'][0,0])))]:
        a=design[kind+'_matrix'];r=-a@x;cov=(a*variance)@a.T;expected+=float(r @ np.linalg.pinv(cov) @ r)
    assert result['independent_counts']=={'phase':3,'logamp':2}
    np.testing.assert_allclose(result['chi2_approx'],expected,rtol=2e-13)
    np.testing.assert_allclose(result['data_loss'],.5*expected/5,rtol=2e-13)
    assert not result['p_value_computed'] and not result['optimizer_executed']
    assert np.any(arrays['t000_f000_phase_covariance']-np.diag(np.diag(arrays['t000_f000_phase_covariance'])))


def test_station_gain_and_noise_scale_preserve_full_diagnostic_and_input():
    d=data();before=deepcopy(d);base,_=diagnose_image(d,point())
    g=np.exp(np.array([.3,-.2,.1,.5])+1j*np.array([2.7,-2.9,.6,-1.4]));p=d['pairs'];gain=g[p[:,0]]*g[p[:,1]].conj()
    altered={**d,'visibilities':d['visibilities']*gain,'weights':d['weights']/np.abs(gain)**2}
    fitted,_=diagnose_image(altered,point());np.testing.assert_allclose(fitted['data_loss'],base['data_loss'],rtol=1e-12,atol=1e-12)
    for k in d:np.testing.assert_array_equal(d[k],before[k])


def test_exact_model_has_zero_residual_but_missing_data_has_null_score():
    d=data();d['visibilities']=np.ones(d['visibilities'].shape,complex)*1000
    exact,_=diagnose_image(d,point());assert exact['data_loss']<1e-20 and exact['state']=='complete'
    d['weights'][:]=0;missing,_=diagnose_image(d,point())
    assert missing['state']=='insufficient_constraints' and missing['data_loss'] is None and missing['chi2_approx'] is None and missing['public_api'] is None
    assert all(x['local_data_loss'] is None for x in missing['cells'])


def test_three_stations_keep_amplitude_unmeasured_instead_of_zero():
    d=data();idx=[0,1,3]
    for key in ['visibilities','weights','uvw_lambda']:d[key]=d[key][...,idx,:] if key=='uvw_lambda' else d[key][...,idx]
    d['pairs']=d['pairs'][idx]
    result,_=diagnose_image(d,point());assert result['independent_counts']=={'phase':1,'logamp':0}
    assert result['cells'][0]['logamp']['chi2_approx'] is None and result['component_chi2_approx']['logamp'] is None


def test_phase_wrap_is_applied_after_selected_closure():
    d=data();d['visibilities']=np.exp(1j*np.array([2.7,-2.5,.4,2.4,-2.7,.8]))[None,None]
    result,arrays=diagnose_image(d,point());r=arrays['t000_f000_phase_residual']
    assert np.max(np.abs(r))<=np.pi and result['state']=='complete'
    selected=arrays['t000_f000_phase_matrix'];expected=np.angle(np.exp(-1j*(selected @ np.angle(d['visibilities'][0,0]))))
    np.testing.assert_allclose(r,expected,atol=1e-14)


def test_common_support_intersects_without_modifying_original_weights():
    a=data();b=deepcopy(a);a['weights'][0,0,0]=0;b['weights'][0,0,1]=0
    am=a['weights'].copy();bm=b['weights'].copy();m=common_baseline_mask([a,b]);assert m.sum()==4
    np.testing.assert_array_equal(a['weights'],am);np.testing.assert_array_equal(b['weights'],bm)


def test_mismatched_axes_cannot_be_called_common_support():
    a=data();b=deepcopy(a);b['frequencies_hz']+=1
    with pytest.raises(ValueError,match='identical'):common_baseline_mask([a,b])
    with pytest.raises(ValueError):common_baseline_mask([])


def test_multicell_scores_aggregate_by_independent_count():
    d=data()
    for key in ['visibilities','weights','uvw_lambda']:d[key]=np.repeat(np.repeat(d[key],2,axis=0),2,axis=1)
    d['times_s']=np.array([.15,.45]);d['frequencies_hz']=np.array([1.42e9,1.4201e9]);d['weights'][0,1,:]=0.
    result,_=diagnose_image(d,point());assert result['independent_count']==15 and result['cells_with_constraints']==3
    weighted=sum(x['local_data_loss']*x['independent_count'] for x in result['cells'] if x['state']=='available')/15
    np.testing.assert_allclose(result['data_loss'],weighted,atol=1e-14)


@pytest.mark.parametrize('image',[np.zeros((8,8)),-np.ones((8,8)),np.full((8,8),np.nan),np.ones((8,9)),np.ones((8,8),complex),np.full((8,8),'bad'),np.ones((7,7))])
def test_invalid_candidate_is_not_scientific_zero(image):
    with pytest.raises(ValueError):diagnose_image(data(),image)


@pytest.mark.parametrize('invalid',['complex','nonfinite','shape'])
def test_invalid_geometry_is_not_scientific_failure(invalid):
    d=data()
    if invalid=='complex':d['uvw_lambda']=d['uvw_lambda'].astype(complex)
    elif invalid=='nonfinite':d['uvw_lambda'][0,0,0,0]=np.inf
    else:d['uvw_lambda']=np.zeros((1,1,6,2))
    with pytest.raises(ValueError):diagnose_image(d,point())


def test_numerical_model_null_is_rejected_like_existing_objective():
    d=data();image=point();image[:]=0;image[4,4]=image[4,5]=.5;d['uvw_lambda'][...,0]=1/(2*16*np.pi/(180*3600))
    with pytest.raises(ValueError,match='numerical zero'):diagnose_image(d,image)
