"""独立実験のcell併用で元の重み・幾何・正則化の尺度を変えない。"""
from copy import deepcopy
from itertools import combinations
import numpy as np
import pytest
from workflows.image_joint_validation import stack_replicates, weighted_check


def data():
    return dict(uvw_lambda=np.ones((1, 1, 6, 3))*30, pairs=np.array(list(combinations(range(4), 2))),
                visibilities=np.ones((1, 1, 6), complex), weights=np.ones((1, 1, 6))*1000,
                times_s=np.array([0.]), frequencies_hz=np.array([1.42e9]), metadata={'visibility_unit': 'ADC^2'})


def test_keeps_separate_cells_weights_and_original_arrays():
    a = data(); b = data(); b['visibilities'] *= 2j; b['weights'] *= 3
    before = deepcopy((a, b)); uv, v, w, pairs = stack_replicates([a, b])
    assert v.shape == (2, 1, 6)
    for actual, key in ((uv, 'uvw_lambda'), (v, 'visibilities'), (w, 'weights')):
        np.testing.assert_array_equal(actual[:1], a[key]); np.testing.assert_array_equal(actual[1:], b[key])
        actual *= 0
    pairs *= 0
    for actual, old in zip((a, b), before, strict=True):
        for key in actual:
            if key != 'metadata': np.testing.assert_array_equal(actual[key], old[key])


@pytest.mark.parametrize('axis', ['pairs', 'times_s', 'frequencies_hz', 'uvw_lambda'])
def test_different_axes_rejected(axis):
    a = data(); b = data()
    if axis == 'pairs': b[axis][-1] = [2, 4]
    else: b[axis].flat[0] += 1
    with pytest.raises(ValueError, match='axes differ'): stack_replicates([a, b])


@pytest.mark.parametrize('inputs', [[], [data()]])
def test_insufficient_replicates(inputs):
    with pytest.raises(ValueError): stack_replicates(inputs)


def test_different_visibility_unit_rejected():
    a = data(); b = data(); b['metadata']['visibility_unit'] = 'Jy'
    with pytest.raises(ValueError, match='units differ'): stack_replicates([a, b])


def test_count_weighted_data_loss_and_regularizer_once():
    a = data(); b = data(); b['visibilities'][0, 0, 1] *= np.exp(.1j)
    image = np.ones((8, 8)); image[4, 4] = 8
    result = weighted_check(stack_replicates([a, b]), [a, b], image, {'pixel_arcsec': 64.})
    assert result['combined']['metrics']['data_loss'] == pytest.approx(result['independent_count_weighted_data_loss'])
    assert result['combined']['metrics']['entropy_loss'] > 0
