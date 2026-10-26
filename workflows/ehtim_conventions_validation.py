"""外部RMLの前提を、点画素・相対visibilityの固定対照で確認する。"""
import argparse
from copy import deepcopy
import hashlib
from itertools import combinations
import json
from pathlib import Path
import numpy as np
from vsora_observation.geometry import ARCSEC_RAD, C_M_S, tangent_grid
from vsora_formats.spectral import load_spectral, validate_spectral
from vsora_simulator.visibility import direct_visibility
from vsora_simulator.sky import synthetic_sky
from vsora_imaging.closure import form_closures, wrap_phase


def image_transfer(image, uv_native, pixel_arcsec):
    """東/北の点画素から外部の逆順・幾何中心格子へ。w項は含めない。"""
    image = np.asarray(image); uv = np.asarray(uv_native)
    if (image.ndim != 2 or image.shape[0] != image.shape[1] or image.shape[0] < 2
            or np.iscomplexobj(image) or not np.isfinite(image).all() or np.any(image < 0)
            or not image.sum() > 0 or uv.ndim < 2 or uv.shape[-1] != 3
            or np.iscomplexobj(uv) or not np.isfinite(uv).all()
            or isinstance(pixel_arcsec, bool) or not np.isfinite(pixel_arcsec) or pixel_arcsec <= 0):
        raise ValueError('finite nonnegative square image, uvw and positive pixel size required')
    n = image.shape[0]; tangent_grid(n, pixel_arcsec)
    delta = (n//2-(n-1)/2)*pixel_arcsec*ARCSEC_RAD
    correction = np.exp(2j*np.pi*delta*(uv[..., 0]+uv[..., 1]))
    return image[::-1, ::-1].copy(), -uv[..., :2].copy(), correction


def w_phase_bound(uvw, pixels, pixel_arcsec):
    """正の総量1の点画素モデルに対する、w項省略の保守的な複素差上限。"""
    uvw = np.asarray(uvw)
    if (uvw.ndim < 2 or uvw.shape[-1] != 3 or not uvw.size or np.iscomplexobj(uvw)
            or not np.isfinite(uvw).all() or type(pixels) is not int or pixels < 2
            or isinstance(pixel_arcsec, bool) or not np.isfinite(pixel_arcsec) or pixel_arcsec <= 0):
        raise ValueError('finite uvw, integer pixels and positive pixel size required')
    l, m = tangent_grid(pixels, pixel_arcsec); radius2 = l*l+m*m
    # 小さい角度でsqrt(1-r²)-1を直接引き算しない。
    maximum_n = float(np.max(radius2/(1+np.sqrt(1-radius2))))
    phase = float(2*np.pi*np.max(np.abs(uvw[..., 2]))*maximum_n)
    return {'maximum_abs_w_lambda': float(np.max(np.abs(uvw[..., 2]))),
            'maximum_phase_rad': phase, 'normalized_visibility_absolute_bound': float(2*np.sin(min(phase, np.pi)/2)),
            'assumes_nonnegative_unit_sum_point_pixels': True}


def spectral_channels(data, *, relative_scale=1., min_snr=10.):
    """各周波数を分離し、maskを保つ。物理Jy/Stokes Iへの較正ではない。"""
    validate_spectral(data)
    if (isinstance(relative_scale, bool) or not np.isfinite(relative_scale) or relative_scale <= 0
            or isinstance(min_snr, bool) or not np.isfinite(min_snr) or min_snr < 5):
        raise ValueError('positive relative scale and baseline SNR >= 5 required')
    data = {k: np.asarray(data[k]) for k in ['visibilities', 'weights', 'pairs', 'times_s', 'frequencies_hz', 'uvw_lambda']}
    if any(np.iscomplexobj(data[k]) for k in ['times_s', 'frequencies_hz', 'uvw_lambda', 'weights']):
        raise ValueError('real spectral axes and geometry required')
    values = data['visibilities']; weights = data['weights']
    keep = (weights > 0) & (np.abs(values)*np.sqrt(weights) >= min_snr) & (np.abs(values) > 0)
    channels = []
    for f, frequency in enumerate(data['frequencies_hz']):
        t, b = np.nonzero(keep[:, f, :])
        channels.append({'frequency_hz': float(frequency), 'time_index': t, 'baseline_index': b,
            'time_hours': data['times_s'][t]/3600., 'pairs': data['pairs'][b].copy(),
            'uv_eht': -data['uvw_lambda'][t, f, b, :2],
            'vis_relative': relative_scale*values[t, f, b],
            'sigma_relative_per_quadrature': relative_scale/np.sqrt(weights[t, f, b])})
    return channels



def structured_time_groups(groups, dtype):
    """等長のstructured arrayをobject化してtupleになった行のdtypeだけを復元。"""
    dtype = np.dtype(dtype)
    if not dtype.names:
        raise ValueError('structured visibility dtype required')
    result = np.empty(len(groups), dtype=object)
    for i, group in enumerate(groups):
        result[i] = np.array(list(group), dtype=dtype)
    return result


def fixed_inputs():
    pairs = np.array(list(combinations(range(4), 2)), dtype=int)
    positions = np.array([[0., 0., 0.], [300., 0., 0.], [40., 190., 25.], [-100., 220., -20.]])
    positions *= 600/np.max(np.linalg.norm(positions[:, None]-positions[None, :], axis=-1))
    baseline = positions[pairs[:, 1]]-positions[pairs[:, 0]]
    frequencies = np.array([1.419744e9, 1.42e9, 1.420256e9]); times = np.array([.15, 300.15])
    geometries = []
    for angle in [0., .15]:
        rotation = np.array([[np.cos(angle), -np.sin(angle), 0.], [np.sin(angle), np.cos(angle), 0.], [0., 0., 1.]])
        geometries.append(baseline @ rotation.T)
    uvw = np.asarray(geometries)[:, None]*frequencies[None, :, None, None]/C_M_S
    uvw[..., 2] = 0.  # 外部2D direct DFTと同じモデルを作るための明示した対照。
    return pairs, positions, frequencies, times, uvw


def test_images(n):
    c = n//2; rows = []
    for name, points in [('center', [(c, c, 1.)]), ('east', [(c, c+1, 1.)]),
                         ('north', [(c+1, c, 1.)]), ('double', [(c-1, c+2, .7), (c+2, c-1, .3)])]:
        image = np.zeros((n, n))
        for y, x, value in points: image[y, x] = value
        rows.append((name, image))
    y, x = np.mgrid[:n, :n]; image = np.exp(-((x-c-1.)**2/3+(y-c+.4)**2/1.5)); image /= image.sum()
    return [*rows, ('asymmetric', image)]


def prepare(repository, output):
    root = Path(repository).resolve(); out = Path(output); out.mkdir(parents=True, exist_ok=False)
    pairs, positions, frequencies, times, uvw = fixed_inputs()
    arrays = {'pairs': pairs, 'positions_m': positions, 'frequencies_hz': frequencies, 'times_s': times, 'uvw': uvw}
    cases = []
    for n in [8, 9, 16, 32]:
        pixel = 512./n
        for name, image in test_images(n):
            key = f'n{n}_{name}'; expected = direct_visibility(uvw, image, pixel)
            # 公開DFTと別の画素ごとの解析和を照合し、adapter自身を期待値にしない。
            independent = np.zeros(uvw.shape[:-1], complex)
            for y, x in np.argwhere(image > 0):
                l = (int(x)-n//2)*pixel*np.pi/(180*3600)
                m = (int(y)-n//2)*pixel*np.pi/(180*3600)
                independent += image[y, x]*np.exp(-2j*np.pi*(uvw[..., 0]*l+uvw[..., 1]*m))
            np.testing.assert_allclose(expected, independent, rtol=2e-12, atol=2e-13)
            arrays[key+'_image'] = image; arrays[key+'_expected'] = expected
            cases.append({'key': key, 'pixels': n, 'pixel_arcsec': pixel, 'source': name,
                          'native_independent_max_abs_difference': float(np.max(np.abs(expected-independent)))})
    image = dict(test_images(8))['double']; values = direct_visibility(uvw, image, 64.)
    sigma = np.broadcast_to(np.linspace(.0008, .0013, len(pairs)), values.shape).copy()
    gains = np.array([[.7, .9, 1.3, 1.6], [1.4, .8, 1.1, .6]])*np.exp(1j*np.array([[.2, -1.1, .8, -.4], [-.5, .7, -1.4, .3]]))
    products = gains[:, pairs[:, 0]]*gains[:, pairs[:, 1]].conj()
    arrays.update(closure_values=values, closure_sigma=sigma,
        closure_gained_values=values*products[:, None], closure_gained_sigma=sigma*np.abs(products[:, None]))
    # 2D化した新観測を作らず、現存入力の幾何からw項モデル差だけを評価する。
    reference = json.loads((root/'validation/runs/stage119/reference.json').read_text()); w_records = []
    input_hashes = {}
    for row in reference['cases']:
        path = root/row['spectrum']; digest = hashlib.sha256(path.read_bytes()).hexdigest(); assert digest == row['input_sha256']
        input_hashes[row['spectrum']] = digest; d = load_spectral(path); n = row['pixels']; pixel = row['pixel_arcsec']
        bound = w_phase_bound(d['uvw_lambda'], n, pixel); zero_w = d['uvw_lambda'].copy(); zero_w[..., 2] = 0.
        cfg = deepcopy(d['metadata']['config']); cfg['image'].update(pixels=n, pixel_arcsec=pixel)
        cfg['source'].update(model='casa', total_flux_jy=1.)
        l, m = tangent_grid(n, pixel); prior = np.exp(-4*np.log(2)*(l*l+m*m)/(240*ARCSEC_RAD)**2); prior /= prior.sum()
        corner = np.zeros((n, n)); corner[0, 0] = 1.
        for name, candidate in [('known_casa_shape', synthetic_sky(cfg)), ('gaussian_prior', prior), ('field_corner', corner)]:
            full = direct_visibility(d['uvw_lambda'], candidate, pixel); planar = direct_visibility(zero_w, candidate, pixel)
            difference = float(np.max(np.abs(full-planar)))
            assert difference <= bound['normalized_visibility_absolute_bound']+2e-10
            w_records.append({'branch': row['branch'], 'pixels': n, 'pixel_arcsec': pixel, 'candidate': name,
                'maximum_normalized_model_visibility_difference': difference, **bound})
    np.savez_compressed(out/'reference.npz', **arrays)
    result = {'stage': 122, 'state': 'complete', 'dft_cases': cases, 'dft_frequency_comparisons': len(cases)*len(frequencies),
        'fixed_geometry': 'two manually rotated consistent 600m station arrays; explicit w=0 control, no new astrometric validation',
        'closure_labels': ['original', 'station_gain_transformed'], 'frequency_groups': 3, 'time_groups_each': 2,
        'quadrature_sigma_definition': 'std of each real/imag component; complex variance is twice its square',
        'w_comparisons': w_records, 'reused_input_sha256': input_hashes,
        'reference_bundle_sha256': hashlib.sha256((out/'reference.npz').read_bytes()).hexdigest(),
        'physical_jy_or_stokes_calibration_performed': False, 'image_optimizer_run': False, 'actual_observation_validated': False}
    (out/'summary.json').write_text(json.dumps(result, indent=2)+'\n'); return result


def reference_observation_class():
    """外部sourceを変えず、検証済みequal-time dtype接続を再利用する。"""
    import ehtim as eh
    class GroupedReferenceObservation(eh.obsdata.Obsdata):
        # 外部原本は変更しない。試験したequal-timeのみ扱い、scan平均は拒否する。
        def tlist(self, conj=False, t_gather=0., scan_gather=False):
            if t_gather != 0 or scan_gather:
                raise ValueError('only equal-time grouping validated by this reference adapter')
            return structured_time_groups(super().tlist(conj=conj), self.data.dtype)

        def copy(self):
            return deepcopy(self)

    return GroupedReferenceObservation


def external(reference, output):
    # optional外部依存は専用環境でだけimportする。productionへの依存追加はしない。
    import ehtim as eh
    import ehtim.const_def as constants
    from ehtim.observing.pulses import deltaPulse2D
    import importlib.metadata
    import sysconfig
    import sys
    GroupedReferenceObservation = reference_observation_class()

    prefix = Path(sysconfig.get_path('purelib')).resolve()
    assert Path(eh.__file__).resolve().is_relative_to(prefix)
    reference = Path(reference); out = Path(output); out.mkdir(parents=True, exist_ok=False)
    study = json.loads((reference/'summary.json').read_text())
    bundle = reference/'reference.npz'; assert hashlib.sha256(bundle.read_bytes()).hexdigest() == study['reference_bundle_sha256']
    with np.load(bundle, allow_pickle=False) as f: arrays = {k: f[k] for k in f.files}
    uvw = arrays['uvw']; dft = []
    for row in study['dft_cases']:
        image, uv, correction = image_transfer(arrays[row['key']+'_image'], uvw, row['pixel_arcsec'])
        external_image = eh.image.Image(image, row['pixel_arcsec']*ARCSEC_RAD, 1., 60., rf=1.42e9, pulse=deltaPulse2D)
        sampled = external_image.sample_uv(uv.reshape(-1, 2), ttype='direct', verbose=False)[0].reshape(uvw.shape[:-1])
        corrected = sampled*correction; expected = arrays[row['key']+'_expected']
        np.testing.assert_allclose(corrected, expected, rtol=2e-12, atol=2e-13)
        dft.append({'key': row['key'], 'maximum_abs_difference': float(np.max(np.abs(corrected-expected))),
            'uncorrected_half_pixel_difference': float(np.max(np.abs(sampled-expected)))})
    pairs = arrays['pairs']; tarr = np.zeros(4, dtype=constants.DTARR)
    tarr['site'] = [f'S{i:02d}' for i in range(4)]
    # 合成ECEF配置。ここではdatatableのuvを使い、外部で幾何を再生成しない。
    tarr['x'] = 6378137.+arrays['positions_m'][:, 2]; tarr['y'] = arrays['positions_m'][:, 0]; tarr['z'] = arrays['positions_m'][:, 1]
    tarr['sefdr'] = 1.; tarr['sefdl'] = 1.
    closures = []; original = None; unmodified_failure = False; ragged_identity = False
    for label, key in [('original', 'closure_'), ('station_gain_transformed', 'closure_gained_')]:
        values = arrays[key+'values']; sigma = arrays[key+'sigma']; data = {'visibilities': values, 'weights': 1/sigma**2,
            'pairs': pairs, 'times_s': arrays['times_s'], 'frequencies_hz': arrays['frequencies_hz'], 'uvw_lambda': uvw}
        core = form_closures(values, 1/sigma**2, pairs, min_snr=10.)
        label_values = []
        for f, channel in enumerate(spectral_channels(data)):
            table = np.zeros(len(channel['vis_relative']), dtype=constants.DTPOL_STOKES)
            table['time'] = channel['time_hours']; table['tint'] = .3
            table['t1'] = [f'S{i:02d}' for i in channel['pairs'][:, 0]]; table['t2'] = [f'S{i:02d}' for i in channel['pairs'][:, 1]]
            table['u'], table['v'] = channel['uv_eht'].T; table['vis'] = channel['vis_relative']
            for name in ['sigma', 'qsigma', 'usigma', 'vsigma']: table[name] = channel['sigma_relative_per_quadrature']
            obs = GroupedReferenceObservation(1., 60., channel['frequency_hz'], 256000., table, tarr.copy(), source='synthetic scalar reference', mjd=61309, ampcal=False, phasecal=False)
            if label == 'original' and f == 0:
                args, kwargs = obs.obsdata_args(); unmodified = eh.obsdata.Obsdata(*args, **kwargs)
                try:
                    unmodified.c_phases(count='max', ang_unit='rad', snrcut=0.)
                except TypeError as failure:
                    assert 'tuple indices' in str(failure); unmodified_failure = True
                else:
                    raise AssertionError('recorded upstream failure was not reproduced in this fixed environment')
                # 異なる長さの対照だけで、原本が保持するstructured rowsともbyte照合。
                ragged_args = list(args); ragged_args[4] = table[:-1].copy()
                ragged = eh.obsdata.Obsdata(*ragged_args, **kwargs)
                native_groups = ragged.tlist(conj=True)
                restored = structured_time_groups(native_groups, ragged.data.dtype)
                assert all(a.dtype == b.dtype and a.tobytes() == b.tobytes() for a, b in zip(native_groups, restored, strict=True))
                ragged_identity = True
            for conjugate in [False, True]:
                base = obs.data_conj() if conjugate else obs.data
                groups = obs.tlist(conj=conjugate)
                assert len(groups) == 2
                for group in groups:
                    expected_rows = base[base['time'] == group['time'][0]]
                    assert group.dtype == base.dtype and group.tobytes() == expected_rows.tobytes()
            assert obs.copy().data.tobytes() == obs.data.tobytes()
            try:
                obs.tlist(t_gather=1.)
            except ValueError:
                pass
            else:
                raise AssertionError('unvalidated grouping must be rejected')
            cp = obs.c_phases(count='max', ang_unit='rad', snrcut=0.)
            ca = obs.c_amplitudes(count='max', ctype='logcamp', debias=False, snrcut=0.)
            checks = []; errors = []; cvalues = []
            for kind, rows in [('phase', cp), ('logamp', ca)]:
                for row in rows:
                    t = int(np.argmin(abs(arrays['times_s']/3600.-row['time'])))
                    stations = [int(row[name][1:]) for name in (['t1', 't2', 't3'] if kind == 'phase' else ['t1', 't2', 't3', 't4'])]
                    a, b, c = stations[:3]
                    terms = [(a, b, 1), (b, c, 1), (c, a, 1)] if kind == 'phase' else [(a, b, 1), (c, stations[3], 1), (a, stations[3], -1), (b, c, -1)]
                    matrix = np.zeros(len(pairs))
                    for i, j, sign in terms:
                        edge = int(np.flatnonzero(np.all(pairs == sorted([i, j]), axis=1))[0])
                        matrix[edge] += sign*(1 if kind == 'logamp' or i < j else -1)
                    base = np.angle(values[t, f]) if kind == 'phase' else np.log(np.abs(values[t, f]))
                    expected = float(matrix @ base); measured = float(row['cphase' if kind == 'phase' else 'camp'])
                    diff = float(abs(wrap_phase(measured-expected))) if kind == 'phase' else abs(measured-expected)
                    error = float(np.sqrt(matrix**2 @ core['baseline_variance'][t, f])); measured_error = float(row['sigmacp' if kind == 'phase' else 'sigmaca'])
                    assert diff < 3e-12; np.testing.assert_allclose(measured_error, error, rtol=2e-12, atol=2e-14)
                    # 同じrowをnativeの全基底へ写して、その実API値とも照合する。
                    design = core[kind+'_matrix']
                    if kind == 'phase':
                        same = np.flatnonzero(np.all(design == matrix, axis=1)); opposite = np.flatnonzero(np.all(design == -matrix, axis=1))
                        assert len(same)+len(opposite) == 1
                        native = float(core[kind][t, f, same[0]]) if len(same) else -float(core[kind][t, f, opposite[0]])
                    else:
                        coefficients = np.linalg.lstsq(design.T, matrix, rcond=None)[0]
                        native = float(coefficients @ core[kind][t, f])
                    native_diff = abs(wrap_phase(measured-native)) if kind == 'phase' else abs(measured-native)
                    assert native_diff < 3e-12
                    checks.append(max(diff, float(native_diff))); errors.append(abs(measured_error-error)); cvalues.append([kind, t, stations, measured, measured_error])
            assert len(cp) == 8 and len(ca) == 6
            closures.append({'label': label, 'frequency_hz': obs.rf, 'rows': len(obs.data), 'phase_rows': len(cp), 'logamp_rows': len(ca),
                'maximum_value_difference': max(checks), 'maximum_sigma_difference': max(errors), 'values': cvalues})
            label_values.append(cvalues)
        if original is None: original = label_values
        else:
            for first, second in zip(original, label_values, strict=True):
                for a, b in zip(first, second, strict=True):
                    assert a[:3] == b[:3]; np.testing.assert_allclose(a[3:], b[3:], rtol=3e-11, atol=3e-12)
    result = {'stage': 122, 'state': 'complete', 'external_version': importlib.metadata.version('ehtim'),
        'dft_cases': dft, 'frequency_groups': 3, 'closure_cases': closures, 'station_gain_invariance': True,
        'all_ehtim_modules_in_external_prefix': True, 'existing_core_modules_in_external_prefix': True,
        'reference_bundle_sha256': study['reference_bundle_sha256'], 'physical_jy_or_stokes_calibration_performed': False,
        'scalar_visibility_in_I_slot_for_mathematical_reference_only': True,
        'marginal_high_snr_sigma_compared_only_not_full_closure_covariance': True,
        'external_source_files_patched': False, 'explicit_equal_time_dtype_adapter_used': True,
        'all_grouped_and_copied_values_order_dtype_bytes_preserved': True,
        'unmodified_uniform_time_api_failure_reproduced': unmodified_failure,
        'unmodified_ragged_group_control_bytes_identical': ragged_identity,
        'image_optimizer_run': False, 'actual_observation_validated': False}
    for name in ['vsora_simulator', 'vsora_imaging', 'vsora_formats', 'vsora_observation']:
        module = __import__(name); assert Path(module.__file__).resolve().is_relative_to(prefix)
    eht_modules = [m for name, m in sys.modules.items() if (name == 'ehtim' or name.startswith('ehtim.')) and getattr(m, '__file__', None)]
    assert all(Path(m.__file__).resolve().is_relative_to(prefix) for m in eht_modules)
    result['external_module_prefixes_checked'] = len(eht_modules)
    (out/'verification.json').write_text(json.dumps(result, indent=2)+'\n'); return result


def main():
    parser = argparse.ArgumentParser(description='外部RML比較前の固定Fourier/Closure対照')
    parser.add_argument('--mode', choices=('prepare', 'external'), required=True)
    parser.add_argument('--repository'); parser.add_argument('--reference'); parser.add_argument('--output', required=True)
    a = parser.parse_args()
    result = prepare(a.repository, a.output) if a.mode == 'prepare' else external(a.reference, a.output)
    print(json.dumps({'state': result['state'], 'mode': a.mode, 'stage': 122}))


if __name__ == '__main__': main()
