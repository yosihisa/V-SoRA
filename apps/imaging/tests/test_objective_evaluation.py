"""画像のflux gaugeと損失分解を確認する。"""
from itertools import combinations
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import pytest
from vsora_imaging.objective_evaluation import evaluate_closure_image
from vsora_imaging.rml import ClosureObjective, fit_closure_image


def arrays():
    pairs = np.array(list(combinations(range(4), 2)))
    uvw = np.random.default_rng(115).uniform(-300, 300, (1, 1, 6, 3))
    phases = np.array([0., .3, -.4, .5]); values = np.exp(1j*(phases[pairs[:, 0]] - phases[pairs[:, 1]]))[None, None]
    return uvw, values, np.full(values.shape, 1e4), pairs


def point():
    image = np.zeros((8, 8)); image[4, 4] = 1.; return image


def test_point_closures_data_loss_and_components():
    result = evaluate_closure_image(*arrays(), point(), pixel_arcsec=64.)
    metrics = result['metrics']
    assert metrics['data_loss'] < 1e-20
    assert sum(metrics[k] for k in ('data_loss', 'entropy_loss', 'tsv_loss', 'centroid_loss')) == pytest.approx(metrics['objective'])
    assert not result['optimizer_executed'] and not result['optimizer_parameter_sum_penalty_included']
    assert not result['actual_observation_success_certified']


def test_flux_gauge_and_inputs_unchanged():
    data = arrays(); image = point(); copies = [x.copy() for x in (*data, image)]
    a = evaluate_closure_image(*data, image, pixel_arcsec=64.)
    b = evaluate_closure_image(*data, image*17, pixel_arcsec=64.)
    assert a['metrics'] == b['metrics']
    assert a['candidate_sum_before_normalization'] == 1 and b['candidate_sum_before_normalization'] == 17
    for x, before in zip((*data, image), copies): np.testing.assert_array_equal(x, before)


def test_prior_has_zero_entropy_and_matches_same_objective():
    data = arrays(); objective = ClosureObjective(*data, pixels=8, pixel_arcsec=64.)
    image = objective.prior.reshape(8, 8)
    result = evaluate_closure_image(*data, image, pixel_arcsec=64.)
    assert abs(result['metrics']['entropy_loss']) < 1e-14
    expected, _ = objective.value_gradient(np.log(image.ravel()))
    assert result['metrics']['objective'] == pytest.approx(expected, rel=1e-12, abs=1e-12)


def test_fitted_image_cost_excludes_parameter_gauge_penalty():
    data = arrays(); image, summary = fit_closure_image(*data, starts=1, max_iterations=20, pixels=8, pixel_arcsec=64.)
    result = evaluate_closure_image(*data, image, pixel_arcsec=64.)
    assert result['metrics']['objective'] == pytest.approx(summary['objective'] - summary['parameter_sum_penalty'], rel=1e-7, abs=1e-8)


@pytest.mark.parametrize('image', [np.zeros((8, 8)), -np.ones((8, 8)), np.ones((7, 7)), np.ones((8, 9)),
    np.ones((8, 8), complex), np.ones((8, 8), bool), np.full((8, 8), np.nan), np.full((8, 8), np.inf), np.full((8, 8), 1e308)])
def test_invalid_image(image):
    with pytest.raises(ValueError): evaluate_closure_image(*arrays(), image, pixel_arcsec=64.)


@pytest.mark.parametrize('pixel', [0., -1., float('nan'), float('inf')])
def test_invalid_pixel_scale(pixel):
    with pytest.raises(ValueError): evaluate_closure_image(*arrays(), point(), pixel_arcsec=pixel)


def test_no_high_snr_closures_is_not_a_valid_evaluation():
    data = list(arrays()); data[2] = np.zeros_like(data[2])
    with pytest.raises(ValueError, match='no high SNR'): evaluate_closure_image(*data, point(), pixel_arcsec=64.)


@pytest.mark.parametrize('name', ['pixel_arcsec', 'min_snr', 'prior_fwhm_arcsec', 'entropy', 'tsv', 'centroid'])
def test_bool_setting_rejected(name):
    settings = {'pixel_arcsec': 64., name: True}
    with pytest.raises(ValueError): evaluate_closure_image(*arrays(), point(), **settings)


def test_numpy_real_settings_return_plain_json():
    result = evaluate_closure_image(*arrays(), point(), pixel_arcsec=np.float32(64), entropy=np.float32(.01))
    assert json.loads(json.dumps(result)) == result


def test_cli_json_identity_and_no_overwrite(tmp_path):
    from vsora_formats.spectral import save_spectral
    from vsora_observation import load_config
    uvw, vis, weights, pairs = arrays(); root = Path(__file__).resolve().parents[3]
    config = load_config(root/'configs/experiments/ideal-point.json')
    source = tmp_path/'source.npz'; image = tmp_path/'image.npy'; output = tmp_path/'objective.json'
    save_spectral(source, dict(uvw_lambda=uvw, visibilities=vis, weights=weights, pairs=pairs,
        times_s=np.array([0.]), frequencies_hz=np.array([1.42e9])), {'config': config, 'visibility_unit': 'ADC^2'})
    np.save(image, point())
    import vsora_imaging.objective_evaluation as module
    runner = [str(root/'tools/run.py')] if '/apps/imaging/src/' in module.__file__ else ['-m']
    command = [sys.executable, *runner, 'vsora_imaging.objective_evaluation', '--input', str(source), '--image', str(image),
               '--output', str(output), '--pixel-arcsec', '64']
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=True)
    actual = json.loads(output.read_text()); assert actual == json.loads(result.stdout)
    expected = evaluate_closure_image(uvw, vis, weights, pairs, point(), pixel_arcsec=64.)
    assert all(actual[k] == v for k, v in expected.items())
    before = output.read_bytes(); repeat = subprocess.run(command, cwd=tmp_path, capture_output=True)
    assert repeat.returncode != 0 and output.read_bytes() == before
