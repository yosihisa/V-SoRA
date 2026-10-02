from itertools import combinations
import numpy as np
import pytest
from vsora_imaging.rml import ClosureObjective, fit_closure_image


def fixture(pixels=12, cells=3):
    rng = np.random.default_rng(21021); pairs = np.array(list(combinations(range(6), 2)))
    stations = rng.normal(size=(cells, 6, 3))*900; stations[..., 2] = 0
    uvw = (stations[:, pairs[:, 1]]-stations[:, pairs[:, 0]])[:, None]
    # Three analytic point sources, total one, centroid exactly zero.
    locations = np.array([[-32, 0], [32, 32], [32, -48]])*np.pi/(180*3600)
    v = sum(flux*np.exp(-2j*np.pi*(uvw[..., :2]@lm)) for flux, lm in zip([.5, .3, .2], locations))
    return uvw, v, np.ones(v.shape)*1e4, pairs


@pytest.mark.parametrize('phase_loss', ['wrapped', 'circular'])
def test_analytic_gradient_against_independent_finite_difference(phase_loss):
    args = fixture(); objective = ClosureObjective(*args, pixels=12)
    objective.phase_loss = phase_loss
    rng = np.random.default_rng(12); z = np.log(objective.prior)+rng.normal(0, .1, 144)
    value, gradient = objective.value_gradient(z)
    numeric = np.empty(144); step = 1e-6
    for i in range(144):
        delta = np.zeros(144); delta[i] = step
        numeric[i] = (objective.value_gradient(z+delta)[0]-objective.value_gradient(z-delta)[0])/(2*step)
    assert np.linalg.norm(numeric-gradient)/np.linalg.norm(gradient) < 1e-6
    assert abs(gradient.sum()) < 1e-10


def test_unknown_station_gain_does_not_change_objective():
    uvw, v, w, pairs = fixture()
    rng = np.random.default_rng(8)
    gains = np.exp(rng.uniform(-2, 2, (3, 1, 6))+1j*rng.uniform(-4, 4, (3, 1, 6)))
    pairgain = gains[..., pairs[:, 0]]*gains[..., pairs[:, 1]].conj()
    a = ClosureObjective(uvw, v, w, pairs, pixels=12)
    b = ClosureObjective(uvw, v*pairgain, w/abs(pairgain)**2, pairs, pixels=12)
    z = np.log(a.prior)+rng.normal(0, .1, 144)
    va, ga = a.value_gradient(z); vb, gb = b.value_gradient(z)
    assert abs(va-vb) < 1e-9
    assert np.max(abs(ga-gb)) < 1e-8


def test_intensity_gradient_against_finite_difference():
    obj = ClosureObjective(*fixture(), pixels=12)
    x = obj.prior+.001
    value, grad = obj.intensity_value_gradient(x)
    numeric = np.empty(144); step = 1e-7
    for i in range(144):
        delta = np.zeros(144); delta[i] = step
        numeric[i] = (obj.intensity_value_gradient(x+delta)[0]-obj.intensity_value_gradient(x-delta)[0])/(2*step)
    assert np.linalg.norm(numeric-grad)/np.linalg.norm(grad) < 1e-6


def test_positive_relative_flux_fit_and_no_information_failure():
    uvw, v, w, p = fixture(cells=10)
    image, summary = fit_closure_image(uvw, v, w, p, pixels=16, starts=3, max_iterations=800)
    assert np.all(image >= 0) and abs(image.sum()-1) < 1e-12
    assert summary['closure_chisq_per_measurement'] < .2
    assert not summary['absolute_flux_measured'] and not summary['absolute_position_measured']
    with pytest.raises(ValueError, match='no high SNR'): ClosureObjective(uvw, v, w*0, p)


def test_adc_rml_fits_units_and_checksums(tmp_path):
    from pathlib import Path
    from astropy.io import fits
    from vsora_observation import load_config
    from vsora_formats.spectral import save_spectral
    from vsora_imaging.rml import image_closure
    uvw, v, w, pairs = fixture(cells=3)
    config=load_config(Path(__file__).resolve().parents[3]/'configs/experiments/ideal-point.json')
    data={'uvw_lambda':uvw,'visibilities':v,'weights':w,'pairs':pairs,
          'times_s':np.array([.15,.45,.75]),'frequencies_hz':np.array([1.42e9])}
    save_spectral(tmp_path/'adc.npz',data,{'config':config,'visibility_unit':'ADC^2'})
    result=image_closure(tmp_path/'adc.npz',tmp_path/'rml',pixels=16,starts=1,max_iterations=100)
    assert result['input_unit']=='ADC^2' and result['output_unit']=='relative flux/pixel'
    with fits.open(tmp_path/'rml/relative-model.fits',checksum=True) as f:
        assert f[0].header['BUNIT']=='1/pixel' and f[0].header['FLUXREF']=='ARBITRARY'
        assert f[0].header['POSREF']=='ASSUMED' and f[0].verify_checksum()==1
    with pytest.raises(FileExistsError): image_closure(tmp_path/'adc.npz',tmp_path/'rml')
