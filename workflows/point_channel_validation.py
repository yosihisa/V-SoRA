"""供給点形状の空間位相と実整列/有限FFT応答を照合する。"""
import argparse
from copy import deepcopy
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
from vsora_imaging.rml import ClosureObjective
from vsora_simulator.visibility import direct_visibility

FS, FFT, BLOCKS, LENGTH = 2048000., 8, 16, 512
START = 96/FS
LIGHT = 299792458.
STATION_UVW = np.array([[0., 0., 0.], [120., 35., 80.], [-90., 170., -60.]])
PAIRS = np.array([[0, 1], [0, 2], [1, 2]])
RTOL, ATOL = 1e-9, 1e-10


def tone_response(frequency, delays):
    """146の独立I0/sinc係数式を定常tone応答へ展開する。"""
    m = np.arange(-32, 33)
    taps = .7*np.sinc(.7*m)*np.i0(8.6*np.sqrt(1-(m/32)**2))/np.i0(8.6)
    taps /= taps.sum()
    omega = 2*np.pi*frequency/FS
    fir = np.sum(taps*np.exp(-1j*omega*np.arange(65)))
    response = []
    for delay in delays:
        position = (START-delay)*FS+32
        index = np.floor(position).astype(int)+m
        distance = position-index
        weights = np.sinc(distance)*np.where(abs(distance) <= 32, (1+np.cos(np.pi*distance/32))/2, 0.)
        weights /= weights.sum()
        response.append(fir*np.exp(1j*omega*32)*np.sum(weights*np.exp(1j*omega*(index-position))))
    return np.array(response)


def run(raw_reference, output):
    out = Path(output)
    if out.exists():
        raise FileExistsError('choose a new point-channel output')
    out.mkdir(parents=True); began = time.monotonic()
    base = Path(raw_reference).resolve()/'high_a/input'
    obs = deepcopy(json.loads((base/'observation.json').read_text()))
    obs['stations'] = obs['stations'][:3]
    obs['observation']['integration_s'] = FFT*BLOCKS/FS
    (out/'observation.json').write_text(json.dumps(obs, indent=2)+'\n')
    original = json.loads((base/'manifest.json').read_text())
    stations = deepcopy(original['stations'][:3])
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
    rf = obs['observation']['frequency_hz']
    delays = STATION_UVW[:, 2]/LIGHT
    baselines = STATION_UVW[PAIRS[:, 1]]-STATION_UVW[PAIRS[:, 0]]
    channel_offsets = np.arange(-4, 4)*FS/FFT
    frequencies = rf+channel_offsets
    def geometry(config, times, filter_elevation=True):
        count = len(times)
        return {'station_delay_s': np.broadcast_to(delays, (count, 3)).copy(),
                'uvw_lambda': np.broadcast_to(baselines*rf/LIGHT, (count, 3, 3)).copy(),
                'pairs': PAIRS.copy(), 'elevation_valid': np.ones(count, bool), 'eop_status': []}
    t = START+np.arange(FFT*BLOCKS)/FS
    captured = []
    class CaptureFX(FXAccumulator):
        def consume(self, data, valid):
            assert valid.all(); captured.append(data.copy())
            return super().consume(data, valid)
    records = []; arrays = {'station_uvw_m': STATION_UVW, 'channel_frequencies_hz': frequencies}
    for label, row, column in [('center', 4, 4), ('off_axis', 1, 6)]:
        image = np.zeros((8, 8)); image[row, column] = 1.
        l, m = np.array([column-4, row-4])*64*np.pi/(180*3600)
        direction = np.array([l, m, np.sqrt(1-l*l-m*m)-1])
        extra = STATION_UVW @ direction/LIGHT
        spatial_channel = np.exp(-2j*np.pi*frequencies[:, None]*(baselines @ direction)[None, :]/LIGHT)
        for fraction in (0., .125, .15625):
            f = fraction*FS; frequency = rf+f
            raw = np.exp(2j*np.pi*f*np.arange(LENGTH)[None, :]/FS)*np.exp(2j*np.pi*frequency*(delays+extra))[:, None]
            def frames(path, nominal_rate, station_id, scale, *, start_sample=0):
                assert start_sample == 0 and nominal_rate == FS and scale == 1.
                values = raw[numeric[station_id]]
                for first in range(0, LENGTH, 64):
                    yield {'sample_index': first, 'data': values[first:first+64], 'valid': np.ones(64, bool)}
            name = label+'_f'+str(fraction); destination = out/name
            captured.clear()
            with patch.object(aligned, 'iter_vdif_frames', frames), patch.object(aligned, 'geometry_at_times', geometry), patch.object(aligned, 'FXAccumulator', CaptureFX):
                summary = aligned.correlate_aligned(out/'manifest.json', out/'clock.json', destination,
                                                    1, start_offset_s=START, seek_input=False)
            assert len(captured) == 1
            response = tone_response(f, delays)
            expected_voltage = response[:, None]*np.exp(2j*np.pi*f*t)[None, :]*np.exp(2j*np.pi*frequency*extra)[:, None]
            np.testing.assert_allclose(captured[0], expected_voltage, rtol=RTOL, atol=ATOL)
            # 周波数binの番号で表した独立な有限DFT和。FFT自体は呼ばない。
            power = abs(np.exp(2j*np.pi*(fraction-np.arange(-4, 4)[:, None]/FFT)*np.arange(FFT)).sum(axis=1)/np.sqrt(FFT))**2
            np.testing.assert_allclose(power.sum(), FFT, rtol=1e-12, atol=1e-12)
            if fraction in (0., .125):
                np.testing.assert_allclose(power.max(), FFT, rtol=1e-12, atol=1e-12)
            pair_response = response[PAIRS[:, 0]]*response[PAIRS[:, 1]].conj()
            spatial_tone = np.exp(-2j*np.pi*frequency*(baselines @ direction)/LIGHT)
            expected = power[:, None]*pair_response[None, :]*spatial_tone[None, :]
            data = load_spectral(destination/'shard-00000.npz')
            np.testing.assert_array_equal(data['frequencies_hz'], frequencies)
            np.testing.assert_allclose(data['visibilities'][0], expected, rtol=RTOL, atol=ATOL)
            assert np.all(data['valid_fft_count'] == BLOCKS)
            assert data['metadata']['visibility_unit'] == 'ADC^2'
            normalized_point = direct_visibility(data['uvw_lambda'], image, 64.)[0]
            np.testing.assert_allclose(normalized_point, spatial_channel, rtol=1e-11, atol=1e-12)
            objective = ClosureObjective(data['uvw_lambda'], data['visibilities'], data['weights'], data['pairs'],
                                         pixels=8, pixel_arcsec=64., min_snr=10., entropy=0., tsv=0., centroid=0.)
            matrix_point = (objective.fourier @ image.ravel()).reshape(-1, 3)
            np.testing.assert_allclose(matrix_point, spatial_channel, rtol=1e-11, atol=1e-12)
            center_frequency_model = power[:, None]*pair_response[None, :]*spatial_channel
            k = 5  # +Fs/8。off-bin入力ではこのbin中心とtoneの空間位相が異なる。
            center_error = float(np.linalg.norm(center_frequency_model[k]-expected[k])/max(np.linalg.norm(expected[k]), 1e-15))
            if label == 'off_axis' and fraction == .15625:
                assert center_error > 1e-6
            arrays.update({name+'_response': response, name+'_finite_DFT_power': power,
                           name+'_actual_visibility': data['visibilities'][0], name+'_expected_visibility': expected,
                           name+'_channel_center_point_phase': spatial_channel, name+'_tone_point_phase': spatial_tone})
            records.append({'point': label, 'point_row_column': [row, column], 'baseband_fraction_Fs': fraction,
                'maximum_corrected_voltage_error': float(abs(captured[0]-expected_voltage).max()),
                'maximum_visibility_error': float(abs(data['visibilities'][0]-expected).max()),
                'maximum_RML_point_matrix_error': float(abs(matrix_point-spatial_channel).max()),
                'finite_DFT_power_sum': float(power.sum()),
                'channel_plus1_center_frequency_spatial_error': center_error,
                'RML_constructor_closure_count_not_evaluated_as_loss': objective.count, 'API_summary': summary})
    result = {'stage': 159, 'state': 'complete', 'conditions': records, 'actual_API_calls': 6,
              'raw_samples_per_station': LENGTH, 'fft': FFT, 'blocks': BLOCKS, 'station_count': 3,
              'span_s': FFT*BLOCKS/FS, 'unit': 'ADC^2 for stored cross-power; unit-sum point shape is not Jy calibration',
              'geometry_replaced_by_fixed_consistent_UVW_and_delays': True,
              'reader_replaced_by_synthetic_decoded_frames': True, 'VDIF_payload_decoded': False,
              'MC_trials': 0, 'seed_MCSE_applicable': False, 'image_optimizer_calls': 0,
              'image_objective_or_gradient_evaluated': False, 'product_code_changed': False,
              'real_observation_or_finite_band_sky_likelihood_calibrated': False,
              'scope': 'Known unit point shapes and deterministic single tones. Real clock/manifest validation, FIR/interpolation/RF/FX/save with fixed synthetic geometry and decoded reader. Finite-channel leakage spatial phase follows the supplied tone frequency; not independent sky signals at each leaked channel center.'}
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
