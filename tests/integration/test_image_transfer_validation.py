"""共通基線の対照で閾値・軸・重みを勝手に変更しないことを確認する。"""
from copy import deepcopy
import numpy as np
import pytest
from workflows.image_transfer_validation import common_baseline_weights, evaluate_candidate


def arrays():
    return dict(pairs=np.array([[0, 1], [0, 2], [1, 2]]), times_s=np.array([0.]),
                frequencies_hz=np.array([1.42e9]), uvw_lambda=np.zeros((1, 1, 3, 3)),
                visibilities=np.array([[[9.9, 10., 10.1]]], complex), weights=np.ones((1, 1, 3)))


def test_exact_threshold_preserves_evaluation_weights_and_inputs():
    train = arrays(); evaluation = deepcopy(train); evaluation['weights'] *= 17
    before = deepcopy((train, evaluation))
    actual = common_baseline_weights(train, evaluation)
    np.testing.assert_array_equal(actual, [[[0., 17., 17.]]])
    actual[0, 0, 1] = 0
    for group, old in zip((train, evaluation), before, strict=True):
        for key in group: np.testing.assert_array_equal(group[key], old[key])


@pytest.mark.parametrize('axis', ['pairs', 'times_s', 'frequencies_hz', 'uvw_lambda'])
def test_different_axes_are_rejected(axis):
    train = arrays(); evaluation = deepcopy(train)
    if axis == 'pairs': evaluation[axis] = np.array([[0, 1], [0, 3], [1, 2]])
    else: evaluation[axis].flat[0] += 1
    with pytest.raises(ValueError, match='axes differ'): common_baseline_weights(train, evaluation)


def test_zero_training_weight_cannot_create_common_information():
    train = arrays(); train['weights'] *= 0
    np.testing.assert_array_equal(common_baseline_weights(train, arrays()), np.zeros((1, 1, 3)))


@pytest.mark.parametrize('value', [0., -1., np.nan, np.inf])
def test_invalid_threshold(value):
    with pytest.raises(ValueError): common_baseline_weights(arrays(), arrays(), value)


def test_no_common_closure_is_unavailable_instead_of_zero_loss():
    data = arrays(); data['weights'] *= 0
    result = evaluate_candidate(data, np.ones((8, 8)), {'pixel_arcsec': 64.})
    assert result['state'] == 'not_evaluable' and 'metrics' not in result
    assert result['reason'] == 'no high SNR independent closure measurements'


def test_other_invalid_image_is_not_hidden_as_missing_information():
    with pytest.raises(ValueError): evaluate_candidate(arrays(), np.zeros((8, 8)), {'pixel_arcsec': 64.})
