"""理想化対照のSNR保存は人工的な重みで、測定較正と区別する。"""
import numpy as np
import pytest
from workflows.image_control_validation import idealize_visibility
from vsora_imaging.closure import form_closures


@pytest.mark.parametrize('dtype', [np.complex64, np.complex128])
def test_known_triangle_phase_and_observed_mask_preserved(dtype):
    pairs = np.array([[0, 1], [0, 2], [1, 2]])
    observed = np.array([[[2+1j, 3-2j, 1-3j]], [[0j, 2+0j, 3+0j]]], dtype=dtype)
    model = np.broadcast_to(np.array([1+0j, 1j, 1+1j], dtype=dtype), observed.shape).copy()
    weights = np.full(observed.shape, 400.)
    before_v = observed.copy(); before_w = weights.copy(); before_m = model.copy()
    values, transported = idealize_visibility(observed, weights, model)
    np.testing.assert_allclose(np.abs(values)*np.sqrt(transported), np.abs(observed.astype(complex))*np.sqrt(weights), rtol=1e-12)
    a = form_closures(observed, weights, pairs, 10.); b = form_closures(values, transported, pairs, 10.)
    for key in ('baseline_valid', 'phase_valid', 'logamp_valid'): np.testing.assert_array_equal(a[key], b[key])
    assert b['phase_valid'][0, 0, 0] and not b['phase_valid'][1, 0, 0]
    assert abs(b['phase'][0, 0, 0] + np.pi/4) < 1e-12
    for old, new in ((before_v, observed), (before_w, weights), (before_m, model)): np.testing.assert_array_equal(old, new)


def test_zero_model_only_allowed_at_zero_weight():
    observed = np.ones((1, 1, 3), complex); weights = np.ones(observed.shape); model = observed.copy(); model[0, 0, 0] = 0
    with pytest.raises(ValueError, match='nonzero model'): idealize_visibility(observed, weights, model)
    weights[0, 0, 0] = 0
    _, moved = idealize_visibility(observed, weights, model)
    assert moved[0, 0, 0] == 0


@pytest.mark.parametrize('kind', ['shape', 'negative', 'nan', 'noncomplex', 'overflow'])
def test_invalid_or_unrepresentable_controls_stop(kind):
    observed = np.ones((1, 1, 3), complex); weights = np.ones(observed.shape); model = observed.copy()
    if kind == 'shape': model = model.ravel()
    elif kind == 'negative': weights[0, 0, 0] = -1
    elif kind == 'nan': model[0, 0, 0] = np.nan
    elif kind == 'noncomplex': model = model.real
    elif kind == 'overflow': model[0, 0, 0] = 1e-300
    with pytest.raises(ValueError): idealize_visibility(observed, weights, model)
