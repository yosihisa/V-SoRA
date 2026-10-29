"""既定比較平滑化と保存156の局所near-null。画像を再fitしない。"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
from scipy.linalg import eigh
from scipy.ndimage import gaussian_filter
from vsora_imaging.experiment import compare_relative

PIXELS, PIXEL_ARCSEC, FWHM = 32, 16., 110.
CUTS = (1e-6, 1e-8, 1e-10)


def leading_pair(matrix):
    n = len(matrix)
    values, vectors = eigh(matrix, subset_by_index=[n-1, n-1])
    return float(values[0]), vectors[:, 0]


def helmert(size):
    h = np.zeros((size, size-1))
    for k in range(1, size):
        h[:k, k-1] = 1/np.sqrt(k*(k+1))
        h[k, k-1] = -k/np.sqrt(k*(k+1))
    np.testing.assert_allclose(h.T@h, np.eye(size-1), rtol=0., atol=1e-12)
    np.testing.assert_allclose(h.sum(axis=0), 0., rtol=0., atol=1e-12)
    return h


def smoothing_operator():
    sigma = FWHM/(np.sqrt(8*np.log(2))*PIXEL_ARCSEC)
    radius = int(4*sigma+.5)
    offset = np.arange(-radius, radius+1)
    kernel = np.exp(-offset**2/(2*sigma**2)); kernel /= kernel.sum()
    pad = int(np.ceil(4*sigma))+2
    size = PIXELS+2*pad
    matrix = np.zeros((size, PIXELS))
    for column in range(PIXELS):
        matrix[column+pad+offset, column] = kernel
    np.testing.assert_allclose(matrix.sum(axis=0), 1., rtol=0., atol=1e-13)
    def apply(x):
        return matrix @ np.asarray(x).reshape(PIXELS, PIXELS) @ matrix.T
    center = np.zeros((PIXELS, PIXELS)); center[16, 16] = 1.
    edge = np.zeros_like(center); edge[0, 0] = 1.
    yy, xx = np.indices(center.shape)
    signed = (-1.)**(xx+yy)
    uniform = np.ones_like(center)/center.size
    errors = []
    for x in (center, edge, signed, uniform):
        expected = gaussian_filter(np.pad(x, pad), sigma, mode='constant')
        actual = apply(x)
        np.testing.assert_allclose(actual, expected, rtol=1e-11, atol=1e-13)
        np.testing.assert_allclose(actual.sum(), x.sum(), rtol=1e-11, atol=1e-12)
        errors.append(float(np.max(abs(actual-expected))))
    np.testing.assert_allclose(apply(.3*center-.7*edge), .3*apply(center)-.7*apply(edge), rtol=1e-11, atol=1e-13)
    big_pad = pad+PIXELS-1
    big = gaussian_filter(np.pad(edge, big_pad), sigma, mode='constant')
    embedded = np.pad(apply(edge), PIXELS-1)
    np.testing.assert_allclose(big, embedded, rtol=1e-11, atol=1e-13)
    metrics, aa, bb, registered = compare_relative(center, edge, PIXEL_ARCSEC,
                                                  common_beam_arcsec=FWHM, max_shift_pixels=0)
    raw = np.linalg.norm(apply(edge)-apply(center))/np.linalg.norm(apply(center))
    np.testing.assert_allclose([metrics['raw_nrmse'], metrics['registered_nrmse']], raw, rtol=1e-11, atol=1e-12)
    window = (slice(pad, pad+PIXELS),)*2
    np.testing.assert_allclose(aa, apply(center)[window], rtol=1e-11, atol=1e-13)
    np.testing.assert_allclose(bb, apply(edge)[window], rtol=1e-11, atol=1e-13)
    np.testing.assert_allclose(registered, bb, rtol=1e-11, atol=1e-13)
    assert metrics['registration_max_shift_pixels'] == 0
    return matrix, kernel, apply, {'sigma_pixels': float(sigma), 'truncate': 4., 'radius_pixels': radius,
        'padding_pixels_no_translation': pad, 'full_support_shape': [size, size],
        'maximum_direct_kernel_difference': max(errors), 'edge_cropped_flux': float(bb.sum()),
        'full_support_flux': float(apply(edge).sum()), 'zero_translation_API_raw_nrmse_control': float(raw),
        'default_large_padding_embedding_checked': True, 'signed_input_passed_to_compare_relative': False}


def run(archive, output):
    source = Path(archive); previous = json.loads((source/'summary.json').read_text())
    assert previous['stage'] == 156
    out = Path(output)
    if out.exists():
        raise FileExistsError('choose a new smoothed-null validation output')
    out.mkdir(parents=True); began = time.monotonic()
    one, kernel, blur, controls = smoothing_operator()
    h = helmert(PIXELS**2)
    gram = np.kron(one.T@one, one.T@one)
    tangent_gram = h.T@gram@h
    total = float(np.trace(tangent_gram))
    unit = np.ones(PIXELS**2)/PIXELS
    independent_total = float(np.trace(gram)-np.linalg.norm(blur(unit))**2)
    np.testing.assert_allclose(total, independent_total, rtol=1e-9, atol=1e-11)
    all_leading, _ = leading_pair(tangent_gram)
    arrays = {'one_dimensional_operator': one, 'normalized_kernel': kernel}
    cases = []
    with np.load(source/'arrays.npz', allow_pickle=False) as saved:
        for old in previous['cases']:
            label = old['case']
            if old['state'] != 'verified_local_jacobian':
                cases.append({'case': label, 'state': old['state'], 'subspace_results': None,
                              'source_input_sha256': old['input_sha256']})
                continue
            j = saved[label+'_whitened_tangent_jacobian']
            prior = saved[label+'_prior_q']
            np.testing.assert_allclose(blur(prior), gaussian_filter(np.pad(prior.reshape(32, 32), controls['padding_pixels_no_translation']), controls['sigma_pixels'], mode='constant'), rtol=1e-11, atol=1e-13)
            projected = j@h
            assert np.linalg.norm(projected@h.T-j)/np.linalg.norm(j) < 1e-12
            _, singular, vt = np.linalg.svd(projected, full_matrices=True)
            np.testing.assert_allclose(vt@vt.T, np.eye(len(vt)), rtol=0., atol=1e-10)
            transformed = vt@tangent_gram@vt.T
            arrays[label+'_singular_values_in_tangent_coordinates'] = singular
            results = []
            for cut in CUTS:
                rank = int(np.count_nonzero(singular > cut*singular[0]))
                assert rank == old['numerical_ranks'][str(cut)]
                block = transformed[rank:, rank:]
                energy = float(np.trace(block))
                # 直接blurした観測row-spaceのエネルギーを全接空間から引く独立対照。
                complement = sum(float(np.linalg.norm(blur(h@row))**2) for row in vt[:rank])
                np.testing.assert_allclose(energy, independent_total-complement, rtol=1e-9, atol=1e-11)
                leading, coefficient = leading_pair(block)
                residual = np.linalg.norm(block@coefficient-leading*coefficient)/max(abs(leading), 1e-15)
                assert residual < 1e-9
                direction = h@(vt[rank:].T@coefficient)
                image = blur(direction)
                np.testing.assert_allclose(direction@direction, 1., rtol=1e-9, atol=1e-11)
                assert abs(direction.sum()) < 1e-10
                np.testing.assert_allclose(np.linalg.norm(image)**2, leading, rtol=1e-9, atol=1e-11)
                data_response = float(np.linalg.norm(j@direction)/np.linalg.norm(j))
                assert data_response <= 2*cut+1e-12
                angle = .37
                rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
                rotated = block.copy()
                rotated[:2] = rotation.T@rotated[:2]
                rotated[:, :2] = rotated[:, :2]@rotation
                rotated_leading, _ = leading_pair(rotated)
                np.testing.assert_allclose([np.trace(rotated), rotated_leading], [energy, leading], rtol=1e-9, atol=1e-11)
                frobenius_ratio = energy/total
                spectral_ratio = float(np.sqrt(leading/all_leading))
                assert -1e-12 <= frobenius_ratio <= 1+1e-12 and 0 <= spectral_ratio <= 1+1e-12
                name = label+'_cut'+str(cut)
                arrays[name+'_signed_unit_direction'] = direction
                arrays[name+'_full_support_blurred_direction'] = image
                results.append({'relative_cut': cut, 'rank': rank, 'subspace_dimension': len(vt)-rank,
                    'Frobenius_squared_ratio_to_all_unit_sum_directions': frobenius_ratio,
                    'spectral_norm_ratio_to_all_unit_sum_directions': spectral_ratio,
                    'subspace_blur_spectral_norm': float(np.sqrt(leading)),
                    'direct_complement_energy_difference': abs(energy-(independent_total-complement)),
                    'eigenpair_relative_residual': float(residual),
                    'basis_rotation_trace_absolute_difference': float(abs(np.trace(rotated)-energy)),
                    'basis_rotation_leading_eigenvalue_absolute_difference': float(abs(rotated_leading-leading)),
                    'unit_signed_witness_relative_data_response': data_response})
            cases.append({'case': label, 'state': 'verified_operator_on_local_subspaces',
                          'source_input_sha256': old['input_sha256'], 'subspace_results': results})
    result = {'stage': 157, 'state': 'complete', 'operator_controls': controls, 'cases': cases,
        'total_unit_sum_tangent_blur_Frobenius_squared': total,
        'total_unit_sum_tangent_blur_spectral_norm': float(np.sqrt(all_leading)),
        'rotation_angle_fixed_rad': .37, 'MC_trials': 0, 'seed_MCSE_applicable': False,
        'image_optimizer_calls': 0, 'main_translation_optimization_calls': 0,
        'source156_summary_sha256': hashlib.sha256((source/'summary.json').read_bytes()).hexdigest(),
        'source156_arrays_sha256': hashlib.sha256((source/'arrays.npz').read_bytes()).hexdigest(),
        'product_code_changed': False, 'physical_primary_beam_or_image_confidence_calibrated': False,
        'scope': 'Fixed full-support comparison smoothing, no registration. Basis-invariant operator norms on saved156 local unit-sum numerical null/near-null subspaces. Ratios are not power retention, information-loss fraction, posterior variance, actual beam resolution or image recovery performance.'}
    (out/'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    np.savez_compressed(out/'arrays.npz', **arrays)
    origins = {n: m.__file__ for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None)}
    (out/'runtime-private.json').write_text(json.dumps({'module_paths': origins,
        'wall_s': time.monotonic()-began, 'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}, indent=2)+'\n')
    print(json.dumps(result))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); run(args.archive, args.output)
