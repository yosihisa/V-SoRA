"""保存signed方向を非負画像へ動かす有限参照。画像を再fitしない。"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
from vsora_formats.spectral import load_spectral
from vsora_imaging.objective_evaluation import evaluate_closure_image
from vsora_imaging.rml import ClosureObjective

FRACTIONS = (.25, .5, .75)


def direct_fourier(uvw):
    directions = []
    for row in range(32):
        for column in range(32):
            l, m = np.array([column-16, row-16])*16*np.pi/(180*3600)
            directions.append([l, m, np.sqrt(1-l*l-m*m)-1])
    return np.exp(-2j*np.pi*np.asarray(uvw).reshape(-1, 3) @ np.array(directions).T)


def predictions(model, blocks):
    result = []
    for cell, name, matrix, lower, observed in blocks:
        v = model[cell]
        if name == 'phase':
            a = np.prod(np.where(matrix > 0, v[None, :], 1.), axis=1)
            b = np.prod(np.where(matrix < 0, v.conj()[None, :], 1.), axis=1)
            result.append(np.angle(a*b))
        else:
            a = np.prod(np.where(matrix > 0, abs(v)[None, :], 1.), axis=1)
            b = np.prod(np.where(matrix < 0, abs(v)[None, :], 1.), axis=1)
            result.append(np.log(a/b))
    return result


def differences(a, b, blocks):
    result = []
    for x, y, block in zip(a, b, blocks, strict=True):
        d = x-y
        result.append(np.angle(np.exp(1j*d)) if block[1] == 'phase' else d)
    return result


def whiten(values, blocks, count):
    return np.concatenate([np.linalg.solve(block[3], value)/np.sqrt(count)
                           for value, block in zip(values, blocks, strict=True)])


def analyze(data, label, saved, directions):
    settings = dict(pixel_arcsec=16., min_snr=10., prior_fwhm_arcsec=240., entropy=0., tsv=0., centroid=0.)
    args = [data[n] for n in ('uvw_lambda', 'visibilities', 'weights', 'pairs')]
    obj = ClosureObjective(*args, pixels=32, **settings)
    q = saved[label+'_prior_q']; j = saved[label+'_whitened_tangent_jacobian']
    d = directions[label+'_cut1e-10_signed_unit_direction']
    np.testing.assert_array_equal(q, obj.prior)
    np.testing.assert_array_equal(saved[label+'_baseline_valid'], obj.closures['baseline_valid'])
    assert abs(d.sum()) < 1e-10
    np.testing.assert_allclose(d @ d, 1., rtol=1e-9, atol=1e-11)
    active = np.flatnonzero(d != 0)
    limiting = int(active[np.argmin(q[active]/abs(d[active]))])
    radius = float(q[limiting]/abs(d[limiting]))
    boundary = np.minimum(q+radius*d, q-radius*d)
    assert boundary.min() >= -1e-15 and abs(boundary[limiting]) <= 1e-15
    assert min((q+1.01*radius*d).min(), (q-1.01*radius*d).min()) < 0
    f = direct_fourier(data['uvw_lambda'])
    np.testing.assert_allclose(f, obj.fourier, rtol=1e-11, atol=1e-12)
    blocks = []
    for cell_index, cell in enumerate(obj.cells):
        for name, matrix, observed, factor in cell:
            if factor is None:
                continue
            index = len(blocks)
            lower = np.tril(factor[0])
            np.testing.assert_array_equal(matrix, saved[f'{label}_block{index}_selected_design'])
            np.testing.assert_array_equal(lower, saved[f'{label}_block{index}_covariance_lower'])
            blocks.append((cell_index, name, matrix, lower, observed))
    shape = (-1, obj.shape[-1])
    baseline_model = (f @ q).reshape(shape)
    p0 = predictions(baseline_model, blocks)
    observed = [b[4] for b in blocks]
    r0 = whiten(differences(p0, observed, blocks), blocks, obj.count)
    np.testing.assert_allclose(r0, saved[label+'_whitened_residual'], rtol=1e-9, atol=1e-8)
    value, gradient = obj._image_value_gradient(q)
    np.testing.assert_allclose(j.T @ r0, gradient-gradient.mean(), rtol=1e-8, atol=1e-8)
    np.testing.assert_allclose(value, .5*float(r0 @ r0), rtol=1e-9, atol=1e-8)
    one = directions['one_dimensional_operator']
    blur = lambda image: one @ image.reshape(32, 32) @ one.T
    bd = directions[label+'_cut1e-10_full_support_blurred_direction']
    np.testing.assert_allclose(blur(d), bd, rtol=1e-9, atol=1e-13)
    result = []; arrays = {'prior_q': q, 'signed_direction': d, 'baseline_whitened_residual': r0}
    for fraction, sign in [(0., 0)] + [(h, s) for h in FRACTIONS for s in (-1, 1)]:
        amplitude = sign*fraction*radius
        candidate = q+amplitude*d
        assert candidate.min() > 0 and np.all(candidate >= .25*q-1e-15)
        np.testing.assert_allclose(candidate.sum(), 1., rtol=0., atol=1e-12)
        model = (f @ candidate).reshape(shape)
        minimum = float(abs(model).min())
        row = {'fraction': fraction, 'sign': sign, 'amplitude': amplitude,
               'candidate_sum': float(candidate.sum()), 'minimum_pixel': float(candidate.min()),
               'minimum_model_visibility': minimum}
        key = f'fraction{fraction}_sign{sign}'
        arrays[key+'_candidate_q'] = candidate
        np.testing.assert_allclose(blur(candidate)-blur(q), amplitude*bd, rtol=1e-9, atol=1e-13)
        row['full_support_blurred_distance_to_prior'] = float(np.linalg.norm(blur(candidate)-blur(q)))
        if minimum < 1e-14:
            result.append({**row, 'state': 'blocked_model_zero', 'data_loss': None})
            continue
        predicted = predictions(model, blocks)
        residual_blocks = differences(predicted, observed, blocks)
        margins = [np.pi-abs(v) for v, b in zip(residual_blocks, blocks, strict=True) if b[1] == 'phase']
        margin = float(min(np.min(x) for x in margins)) if margins else None
        row['phase_residual_branch_margin'] = margin
        if margin is not None and margin <= 1e-4:
            result.append({**row, 'state': 'blocked_branch_reference', 'data_loss': None})
            continue
        residual = whiten(residual_blocks, blocks, obj.count)
        change = whiten(differences(predicted, p0, blocks), blocks, obj.count)
        crossing = float(np.linalg.norm(residual-r0-change)) > 1e-8
        # 共分散行列への直接solveはAPI内部のCholesky solveと別の計算経路。
        independent_loss = sum(float(v @ np.linalg.solve(b[3] @ b[3].T, v))
                               for v, b in zip(residual_blocks, blocks, strict=True))/(2*obj.count)
        actual = evaluate_closure_image(*args, candidate.reshape(32, 32), **settings)
        metrics = actual['metrics']
        np.testing.assert_allclose(metrics['data_loss'], independent_loss, rtol=1e-9, atol=1e-8)
        assert metrics['independent_closure_counts'] == obj.count_by_type
        assert metrics['entropy_loss'] == metrics['tsv_loss'] == metrics['centroid_loss'] == 0
        linear = j @ (amplitude*d)
        row.update(state='evaluated_fixed_candidate', branch_crossing_from_prior=crossing,
                   data_loss=metrics['data_loss'], independent_data_loss=independent_loss,
                   API_loss_absolute_difference=abs(metrics['data_loss']-independent_loss),
                   whitened_prediction_distance_to_prior=float(np.linalg.norm(change)),
                   linear_prediction_distance=float(np.linalg.norm(linear)),
                   nonlinear_minus_linear_norm=float(np.linalg.norm(change-linear)),
                   local_quadratic_data_loss=None if crossing else .5*float((r0+linear) @ (r0+linear)),
                   image_L2_distance_to_prior=float(np.linalg.norm(candidate-q)),
                   optimizer_executed=actual['optimizer_executed'])
        arrays[key+'_whitened_prediction_change'] = change
        arrays[key+'_linear_change'] = linear
        result.append(row)
    return {'case': label, 'state': 'finite_positive_candidates', 'positivity_radius': radius,
            'limiting_pixel_index': limiting, 'limiting_row_column': list(divmod(limiting, 32)),
            'closure_count': obj.count, 'closure_counts': obj.count_by_type, 'candidates': result}, arrays


def run(jacobian_archive, direction_archive, input_archive, output):
    jacobian, direction, source = map(Path, (jacobian_archive, direction_archive, input_archive))
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for parent in (jacobian, direction)
              for p in (parent/'summary.json', parent/'arrays.npz')}
    previous = json.loads((jacobian/'summary.json').read_text())
    smooth = json.loads((direction/'summary.json').read_text())
    assert previous['stage'] == 156 and smooth['stage'] == 157
    assert smooth['source156_arrays_sha256'] == before[str(jacobian/'arrays.npz')]
    out = Path(output)
    if out.exists():
        raise FileExistsError('choose a new finite-positive output')
    out.mkdir(parents=True); began = time.monotonic()
    rows = []; arrays = {}
    with np.load(jacobian/'arrays.npz', allow_pickle=False) as saved, np.load(direction/'arrays.npz', allow_pickle=False) as directions:
        for old in previous['cases']:
            label = old['case']; path = source/label/'fitter.npz'
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest == old['input_sha256']
            before[str(path)] = digest
            data = load_spectral(path)
            assert data['metadata']['config']['source']['model'] == 'unknown'
            assert not data['metadata']['generating_truth_supplied_to_fitter']
            if old['state'] == 'no_high_snr_closures':
                try:
                    ClosureObjective(data['uvw_lambda'], data['visibilities'], data['weights'], data['pairs'])
                except ValueError as exc:
                    assert str(exc) == 'no high SNR independent closure measurements'
                else:
                    raise AssertionError('expected inherited no-high-SNR refusal')
                rows.append({'case': label, 'state': old['state'], 'candidates': None})
                continue
            assert old['state'] == 'verified_local_jacobian'
            row, result = analyze(data, label, saved, directions)
            row['source_input_sha256'] = digest
            rows.append(row); arrays.update({label+'_'+key: value for key, value in result.items()})
    assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest() == h for n, h in before.items())
    result = {'stage': 158, 'state': 'complete', 'cases': rows, 'fractions_fixed': list(FRACTIONS),
              'MC_trials': 0, 'seed_MCSE_applicable': False, 'image_optimizer_calls': 0,
              'new_SVD_or_differentiation': False, 'product_code_changed': False,
              'translation_optimization_calls': 0, 'truth_or_saved_fit_image_read': False,
              'confidence_or_image_recovery_success_calibrated': False,
              'scope': 'Finite constructed nonnegative unit-sum candidates from saved157 signed directions. Fixed observed high-SNR closure support/covariance. Positivity radius is not a confidence radius. No fit, likelihood adoption, physical beam or causal exposure comparison.'}
    (out/'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    np.savez_compressed(out/'arrays.npz', **arrays)
    origins = {n: m.__file__ for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None)}
    (out/'runtime-private.json').write_text(json.dumps({'module_paths': origins,
        'wall_s': time.monotonic()-began, 'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}, indent=2)+'\n')
    print(json.dumps(result)); return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('jacobian-archive', 'direction-archive', 'input-archive', 'output'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args(); run(**vars(args))
