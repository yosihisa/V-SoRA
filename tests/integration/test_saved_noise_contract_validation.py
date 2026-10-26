"""既存APIの比較を、同一support/単位/空情報の意味で検証する。"""
from copy import deepcopy
from itertools import combinations
import numpy as np
import pytest
from workflows.saved_noise_contract_validation import compare_noise


def fixture():
    pairs=np.array(list(combinations(range(4),2)));v=np.exp(1j*np.arange(6)*.2)
    data={'visibilities':v[None,None,:],'weights':np.full((1,1,6),400.),'pairs':pairs,
          'frequencies_hz':np.array([1.42e9]),'metadata':{'visibility_unit':'ADC^2'}}
    diagnostic={'state':'conditional_estimate','channel_index':0,'time_index':0,'frequency_hz':1.42e9,
                'visibility_unit':'ADC^2','estimated_visibility_covariance':(np.eye(12)/400).tolist()}
    return data,diagnostic


def test_independent_circular_case_returns_production_covariance():
    data,q=fixture();info,arrays=compare_noise(data,0,q)
    assert info['phase_rank']==3 and info['logamp_rank']==2
    np.testing.assert_allclose(arrays['joint_comparison_covariance'],arrays['production_comparison_covariance'],rtol=1e-12,atol=1e-15)
    assert info['metrics']['maximum_phase_logamp_correlation']<1e-12


def test_positive_covariance_scale_change_preserves_closure_comparison():
    data,q=fixture();t=np.arange(12)/11;cov=np.eye(12)/400+.0002*np.outer(t,t);q['estimated_visibility_covariance']=cov.tolist()
    info,a=compare_noise(data,0,q);other=deepcopy(data);other['visibilities']*=2;other['weights']/=4
    q2=deepcopy(q);q2['estimated_visibility_covariance']=(cov*4).tolist();info2,b=compare_noise(other,0,q2)
    np.testing.assert_array_equal(a['selected_joint_rows'],b['selected_joint_rows'])
    np.testing.assert_allclose(a['joint_comparison_covariance'],b['joint_comparison_covariance'],rtol=1e-12,atol=1e-15)
    assert info['metrics']['maximum_phase_logamp_correlation']>0


@pytest.mark.parametrize('key,value',[('channel_index',1),('time_index',1),('visibility_unit','Jy')])
def test_different_cell_or_units_cannot_be_mixed(key,value):
    data,q=fixture();q[key]=value
    with pytest.raises(ValueError,match='matching cell'):compare_noise(data,0,q)


def test_inactive_information_is_not_zero_variance():
    data,q=fixture();q={'state':'inactive','reason':'no_positive_baseline_weights'}
    info,arrays=compare_noise(data,0,q)
    assert info['state']=='not_available' and info['metrics'] is None and arrays=={}


def test_zero_high_snr_support_is_explicit_zero_rank_with_null_metrics():
    data,q=fixture();data['weights'][:]=1.
    info,arrays=compare_noise(data,0,q)
    assert info['state']=='no_common_independent_closures' and info['phase_rank']==info['logamp_rank']==0
    assert info['metrics'] is None and arrays['joint_comparison_covariance'].shape==(0,0)
