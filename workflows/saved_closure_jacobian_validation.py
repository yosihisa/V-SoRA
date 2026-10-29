"""保存133の固定priorでClosure局所微分を照合。画像を再fitしない。"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
from scipy.linalg import solve_triangular
from vsora_formats.spectral import load_spectral
from vsora_imaging.rml import ClosureObjective

CASES = ('high_a_t0.3', 'high_a_t3', 'weak_a_t0.3')
STEPS = (1e-7, 3e-8)
RANK_THRESHOLDS = (1e-6, 1e-8, 1e-10)


def direct_fourier(uvw, pixels, pixel_arcsec):
    directions = []
    radians = np.pi/(180*3600)
    for row in range(pixels):
        for column in range(pixels):
            l = (column-pixels//2)*pixel_arcsec*radians
            m = (row-pixels//2)*pixel_arcsec*radians
            directions.append([l, m, np.sqrt(1-l*l-m*m)-1])
    return np.exp(-2j*np.pi*np.asarray(uvw).reshape(-1, 3)@np.array(directions).T)


def independent_predictions(model, descriptors):
    values = []
    for cell, name, matrix, lower, observed in descriptors:
        v = model[cell]
        if name == 'phase':
            positive = np.prod(np.where(matrix > 0, v[None, :], 1.), axis=1)
            negative = np.prod(np.where(matrix < 0, v.conj()[None, :], 1.), axis=1)
            values.append(np.angle(positive*negative))
        else:
            positive = np.prod(np.where(matrix > 0, abs(v)[None, :], 1.), axis=1)
            negative = np.prod(np.where(matrix < 0, abs(v)[None, :], 1.), axis=1)
            values.append(np.log(positive/negative))
    return values


def whiten_blocks(values, descriptors, count):
    return np.concatenate([solve_triangular(d[3], value, lower=True)/np.sqrt(count)
                           for value, d in zip(values, descriptors, strict=True)])


def analyze(data, label):
    base = {'case': label, 'input_shape': list(data['visibilities'].shape), 'pixels': 32,
            'pixel_arcsec': 16., 'min_snr': 10., 'reference': 'unchanged_constructor_prior_fwhm240',
            'regularization_included_in_local_matrix': False}
    try:
        objective = ClosureObjective(data['uvw_lambda'], data['visibilities'], data['weights'], data['pairs'],
            pixels=32, pixel_arcsec=16., min_snr=10., prior_fwhm_arcsec=240., entropy=0., tsv=0., centroid=0.)
    except ValueError as exc:
        if str(exc) != 'no high SNR independent closure measurements':
            raise
        return {**base, 'state': 'no_high_snr_closures', 'closure_count': 0,
                'jacobian_shape': None, 'numerical_ranks': None, 'data_loss': None}, {}
    q = objective.prior.copy(); size = len(q)
    direct = direct_fourier(data['uvw_lambda'], 32, 16.)
    np.testing.assert_allclose(direct, objective.fourier, rtol=1e-11, atol=1e-12)
    f = objective.fourier.reshape(-1, objective.shape[-1], size)
    model = (direct@q).reshape(-1, objective.shape[-1])
    minimum = float(np.min(abs(model)))
    if minimum < 1e-14:
        return {**base, 'state': 'blocked_model_zero', 'closure_count': objective.count,
                'minimum_model_visibility': minimum, 'jacobian_shape': None,
                'numerical_ranks': None, 'data_loss': None}, {}
    descriptors = []; derivative_blocks = []; observed_blocks = []
    for cell_index, cell in enumerate(objective.cells):
        for name, matrix, observed, factor in cell:
            if factor is None:
                continue
            assert bool(factor[1])
            lower = np.tril(factor[0])
            variance = objective.closures['baseline_variance'].reshape(model.shape)[cell_index]
            covariance = (matrix*variance)@matrix.T
            np.testing.assert_allclose(lower@lower.T, covariance, rtol=1e-11, atol=1e-12)
            descriptors.append((cell_index, name, matrix, lower, observed))
            observed_blocks.append(observed)
            ratio = f[cell_index]/model[cell_index, :, None]
            derivative_blocks.append(matrix@(ratio.imag if name == 'phase' else ratio.real))
    predicted = independent_predictions(model, descriptors)
    residuals = []; margins = []
    for prediction, descriptor in zip(predicted, descriptors, strict=True):
        residual = prediction-descriptor[4]
        if descriptor[1] == 'phase':
            residual = np.angle(np.exp(1j*residual))
            margins.extend((np.pi-abs(residual)).tolist())
        residuals.append(residual)
    margin = float(min(margins)) if margins else None
    base.update(closure_count=objective.count, closure_counts=objective.count_by_type,
                minimum_model_visibility=minimum, phase_residual_branch_margin=margin)
    if minimum < 1e-14 or (margin is not None and margin <= 1e-4) or q.min() <= max(STEPS):
        return {**base, 'state': 'blocked_local_reference', 'jacobian_shape': None,
                'numerical_ranks': None, 'data_loss': None}, {}
    tangent_blocks = [d-d.mean(axis=1, keepdims=True) for d in derivative_blocks]
    jacobian = whiten_blocks(tangent_blocks, descriptors, objective.count)
    residual = whiten_blocks(residuals, descriptors, objective.count)
    value, gradient = objective._image_value_gradient(q)
    independent_value = .5*float(residual@residual)
    np.testing.assert_allclose(value, independent_value, rtol=1e-9, atol=1e-8)
    expected_gradient = gradient-gradient.mean()
    independent_gradient = jacobian.T@residual
    assert np.linalg.norm(independent_gradient-expected_gradient)/max(np.linalg.norm(expected_gradient), 1e-15) < 1e-8
    # Fourierの線形性でq±h(e_k-1/N)の電圧を作り、微分式を使わずClosure値を差分する。
    df = direct.reshape(f.shape)-direct.reshape(f.shape).mean(axis=2, keepdims=True)
    differences = []; numeric_references = []
    for step in STEPS:
        numeric = np.empty(jacobian.shape)
        for k in range(size):
            plus = independent_predictions(model+step*df[:, :, k], descriptors)
            minus = independent_predictions(model-step*df[:, :, k], descriptors)
            delta = []
            for a, b, descriptor in zip(plus, minus, descriptors, strict=True):
                d = a-b
                if descriptor[1] == 'phase':
                    d = np.angle(np.exp(1j*d))
                delta.append(d/(2*step))
            numeric[:, k] = whiten_blocks(delta, descriptors, objective.count)
        norm_difference = float(np.linalg.norm(jacobian-numeric)/np.linalg.norm(jacobian))
        differences.append({'step': step, 'maximum_absolute_difference': float(np.max(abs(jacobian-numeric))),
                            'relative_norm_difference': norm_difference,
                            'within_original_component_tolerance': bool(np.all(abs(jacobian-numeric) <= 3e-4+3e-4*abs(numeric)))})
        numeric_references.append(numeric)
    ratio = (STEPS[1]/STEPS[0])**2
    richardson = (numeric_references[1]-ratio*numeric_references[0])/(1-ratio)
    np.testing.assert_allclose(jacobian, richardson, rtol=3e-4, atol=3e-4)
    richardson_error = float(np.linalg.norm(jacobian-richardson)/np.linalg.norm(jacobian))
    assert richardson_error <= 1e-5
    convergence = differences[1]['relative_norm_difference']/differences[0]['relative_norm_difference']
    if differences[0]['relative_norm_difference'] >= 1e-8:
        assert .04 <= convergence <= .16
    _, singular, vh = np.linalg.svd(jacobian, full_matrices=False)
    ranks = {str(threshold): int(np.count_nonzero(singular > threshold*singular[0])) for threshold in RANK_THRESHOLDS}
    augmented = np.vstack([np.ones(size)/np.sqrt(size), jacobian/singular[0]])
    _, _, null_basis = np.linalg.svd(augmented, full_matrices=True)
    direction = null_basis[-1]
    null_residual = float(np.linalg.norm(jacobian@direction)/np.linalg.norm(jacobian))
    assert abs(direction.sum()) < 1e-10 and null_residual <= 1e-10
    h = .1*q.min()/abs(direction).max()
    plus, minus = q+h*direction, q-h*direction
    assert min(plus.min(), minus.min()) > 0
    np.testing.assert_allclose([plus.sum(), minus.sum()], 1., rtol=0., atol=1e-12)
    pred_plus = independent_predictions((direct@plus).reshape(model.shape), descriptors)
    pred_minus = independent_predictions((direct@minus).reshape(model.shape), descriptors)
    finite_delta = []
    for a, b, descriptor in zip(pred_plus, pred_minus, descriptors, strict=True):
        d = a-b
        if descriptor[1] == 'phase':
            d = np.angle(np.exp(1j*d))
        finite_delta.append(d)
    finite_norm = float(np.linalg.norm(whiten_blocks(finite_delta, descriptors, objective.count)))
    arrays = {'prior_q': q, 'whitened_tangent_jacobian': jacobian, 'whitened_residual': residual,
              'finite_difference_coarse': numeric_references[0], 'finite_difference_fine': numeric_references[1],
              'finite_difference_Richardson': richardson,
              'singular_values': singular, 'null_direction': direction,
              'null_q_plus': plus, 'null_q_minus': minus,
              'baseline_valid': objective.closures['baseline_valid'],
              'model_visibility': model, 'data_tangent_gradient': independent_gradient}
    for i, descriptor in enumerate(descriptors):
        arrays[f'block{i}_selected_design'] = descriptor[2]
        arrays[f'block{i}_covariance_lower'] = descriptor[3]
    return {**base, 'state': 'verified_local_jacobian', 'jacobian_shape': list(jacobian.shape),
            'unit_sum_image_tangent_dimension': size-1, 'numerical_ranks': ranks,
            'rank_thresholds_relative': list(RANK_THRESHOLDS),
            'tangent_null_dimension_at_main_threshold': size-1-ranks[str(1e-10)],
            'data_loss': value, 'independent_data_loss': independent_value,
            'data_gradient_relative_difference': float(np.linalg.norm(independent_gradient-expected_gradient)/np.linalg.norm(expected_gradient)),
            'finite_difference_checks': differences,
            'formal_derivative_reference': 'Richardson extrapolation of the same fixed two centered differences',
            'Richardson_maximum_absolute_difference': float(np.max(abs(jacobian-richardson))),
            'Richardson_relative_norm_difference': richardson_error,
            'fine_over_coarse_error_norm_ratio': convergence,
            'local_null_relative_Jd': null_residual, 'null_direction_sum': float(direction.sum()),
            'finite_null_pair_image_L2_difference': float(np.linalg.norm(plus-minus)),
            'finite_null_pair_whitened_prediction_difference_norm': finite_norm,
            'finite_null_pair_is_exact_nonlinear_symmetry_claimed': False}, arrays


def run(archive, output):
    source = Path(archive); out = Path(output)
    if out.exists():
        raise FileExistsError('choose a new saved-closure Jacobian output')
    out.mkdir(parents=True); began = time.monotonic()
    rows = []; arrays = {}
    for label in CASES:
        path = source/label/'fitter.npz'
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        data = load_spectral(path)
        assert data['metadata']['config']['source']['model'] == 'unknown'
        assert not data['metadata']['generating_truth_supplied_to_fitter']
        row, result = analyze(data, label)
        row['input_sha256'] = before
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before
        rows.append(row)
        arrays.update({label+'_'+key: value for key, value in result.items()})
        print(json.dumps(row), flush=True)
    result = {'stage': 156, 'state': 'complete', 'cases': rows, 'image_optimizer_calls': 0,
              'MC_trials': 0, 'seed_MCSE_applicable': False, 'product_code_changed': False,
              'new_raw_correlation_or_truth_image_read': False,
              'whitening': 'L^-1 J P / sqrt(independent closure row count); fixed observed within-type/cell covariance',
              'unit_sum_tangent_parameterization': 'P=I-11^T/1024; intensity Euclidean metric, not softmax metric',
              'true_Fisher_or_posterior_or_image_confidence_computed': False,
              'scope': 'Same saved133 observed support and constructor prior. Local forward Jacobian/rank only; fixed high-SNR covariance, shared basis. No production likelihood adoption, refit, causal exposure comparison, real hardware or physical gauge identification.'}
    (out/'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    np.savez_compressed(out/'arrays.npz', **arrays)
    origins = {n: m.__file__ for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None)}
    (out/'runtime-private.json').write_text(json.dumps({'module_paths': origins,
        'wall_s': time.monotonic()-began, 'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); run(args.archive, args.output)
