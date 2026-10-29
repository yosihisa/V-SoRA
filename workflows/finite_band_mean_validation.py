"""同時混合した3線スペクトルの有限probe平均を実整列APIへ照合。"""
import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import resource
import sys
import time
from unittest.mock import patch

import numpy as np
from vsora_correlator import aligned
from vsora_correlator.stream_fx import FXAccumulator
from vsora_formats.spectral import load_spectral
from vsora_simulator.visibility import direct_visibility

spec = importlib.util.spec_from_file_location('existing_point_reference', Path(__file__).with_name('point_channel_validation.py'))
ref = importlib.util.module_from_spec(spec); spec.loader.exec_module(ref)
FS, FFT, BLOCKS, LENGTH, START = ref.FS, ref.FFT, ref.BLOCKS, ref.LENGTH, ref.START
FRACTIONS = np.array([-89., 25., 108.])/512
SIGNS = np.array([[1., 1., 1.], [1., -1., -1.], [-1., 1., -1.], [-1., -1., 1.]])
RTOL, ATOL = 1e-9, 1e-10


def run(raw_reference, output):
    out = Path(output)
    if out.exists():
        raise FileExistsError('choose a new finite-band mean output')
    out.mkdir(parents=True); began = time.monotonic()
    np.testing.assert_array_equal(SIGNS.mean(axis=0), 0.)
    np.testing.assert_array_equal(SIGNS.T @ SIGNS/4, np.eye(3))
    # 実符号なので擬二次momentもI。proper complex/Gaussian標本とはしない。
    np.testing.assert_array_equal(SIGNS.T @ SIGNS.conj()/4, np.eye(3))
    base = Path(raw_reference).resolve()/'high_a/input'
    obs = deepcopy(json.loads((base/'observation.json').read_text()))
    obs['stations'] = obs['stations'][:3]; obs['observation']['integration_s'] = FFT*BLOCKS/FS
    (out/'observation.json').write_text(json.dumps(obs, indent=2)+'\n')
    original = json.loads((base/'manifest.json').read_text()); stations = deepcopy(original['stations'][:3])
    for row in stations:
        row['vdif'] = str(base/row['vdif']); row['decoded_voltage_scale'] = 1.
    manifest = {**original, 'observation_config': 'observation.json', 'fft_length': FFT,
                'blocks_per_integration': BLOCKS, 'stations': stations}
    manifest.pop('spectral_quality', None)
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (out/'clock.json').write_text(json.dumps({'schema_version': 1, 'max_abs_baseband_hz': .3*FS,
        'stations': [{'id': row['id'], 'input_start_offset_s': 0., 'actual_sample_rate_hz': FS}
                     for row in stations]}, indent=2)+'\n')
    numeric = {row['station_numeric_id']: i for i, row in enumerate(stations)}
    rf = obs['observation']['frequency_hz']; uvw = ref.STATION_UVW; pairs = ref.PAIRS
    delays = uvw[:, 2]/ref.LIGHT; baselines = uvw[pairs[:, 1]]-uvw[pairs[:, 0]]
    def geometry(config, times, filter_elevation=True):
        count = len(times)
        return {'station_delay_s': np.broadcast_to(delays, (count, 3)).copy(),
                'uvw_lambda': np.broadcast_to(baselines*rf/ref.LIGHT, (count, 3, 3)).copy(),
                'pairs': pairs.copy(), 'elevation_valid': np.ones(count, bool), 'eop_status': []}
    image = np.zeros((8, 8)); image[1, 6] = 1.
    l, m = np.array([2., -3.])*64*np.pi/(180*3600)
    direction = np.array([l, m, np.sqrt(1-l*l-m*m)-1]); extra = uvw @ direction/ref.LIGHT
    baseband = FRACTIONS*FS; frequencies = rf+baseband
    channels = rf+np.arange(-4, 4)*FS/FFT
    spatial = direct_visibility(baselines[None]*frequencies[:, None, None]/ref.LIGHT, image, 64.)
    point_sum = np.exp(-2j*np.pi*frequencies[:, None]*(baselines @ direction)[None]/ref.LIGHT)
    np.testing.assert_allclose(spatial, point_sum, rtol=1e-11, atol=1e-12)
    channel_point = direct_visibility(baselines[None]*channels[:, None, None]/ref.LIGHT, image, 64.)
    np.testing.assert_allclose(channel_point, np.exp(-2j*np.pi*channels[:, None]*(baselines @ direction)[None]/ref.LIGHT), rtol=1e-11, atol=1e-12)
    mode_raw = np.exp(2j*np.pi*baseband[:, None, None]*np.arange(LENGTH)[None, None]/FS)*np.exp(2j*np.pi*frequencies[:, None]*(delays+extra)[None])[:, :, None]
    response = np.array([ref.tone_response(f, delays) for f in baseband])
    t = START+np.arange(FFT*BLOCKS)/FS
    mode_voltage = response[:, :, None]*np.exp(2j*np.pi*frequencies[:, None]*extra[None])[:, :, None]*np.exp(2j*np.pi*baseband[:, None, None]*t[None, None])
    power = abs(np.exp(2j*np.pi*(FRACTIONS[None, :, None]-np.arange(-4, 4)[:, None, None]/FFT)*np.arange(FFT)).sum(axis=2)/np.sqrt(FFT))**2
    np.testing.assert_allclose(power.sum(axis=0), FFT, rtol=1e-12, atol=1e-12)
    dft = np.exp(-2j*np.pi*np.arange(-4, 4)[:, None]*np.arange(FFT)/FFT)/np.sqrt(FFT)
    pair_response = response[:, pairs[:, 0]]*response[:, pairs[:, 1]].conj()
    arrays = {'sign_probes': SIGNS, 'mode_fractions_Fs': FRACTIONS, 'point_image': image,
              'raw_modes': mode_raw, 'independent_corrected_modes': mode_voltage,
              'mode_response': response, 'finite_DFT_power': power, 'mode_point_phase': spatial,
              'channel_point_phase': channel_point}
    captured = []
    class CaptureFX(FXAccumulator):
        def consume(self, data, valid):
            assert valid.all(); captured.append(data.copy()); return super().consume(data, valid)
    records = []
    for label, weights in [('uniform', np.array([1., 1., 1.])/3), ('colored', np.array([.1, .3, .6]))]:
        np.testing.assert_allclose(weights.sum(), 1., rtol=0., atol=1e-15)
        raw = np.einsum('pm,m,msn->psn', SIGNS, np.sqrt(weights), mode_raw)
        voltage = np.einsum('pm,m,mst->pst', SIGNS, np.sqrt(weights), mode_voltage)
        np.testing.assert_allclose(raw.mean(axis=0), 0., rtol=0., atol=1e-12)
        np.testing.assert_allclose(np.mean(abs(raw)**2, axis=0), 1., rtol=1e-12, atol=1e-12)
        z = np.einsum('kn,psbn->psbk', dft, voltage.reshape(4, 3, BLOCKS, FFT))
        per_probe = np.stack([(z[:, i]*z[:, j].conj()).mean(axis=1) for i, j in pairs], axis=-1)
        expected = np.einsum('m,km,mb,mb->kb', weights, power, pair_response, spatial)
        np.testing.assert_allclose(per_probe.mean(axis=0), expected, rtol=RTOL, atol=ATOL)
        actual = []; summaries = []; maximum_voltage = maximum_per_probe = 0.
        for probe in range(4):
            def frames(path, nominal_rate, station_id, scale, *, start_sample=0):
                assert start_sample == 0 and nominal_rate == FS and scale == 1.
                values = raw[probe, numeric[station_id]]
                for first in range(0, LENGTH, 64):
                    yield {'sample_index': first, 'data': values[first:first+64], 'valid': np.ones(64, bool)}
            captured.clear(); destination = out/f'{label}-probe{probe}'
            with patch.object(aligned, 'iter_vdif_frames', frames), patch.object(aligned, 'geometry_at_times', geometry), patch.object(aligned, 'FXAccumulator', CaptureFX):
                summaries.append(aligned.correlate_aligned(out/'manifest.json', out/'clock.json', destination, 1, start_offset_s=START, seek_input=False))
            assert len(captured) == 1
            np.testing.assert_allclose(captured[0], voltage[probe], rtol=RTOL, atol=ATOL)
            data = load_spectral(destination/'shard-00000.npz')
            np.testing.assert_allclose(data['visibilities'][0], per_probe[probe], rtol=RTOL, atol=ATOL)
            np.testing.assert_array_equal(data['frequencies_hz'], channels)
            assert np.all(data['valid_fft_count'] == BLOCKS) and data['metadata']['visibility_unit'] == 'ADC^2'
            maximum_voltage = max(maximum_voltage, float(abs(captured[0]-voltage[probe]).max()))
            maximum_per_probe = max(maximum_per_probe, float(abs(data['visibilities'][0]-per_probe[probe]).max()))
            actual.append(data['visibilities'][0])
        observed = np.mean(actual, axis=0)
        np.testing.assert_allclose(observed, expected, rtol=RTOL, atol=ATOL)
        approximation = channel_point*np.einsum('m,km,mb->kb', weights, power, pair_response)
        difference = float(np.linalg.norm(approximation-expected)/np.linalg.norm(expected))
        assert difference > 1e-6
        single_probe_difference = [float(np.linalg.norm(x-expected)/np.linalg.norm(expected)) for x in actual]
        arrays.update({label+'_line_power_fractions': weights, label+'_actual_per_probe': np.array(actual),
                       label+'_direct_DFT_per_probe': per_probe, label+'_weighted_mode_mean': expected,
                       label+'_observed_mean': observed, label+'_channel_center_approximation': approximation})
        records.append({'line_power_case': label, 'line_power_fractions': weights.tolist(), 'actual_API_calls': 4,
            'maximum_voltage_error': maximum_voltage, 'maximum_per_probe_visibility_error': maximum_per_probe,
            'maximum_mean_error': float(abs(observed-expected).max()),
            'channel_center_spatial_phase_only_relative_mean_difference': difference,
            'single_probe_relative_distance_to_finite_mean': single_probe_difference,
            'API_summaries': summaries})
    result = {'stage': 161, 'state': 'complete', 'conditions': records, 'actual_API_calls': 8,
        'finite_sign_probes': 4, 'input_modes_per_probe': 3, 'raw_samples_per_station': LENGTH,
        'fft': FFT, 'blocks': BLOCKS, 'span_s': FFT*BLOCKS/FS,
        'mode_fractions_Fs': FRACTIONS.tolist(), 'MC_trials': 0, 'seed_MCSE_applicable': False,
        'ensemble_proper_complex_or_Gaussian': False, 'mode_pseudomoment': 'I, not zero',
        'power_weights_are_discrete_line_masses_not_continuous_PSD_per_Hz': True,
        'image_optimizer_calls': 0, 'new_Closure_or_RML_evaluation': False, 'product_code_changed': False,
        'scope': 'Fixed point and three spectral lines, four deterministic sign probes with simultaneous mode mixing. Real aligned FIR/interpolation/RF/FX/save under synthetic decoded reader and fixed geometry. Finite mean identity only; no continuous-band PSD integral, Gaussian noise covariance, IID/coverage, calibrated Jy, unknown station inference or actual observation success.'}
    (out/'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    np.savez_compressed(out/'arrays.npz', **arrays)
    modules = {n: m.__file__ for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None)}
    (out/'runtime-private.json').write_text(json.dumps({'module_paths': modules, 'wall_s': time.monotonic()-began,
        'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}, indent=2)+'\n')
    print(json.dumps(result)); return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-reference', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); run(args.raw_reference, args.output)
