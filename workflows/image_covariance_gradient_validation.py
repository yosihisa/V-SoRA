"""供給受信機の画像依存Cの連鎖微分と非一意性。製品尤度は変更しない。"""
import argparse
from itertools import combinations
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
from scipy.special import softmax
from vsora_correlator.gaussian_likelihood import gaussian_nll, sample_second_moment
from vsora_simulator.sky_covariance import sky_station_covariance
from vsora_simulator.visibility import direct_visibility

PIXELS, PIXEL_ARCSEC, FLUX, MODES = 8, 45., 1000., 12
NOISE = np.array([2000., 3000., 4000.])
GAINS = np.array([1.2*np.exp(.2j), .8*np.exp(-.4j), 1.1*np.exp(.7j)])
PAIRS = np.array(list(combinations(range(3), 2)))
FD_STEPS = (1e-4, 3e-5)


def coordinates():
    base = np.array([[0., 0., 0.], [1100., 450., 700.], [-650., 1400., -1100.]])
    result = []
    for angle in (0., .07, -.05, .12):
        c, s = np.cos(angle), np.sin(angle)
        rotation = np.array([[c, -s, 0.], [s, c, 0.], [0., 0., 1.]])
        result.append(base@rotation.T)
    return np.array(result)


def responses(coords):
    """製品tangent_gridを呼ばず、全点画素をrow/columnから列挙する。"""
    directions = []
    radians = np.pi/(180*3600)
    for row in range(PIXELS):
        for column in range(PIXELS):
            l = (column-PIXELS//2)*PIXEL_ARCSEC*radians
            m = (row-PIXELS//2)*PIXEL_ARCSEC*radians
            directions.append([l, m, np.sqrt(1-l*l-m*m)-1])
    direction = np.array(directions)
    return np.exp(2j*np.pi*(coords-coords[0])@direction.T)


def product_covariance(coords, q):
    c = sky_station_covariance(coords, FLUX*q.reshape(PIXELS, PIXELS),
                               PIXEL_ARCSEC, NOISE)['station_covariance_jy']
    return GAINS[:, None]*c*GAINS.conj()[None, :]


def direct_covariance(response, q):
    source = sum(FLUX*q[p]*np.outer(response[:, p], response[:, p].conj())
                 for p in range(PIXELS**2))
    return GAINS[:, None]*(source+np.diag(NOISE))*GAINS.conj()[None, :]


def real_voltage_value(q, coords, operators, voltages):
    """独立の実6次元密度を全raw電圧で評価。Sや既存NLLは使わない。"""
    value = 0.
    for response, x in zip(operators, voltages, strict=True):
        c = direct_covariance(response, q)
        sigma = .5*np.block([[c.real, -c.imag], [c.imag, c.real]])
        sign, logdet = np.linalg.slogdet(sigma)
        assert sign > 0
        real = np.concatenate([x.real, x.imag], axis=1)
        quadratic = np.sum(real*np.linalg.solve(sigma, real.T).T)
        value += .5*(MODES*(6*np.log(2*np.pi)+logdet)+quadratic)
    return float(value)


def evaluate(z, coords, operators, moments):
    q = softmax(z)
    value = 0.; gradient_q = np.zeros(len(q)); trace_only = np.zeros(len(q))
    covariances = []
    for station, response, moment in zip(coords, operators, moments, strict=True):
        c = product_covariance(station, q)
        independent = direct_covariance(response, q)
        np.testing.assert_allclose(c, independent, rtol=1e-12, atol=1e-10)
        for i, j in PAIRS:
            visibility = direct_visibility(station[j]-station[i], FLUX*q.reshape(PIXELS, PIXELS), PIXEL_ARCSEC)
            np.testing.assert_allclose(c[i, j], GAINS[i]*GAINS[j].conj()*visibility, rtol=1e-12, atol=1e-10)
        value += gaussian_nll(c, moment, MODES)+MODES*3*np.log(np.pi)
        precision = np.linalg.solve(c, np.eye(3))
        data_term = -precision@moment@precision
        b = GAINS[:, None]*response
        gradient_q += MODES*FLUX*np.einsum('ip,ij,jp->p', b.conj(), precision+data_term, b).real
        trace_only += MODES*FLUX*np.einsum('ip,ij,jp->p', b.conj(), data_term, b).real
        covariances.append(c)
    gradient = q*(gradient_q-q@gradient_q)
    missing_logdet = q*(trace_only-q@trace_only)
    return float(value), gradient, missing_logdet, np.array(covariances)


def run(output):
    out = Path(output)
    if out.exists():
        raise FileExistsError('choose a new conditional-image covariance validation output')
    out.mkdir(parents=True); began = time.monotonic()
    coords = coordinates(); operators = np.array([responses(station) for station in coords])
    index = np.arange(PIXELS**2)
    reference_z = .3*np.sin(index*.37)+.2*np.cos(index*.19)
    reference_q = softmax(reference_z)
    voltages = []; moments = []
    for station in coords:
        c = product_covariance(station, reference_q)
        lower = np.linalg.cholesky(c)
        x = np.array([np.sqrt(3)*phase*lower[:, column]
                      for column in range(3) for phase in (1, -1, 1j, -1j)])
        moment = sample_second_moment(x)
        np.testing.assert_allclose(moment, c, rtol=1e-12, atol=1e-10)
        np.testing.assert_allclose(x.mean(axis=0), 0., rtol=0., atol=1e-12)
        np.testing.assert_allclose(x.T@x/MODES, 0., rtol=0., atol=1e-10)
        voltages.append(x); moments.append(moment)
    voltages, moments = np.array(voltages), np.array(moments)
    arrays = {'station_coords_lambda': coords, 'supplied_gains': GAINS, 'supplied_receiver_Jy': NOISE,
              'deterministic_voltage_probes': voltages, 'observed_second_moments': moments,
              'reference_q': reference_q}
    states = []
    for label, z in [('uniform', np.zeros(64)),
                     ('asymmetric', .4*np.cos(index*.23)-.1*np.sin(index*.41)),
                     ('reference_moment', reference_z)]:
        value, gradient, missing_logdet, covariances = evaluate(z, coords, operators, moments)
        q = softmax(z)
        independent = real_voltage_value(q, coords, operators, voltages)
        np.testing.assert_allclose(value, independent, rtol=1e-11, atol=1e-9)
        assert abs(gradient.sum()) < 1e-10
        checks = []
        for step in FD_STEPS:
            numeric = np.empty(64)
            for k in range(64):
                delta = np.zeros(64); delta[k] = step
                plus = real_voltage_value(softmax(z+delta), coords, operators, voltages)
                minus = real_voltage_value(softmax(z-delta), coords, operators, voltages)
                numeric[k] = (plus-minus)/(2*step)
            np.testing.assert_allclose(gradient, numeric, rtol=2e-5, atol=2e-7)
            checks.append({'step': step, 'maximum_absolute_difference': float(np.max(abs(gradient-numeric))),
                           'difference_norm': float(np.linalg.norm(gradient-numeric))})
            arrays[f'{label}_finite_difference_{step}'] = numeric
        if label == 'reference_moment':
            assert np.max(abs(gradient)) < 1e-9
            assert np.max(abs(missing_logdet)) > 1e-6
        arrays.update({label+'_q': q, label+'_gradient_z': gradient,
                       label+'_missing_logdet_gradient_z': missing_logdet,
                       label+'_covariances': covariances})
        states.append({'label': label, 'normalized_raw_voltage_nll': value,
                       'real_density_value': independent, 'absolute_objective_difference': abs(value-independent),
                       'gradient_inf_norm': float(np.max(abs(gradient))),
                       'missing_logdet_gradient_inf_norm': float(np.max(abs(missing_logdet))),
                       'finite_difference_checks': checks})
    # geometryのみから線形forwardのnull方向を作る。評価データで方向を選ばない。
    rows = [np.ones(64)]
    for response in operators:
        b = GAINS[:, None]*response
        for i, j in PAIRS:
            coefficient = FLUX*b[i]*b[j].conj()
            rows.extend([coefficient.real, coefficient.imag])
    forward = np.array(rows)
    _, singular, vh = np.linalg.svd(forward, full_matrices=True)
    rank = int(np.count_nonzero(singular > 1e-10*singular[0]))
    direction = vh[-1]; h = .25*reference_q.min()/abs(direction).max()
    plus, minus = reference_q+h*direction, reference_q-h*direction
    assert np.min(plus) > 0 and np.min(minus) > 0 and not np.array_equal(plus, minus)
    np.testing.assert_allclose([plus.sum(), minus.sum()], 1., rtol=0., atol=1e-12)
    np.testing.assert_allclose(forward@direction, 0., rtol=0., atol=1e-9)
    cplus = np.array([product_covariance(station, plus) for station in coords])
    cminus = np.array([product_covariance(station, minus) for station in coords])
    np.testing.assert_allclose(cplus, cminus, rtol=1e-12, atol=1e-10)
    vplus = real_voltage_value(plus, coords, operators, voltages)
    vminus = real_voltage_value(minus, coords, operators, voltages)
    np.testing.assert_allclose(vplus, vminus, rtol=1e-11, atol=1e-9)
    arrays.update(null_direction=direction, nonunique_q_plus=plus, nonunique_q_minus=minus,
                  forward_singular_values=singular, nonunique_covariances_plus=cplus,
                  nonunique_covariances_minus=cminus)
    refused = []
    probes = [('singular_covariance', lambda: gaussian_nll(np.ones((3, 3)), moments[0], MODES)),
              ('negative_receiver', lambda: sky_station_covariance(coords[0], FLUX*reference_q.reshape(8, 8), PIXEL_ARCSEC, [2000., -1., 4000.])),
              ('boolean_modes', lambda: gaussian_nll(moments[0], moments[0], True)),
              ('indefinite_second_moment', lambda: gaussian_nll(moments[0], np.diag([-1., 1., 1.]), MODES))]
    for name, probe in probes:
        try:
            probe()
        except ValueError:
            refused.append(name)
        else:
            raise AssertionError('existing API failed refusal: '+name)
    result = {'stage': 155, 'state': 'complete', 'states': states,
        'model': 'C_t(q)=G[A_t diag(1000 Jy q) A_t^H+diag([2000,3000,4000] Jy)]G^H; supplied gain/flux/receiver, scalar beam, iid proper complex Gaussian model; no selection',
        'pixels': 8, 'stations': 3, 'cells': 4, 'deterministic_probes_per_cell': 12,
        'MC_trials': 0, 'seed_MCSE_applicable': False, 'image_optimizer_calls': 0,
        'finite_probes_are_Gaussian_samples': False,
        'nonuniqueness': {'forward_shape': list(forward.shape), 'numerical_rank': rank,
            'relative_singular_tolerance': 1e-10, 'null_dimension_at_least_from_rows': 64-len(rows),
            'image_L2_difference': float(np.linalg.norm(plus-minus)),
            'maximum_covariance_difference': float(np.max(abs(cplus-cminus))),
            'normalized_nll_difference': float(abs(vplus-vminus)), 'positive_unit_sum_both': True},
        'existing_API_refusals': refused, 'new_production_likelihood_or_RML': False,
        'unknown_receiver_or_real_observation_or_low_SNR_closure_model_validated': False,
        'scope': 'Conditional supplied-receiver image-covariance calculation and gradient; independent real raw-voltage density and finite differences. Constructive nonuniqueness even with supplied receivers. No adopted production model, image fit, filter/quantization/rate inference/gating or actual Cas A confidence.'}
    (out/'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    np.savez_compressed(out/'arrays.npz', **arrays)
    origins = {n: m.__file__ for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None)}
    (out/'runtime-private.json').write_text(json.dumps({'module_paths': origins,
        'wall_s': time.monotonic()-began, 'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}, indent=2)+'\n')
    print(json.dumps(result))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    run(parser.parse_args().output)
