"""固定原本の拒否条件と、未処理/有効制約0の意味を実際に検証する。"""
import json
import numpy as np
import pytest
from workflows.short_integration_matrix import (
    CASES, verify_inputs, sha, truth_evaluation, classify_result, independent_counts, EXPECTED_FAILURES)
from vsora_imaging.closure import form_closures


def raw_catalog(tmp_path):
    rows = []
    for case in CASES:
        raw = tmp_path/case/'input'; raw.mkdir(parents=True)
        for i in range(18): (raw/f'file-{i}').write_text(str(i))
        (raw/'observation.json').write_text(json.dumps({'source': {'model': 'unknown'}, 'noise': {'enabled': True}}))
        rows.append({'case': case, 'raw_input_file_sha256': {p.name: sha(p) for p in raw.iterdir()}})
    return {'cases': rows}


def test_modified_raw_or_extra_file_refused_before_inference(tmp_path):
    reference = raw_catalog(tmp_path); verify_inputs(tmp_path, reference)
    p = tmp_path/'weak_b/input/file-0'; p.write_text('changed')
    with pytest.raises(ValueError, match='SHA mismatch'): verify_inputs(tmp_path, reference)
    p.write_text('0'); (p.parent/'extra').write_text('extra')
    with pytest.raises(ValueError, match='SHA mismatch'): verify_inputs(tmp_path, reference)


@pytest.mark.parametrize('change', ['known_sky', 'flux', 'noise_false'])
def test_observation_truth_and_wrong_noise_metadata_rejected(tmp_path, change):
    reference = raw_catalog(tmp_path); path = tmp_path/'high_a/input/observation.json'
    observed = json.loads(path.read_text())
    if change == 'known_sky': observed['source']['model'] = 'casa'
    if change == 'flux': observed['source']['total_flux_jy'] = 1000.
    if change == 'noise_false': observed['noise']['enabled'] = False
    path.write_text(json.dumps(observed)); reference['cases'][0]['raw_input_file_sha256'][path.name] = sha(path)
    with pytest.raises(ValueError, match='unknown sky'): verify_inputs(tmp_path, reference)


def test_missing_or_reordered_case_refused(tmp_path):
    reference = raw_catalog(tmp_path); reference['cases'].reverse()
    with pytest.raises(ValueError, match='fixed four'): verify_inputs(tmp_path, reference)


def test_null_evaluation_and_known_boxcar_calculation():
    assert truth_evaluation(None, {}, None, .3) is None
    estimate = {'station_rates_hz': [0., .5, -.5]}; generating = {'station_rates_hz': [0., 0., 0.]}
    result = truth_evaluation(estimate, generating, np.array([[0,1],[1,2]]), 1.)
    assert result['maximum_station_rate_error_hz'] == .5
    assert result['calculated_minimum_constant_rate_boxcar_retention'] == abs(np.sinc(1.))
    assert result['truth_supplied_to_estimator'] is False and result['retention_is_measured_coherence'] is False
    with pytest.raises(ValueError, match='matching finite'):
        truth_evaluation(estimate, {'station_rates_hz': [0., np.nan, 0.]}, np.array([[0,1]]), 1.)


@pytest.mark.parametrize('message,code', list(EXPECTED_FAILURES.items()))
def test_exact_scientific_failure_retained(tmp_path, message, code):
    partial = tmp_path/'pipeline.partial'; partial.mkdir()
    (partial/'pipeline.json').write_text(json.dumps({'state': 'incomplete', 'error_type': 'ValueError'}))
    path, summary, failure = classify_result(tmp_path, 1, 'ValueError: '+message+'\n')
    assert path == partial and summary['state'] == 'incomplete' and failure == code


def test_unexpected_error_and_corrupt_success_not_accepted(tmp_path):
    with pytest.raises(RuntimeError, match='unexpected'): classify_result(tmp_path, 1, 'RuntimeError: disk failure\n')
    completed = tmp_path/'pipeline'; completed.mkdir()
    (completed/'pipeline.json').write_text(json.dumps({'state': 'incomplete'}))
    with pytest.raises(ValueError, match='complete pipeline'): classify_result(tmp_path, 0, '')


def test_correlated_but_no_usable_closure_is_zero_rank_not_null():
    pairs = np.array([[0,1],[0,2],[1,2]])
    closures = form_closures(np.ones((1,1,3), complex), np.zeros((1,1,3)), pairs, 10.)
    ranks = independent_counts(closures)
    assert ranks is not None and ranks['phase_rank'] == ranks['logamp_rank'] == 0
    assert ranks['cells'][0]['phase']['selected'] == []


def test_shared_baselines_have_fewer_independent_closures():
    pairs = np.array([[i,j] for i in range(4) for j in range(i+1,4)])
    closures = form_closures(np.ones((1,1,6), complex), np.full((1,1,6), 400.), pairs, 10.)
    ranks = independent_counts(closures)
    assert closures['phase_valid'].sum() == 4 and ranks['phase_rank'] == 3
    assert ranks['logamp_rank'] == 2
