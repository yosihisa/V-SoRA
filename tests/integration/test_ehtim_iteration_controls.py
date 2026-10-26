"""局所勾配の診断が誤勾配・不正値を成功へ置換しないこと。"""
import numpy as np
import pytest
from workflows.ehtim_iteration_controls import directional_gradient
from workflows.ehtim_image_reference import external_imager


def test_independent_quadratic_derivative_matches_and_input_unchanged():
    a=np.array([1.,3.,7.]);x=np.array([.2,-.7,2.]);before=x.copy()
    result=directional_gradient(lambda z:float(.5*np.sum(a*z*z)),lambda z:a*z,x)
    assert result['all_primary_passed'] and result['maximum_primary_normalized_error']<1e-9
    np.testing.assert_array_equal(x,before)


def test_deliberately_wrong_derivative_is_a_negative_diagnostic():
    result=directional_gradient(lambda z:float(z@z),lambda z:2*z+10.,np.array([1.,2.,3.]))
    assert not result['all_primary_passed'] and result['maximum_primary_normalized_error']>.1


def test_nonfinite_objective_is_not_a_zero_difference():
    with pytest.raises(ValueError,match='nonfinite'):directional_gradient(lambda z:float('nan'),lambda z:2*z,np.ones(3))


@pytest.mark.parametrize('gradient',[lambda z:np.ones(4),lambda z:np.full(3,np.nan)])
def test_invalid_analytic_derivative_is_rejected(gradient):
    with pytest.raises(ValueError):directional_gradient(lambda z:float(z@z),gradient,np.ones(3))


@pytest.mark.parametrize('x',[np.ones((2,2)),np.array([np.inf]),np.array([])])
def test_invalid_parameter_vector_is_rejected(x):
    with pytest.raises(ValueError):directional_gradient(lambda z:1.,lambda z:z,x)


@pytest.mark.parametrize('limit',[0,True,5001,-1])
def test_external_budget_guard_before_optional_import(limit):
    with pytest.raises(ValueError,match='iterations'):external_imager(None,None,limit)


def test_secondary_extrapolation_matches_independent_quartic_derivative():
    x=np.array([.7,-1.2,.3]);q=directional_gradient(lambda z:float(np.sum(z**4)),lambda z:4*z**3,x)
    assert q['maximum_secondary_normalized_error']<1e-7
    assert q['all_primary_passed']==all(row['primary_passed'] for row in q['directions'])
