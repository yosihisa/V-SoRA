"""局graphの必要条件を、周波数解の成功と混同しない。"""
from copy import deepcopy
from itertools import combinations
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import pytest
from vsora_correlator.rate_graph import diagnose_rate_graph
from vsora_correlator.rate import estimate_station_rates


def pilot(ids=(0, 1, 2, 3), seed=111):
    pairs = np.array(list(combinations(ids, 2)))
    time = np.arange(256)*.004
    rates = dict(zip(ids, [0., 5., -7., 11.]))
    delta = np.array([rates[i] - rates[j] for i, j in pairs])
    rng = np.random.default_rng(seed)
    vis = np.exp(2j*np.pi*time[:, None, None]*delta[None, None, :])*np.ones((1, 3, 1))
    vis += .1*(rng.normal(size=vis.shape) + 1j*rng.normal(size=vis.shape))
    return {'visibilities': vis, 'weights': np.full(vis.shape, 100.), 'times_s': time, 'pairs': pairs}


def test_connected_matches_current_estimator_and_does_not_mutate():
    data = pilot(); before = deepcopy(data)
    diagnostic = diagnose_rate_graph(data); fit = estimate_station_rates(data)
    assert diagnostic['state'] == 'connected' and diagnostic['components'] == [[0, 1, 2, 3]]
    assert diagnostic['graph_rank'] == diagnostic['required_graph_rank'] == 3
    assert diagnostic['baseline_estimates'] == fit['baseline_estimates']
    assert diagnostic['accepted_baselines'] == fit['accepted_baselines'] == 6
    assert not diagnostic['station_solution_attempted'] and not diagnostic['false_alarm_probability_calibrated']
    assert np.max(np.abs(np.array(fit['station_rates_hz']) - [0, 5, -7, 11])) < .02
    for key in data: np.testing.assert_array_equal(data[key], before[key])


def test_disconnected_keeps_isolated_station():
    data = pilot(); data['weights'][..., np.any(data['pairs'] == 3, axis=1)] = 0
    result = diagnose_rate_graph(data)
    assert result['state'] == 'disconnected'
    assert result['components'] == [[0, 1, 2], [3]]
    assert result['isolated_stations'] == result['stations_outside_reference_component'] == [3]
    assert result['accepted_baselines'] == 3 and result['graph_rank'] == 2
    assert result['rejected_baselines'] == {'no channels with eight valid samples': 3}
    with pytest.raises(ValueError, match='graph is disconnected'): estimate_station_rates(data)


def test_two_nontrivial_components():
    data = pilot()
    for b, pair in enumerate(data['pairs']):
        if tuple(pair) not in ((0, 1), (2, 3)): data['weights'][..., b] = 0
    result = diagnose_rate_graph(data, reference_station=2)
    assert result['components'] == [[0, 1], [2, 3]]
    assert result['reference_component'] == [2, 3] and result['stations_outside_reference_component'] == [0, 1]
    assert not result['isolated_stations']


def test_non_contiguous_station_ids_and_reference():
    data = pilot((2, 5, 9))
    result = diagnose_rate_graph(data, reference_station=5)
    assert result['station_indices'] == [2, 5, 9] and result['graph_rank'] == 2
    assert result['baseline_estimates'] == estimate_station_rates(data, reference_station=5)['baseline_estimates']


def test_no_coherent_signal_is_not_a_solution():
    data = pilot(); data['visibilities'][:] = 0
    result = diagnose_rate_graph(data)
    assert result['accepted_baselines'] == 0 and result['graph_rank'] == 0
    assert result['components'] == [[0], [1], [2], [3]]
    assert result['rejected_baselines'] == {'insufficient coherent detection': 6}


def test_outside_search_and_nyquist_equality():
    data = pilot(); result = diagnose_rate_graph(data, max_rate_hz=2.)
    assert result['accepted_baselines'] == 0
    assert result['rejected_baselines'] == {'peak outside search or on search boundary': 6}
    with pytest.raises(ValueError): diagnose_rate_graph(data, max_rate_hz=125.)


@pytest.mark.parametrize('name', ['max_rate_hz', 'min_snr', 'min_peak_z'])
@pytest.mark.parametrize('value', [True, 0, -1, float('nan'), float('inf'), 1j, '8', [8]])
def test_invalid_settings(name, value):
    with pytest.raises(ValueError): diagnose_rate_graph(pilot(), **{name: value})


@pytest.mark.parametrize('reference', [True, 1., -1, 8])
def test_invalid_reference(reference):
    with pytest.raises(ValueError): diagnose_rate_graph(pilot(), reference_station=reference)


def test_invalid_time_and_weight_rejected():
    data = pilot(); data['times_s'][4] += .001
    with pytest.raises(ValueError): diagnose_rate_graph(data)
    data = pilot(); data['weights'][0, 0, 0] = -1
    with pytest.raises(ValueError): diagnose_rate_graph(data)


def test_cli_json_and_non_overwrite(tmp_path):
    from vsora_formats.spectral import save_spectral
    from vsora_observation import load_config
    data = pilot(); data.update(uvw_lambda=np.zeros(data['visibilities'].shape + (3,)),
        frequencies_hz=np.array([1.419e9, 1.42e9, 1.421e9]), integration_s=np.full((256, 6), .004))
    root = Path(__file__).resolve().parents[3]
    config = load_config(root/'configs/experiments/ideal-point.json')
    source = tmp_path/'pilot.npz'; save_spectral(source, data, {'config': config, 'visibility_unit': 'ADC^2'})
    output = tmp_path/'graph.json'
    import vsora_correlator.rate_graph as module
    runner = [str(root/'tools/run.py')] if '/apps/correlator/src/' in module.__file__ else ['-m']
    cmd = [sys.executable, *runner, 'vsora_correlator.rate_graph', '--input', str(source), '--output', str(output)]
    completed = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, check=True)
    expected = diagnose_rate_graph(data)
    assert json.loads(output.read_text()) == json.loads(completed.stdout) == expected
    before = output.read_bytes(); repeat = subprocess.run(cmd, cwd=tmp_path, capture_output=True)
    assert repeat.returncode != 0 and output.read_bytes() == before
