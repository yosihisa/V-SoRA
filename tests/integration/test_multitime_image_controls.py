"""真値rate対照の来歴が推定値の採用率や誤差と混ざらない。"""
from copy import deepcopy
import numpy as np
import pytest
from workflows.multitime_image_controls import truth_rate_profile


def template():
    return {'schema_version': 1, 'type': 'station_rate_only', 'station_ids': ['A','B','C'],
            'station_indices': [0,1,2], 'time_origin_utc': '2026-10-02T10:00:00Z',
            'valid_time_range_s': [0.004,3.], 'sample_cadence_s': .004, 'time_reference_s': 1.502,
            'station_rates_hz': [0.,1.,2.], 'baseline_estimates': [{'accepted': True}], 'rms_hz': .01}


def test_known_rates_have_only_coordinate_and_evaluation_provenance():
    old = template(); before = deepcopy(old); out = truth_rate_profile(old, np.array([0.,3.,4.]))
    assert old == before and out['station_rates_hz'] == [0.,3.,4.]
    assert out['evaluation_only'] and out['estimated_from_data'] is False
    assert 'baseline_estimates' not in out and 'rms_hz' not in out
    out['station_indices'][0] = 999
    assert old == before


@pytest.mark.parametrize('rates', [[0.,1.], [[0.,1.,2.]], [0.,1.,np.nan], [0.,np.inf,1.], [0j,1j,2j], [True,False,True]])
def test_invalid_known_rates(rates):
    with pytest.raises(ValueError): truth_rate_profile(template(), rates)
