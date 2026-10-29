"""固定混合電圧の実codecから整列平均までを独立復号・有限係数へ照合。"""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import sys
import time
from unittest.mock import patch

import numpy as np
from astropy.time import Time
from vsora_correlator import aligned
from vsora_correlator.stream_fx import FXAccumulator
from vsora_formats.spectral import load_spectral
from vsora_formats.vdif import read_vdif, write_vdif


def helper(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


quantizer = helper('existing_scalar_quantizer', 'quantized_ensemble_validation.py')
reference = helper('existing_sample_reference', 'aligned_mean_validation.py')
FS, FFT, BLOCKS, COUNT, SUPPORT = 2048000., 8, 16, 4096, 512
START = 96/FS
LIGHT = 299792458.
UVW = np.array([[0., 0., 0.], [120., 35., 80.], [-90., 170., -60.]])
PAIRS = np.array([[0, 1], [0, 2], [1, 2]])
FRACTIONS = np.array([-89., 25., 108.])/512
SIGNS = np.array([[1., 1., 1.], [1., -1., -1.], [-1., 1., -1.], [-1., -1., 1.]])
WEIGHTS = np.array([.1, .3, .6])
RTOL, ATOL = 1e-9, 1e-10


def cross_power(spectrum):
    """probe, station, channel, blockから有限block平均を直接作る。"""
    return np.stack([(spectrum[:, i]*spectrum[:, j].conj()).mean(axis=-1)
                     for i, j in PAIRS], axis=-1)


def run(raw_reference, output):
    out = Path(output).resolve()
    if out.exists():
        raise FileExistsError('choose a new quantized aligned mean output')
    out.mkdir(parents=True); began = time.monotonic()
    base = Path(raw_reference).resolve()/'high_a/input'
    obs = deepcopy(json.loads((base/'observation.json').read_text()))
    obs['stations'] = obs['stations'][:3]; obs['observation']['integration_s'] = FFT*BLOCKS/FS
    (out/'observation.json').write_text(json.dumps(obs, indent=2)+'\n')
    original = json.loads((base/'manifest.json').read_text())
    stations = deepcopy(original['stations'][:3])
    clock = {'schema_version': 1, 'max_abs_baseband_hz': .3*FS,
             'stations': [{'id': row['id'], 'input_start_offset_s': 0., 'actual_sample_rate_hz': FS}
                          for row in stations]}
    (out/'clock.json').write_text(json.dumps(clock, indent=2)+'\n')
    rf = obs['observation']['frequency_hz']; delays = UVW[:, 2]/LIGHT
    baselines = UVW[PAIRS[:, 1]]-UVW[PAIRS[:, 0]]
    channels = rf+np.arange(-4, 4)*FS/FFT
    def geometry(config, times, filter_elevation=True):
        count = len(times)
        return {'station_delay_s': np.broadcast_to(delays, (count, 3)).copy(),
                'uvw_lambda': np.broadcast_to(baselines*rf/LIGHT, (count, 3, 3)).copy(),
                'pairs': PAIRS.copy(), 'elevation_valid': np.ones(count, bool), 'eop_status': []}
    l, m = np.array([2., -3.])*64*np.pi/(180*3600)
    direction = np.array([l, m, np.sqrt(1-l*l-m*m)-1]); extra = UVW @ direction/LIGHT
    frequencies = FRACTIONS*FS
    modes = np.exp(2j*np.pi*frequencies[:, None, None]*np.arange(COUNT)[None, None]/FS)
    modes = modes*np.exp(2j*np.pi*(rf+frequencies[:, None])*(delays+extra)[None])[:, :, None]
    raw = np.einsum('pm,m,msn->psn', SIGNS, np.sqrt(WEIGHTS), modes)
    np.testing.assert_array_equal(SIGNS.T @ SIGNS/4, np.eye(3))
    np.testing.assert_allclose(raw.mean(axis=0), 0., rtol=0., atol=1e-12)
    np.testing.assert_allclose(np.mean(abs(raw)**2, axis=0), 1., rtol=1e-12, atol=1e-12)
    times = START+np.arange(FFT*BLOCKS)/FS
    queries = (times[None]-delays[:, None])*FS
    _, _, taps = reference.clock_reference.finite_operator(1., 0.)
    sample = []; fourier = []
    for station in range(3):
        phase = np.full(FFT*BLOCKS, np.exp(-2j*np.pi*rf*delays[station]))
        a, b = reference.direct_operator(queries[station], phase, taps)
        sample.append(a); fourier.append(b)
    sample, fourier = np.array(sample), np.array(fourier)
    assert sample.shape == (3, FFT*BLOCKS, SUPPORT)
    before_fft = np.einsum('scbn,psn->pscb', fourier, raw[:, :, :SUPPORT])
    before_probe = cross_power(before_fft); before_mean = before_probe.mean(axis=0)
    arrays = {'sign_probes': SIGNS, 'mode_fractions_Fs': FRACTIONS, 'line_power_fractions': WEIGHTS,
              'station_uvw_m': UVW, 'direction_l_m_nminus1': direction, 'queries': queries,
              'prequantized_raw_first512': raw[:, :, :SUPPORT],
              'prequantized_probe_visibility': before_probe, 'prequantized_mean': before_mean}
    captured = []; captured_power = []
    class CaptureFX(FXAccumulator):
        def consume(self, data, valid):
            assert valid.all(); captured.append(data.copy())
            result = super().consume(data, valid)
            assert np.all(self.station_counts == BLOCKS)
            captured_power.append((self.power/self.station_counts)[np.argsort(self.frequency)].copy())
            return result
    records = []; fingerprints = {}
    for label, scale in [('scale1', 1.), ('scale0125', .125)]:
        decoded = np.empty_like(raw); clip = []; sidecars = []; summaries = []
        actual = []; voltage_error = visibility_error = power_error = 0.
        for probe in range(4):
            rows = deepcopy(stations)
            for station, row in enumerate(rows):
                filename = f'{label}-probe{probe}-station{station}.vdif'; path = out/filename
                sidecar = write_vdif(path, raw[probe, station], obs['observation']['start_utc'],
                    FS, row['station_numeric_id'], scale=scale, samples_per_frame=COUNT, voltage_unit='ADC')
                values, valid, header = read_vdif(path, FS, row['station_numeric_id'], scale=scale)
                independent = quantizer.independent_quantize(raw[probe, station], scale)
                np.testing.assert_array_equal(values, independent)
                assert valid.all() and values.shape == (COUNT,) and path.stat().st_size == 8224
                assert header['station_id'] == row['station_numeric_id']
                assert abs((Time(header['start_utc'])-Time(sidecar['start_utc'])).sec) < 1e-9
                assert sidecar['sample_count'] == COUNT and sidecar['decoded_voltage_scale'] == scale
                assert sidecar['decoded_voltage_unit'] == 'ADC' and sidecar['invalid_frame_count'] == 0
                fraction = float(np.mean((abs((raw[probe, station]/scale).real) > 127.5/35.5) |
                                         (abs((raw[probe, station]/scale).imag) > 127.5/35.5)))
                assert sidecar['clipped_fraction'] == fraction
                decoded[probe, station] = independent; clip.append(fraction); sidecars.append(sidecar)
                row['vdif'] = filename; row['decoded_voltage_scale'] = scale
                for file in [path, path.with_suffix('.json')]:
                    fingerprints[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
            manifest = {**original, 'observation_config': 'observation.json', 'fft_length': FFT,
                        'blocks_per_integration': BLOCKS, 'stations': rows}
            manifest.pop('spectral_quality', None)
            manifest_path = out/f'{label}-probe{probe}-manifest.json'
            manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
            predicted_voltage = np.einsum('stn,sn->st', sample, decoded[probe, :, :SUPPORT])
            z = np.einsum('scbn,sn->scb', fourier, decoded[probe, :, :SUPPORT])
            expected = cross_power(z[None])[0]
            captured.clear(); captured_power.clear(); destination = out/f'{label}-probe{probe}'
            # readerは置換しない。新VDIFの実header/payloadをSampleBufferが読む。
            with patch.object(aligned, 'geometry_at_times', geometry), patch.object(aligned, 'FXAccumulator', CaptureFX):
                summaries.append(aligned.correlate_aligned(manifest_path, out/'clock.json', destination,
                    1, start_offset_s=START, seek_input=False))
            assert len(captured) == 1
            np.testing.assert_allclose(captured[0], predicted_voltage, rtol=RTOL, atol=ATOL)
            data = load_spectral(destination/'shard-00000.npz')
            np.testing.assert_allclose(data['visibilities'][0], expected, rtol=RTOL, atol=ATOL)
            power = np.mean(abs(z)**2, axis=-1).T
            np.testing.assert_allclose(captured_power[0], power, rtol=RTOL, atol=ATOL)
            np.testing.assert_array_equal(data['frequencies_hz'], channels)
            assert np.all(data['valid_fft_count'] == BLOCKS) and data['metadata']['visibility_unit'] == 'ADC^2'
            voltage_error = max(voltage_error, float(abs(captured[0]-predicted_voltage).max()))
            visibility_error = max(visibility_error, float(abs(data['visibilities'][0]-expected).max()))
            power_error = max(power_error, float(abs(captured_power[0]-power).max()))
            actual.append(data['visibilities'][0])
        z = np.einsum('scbn,psn->pscb', fourier, decoded[:, :, :SUPPORT])
        direct_probe = cross_power(z); direct_mean = direct_probe.mean(axis=0)
        observed = np.mean(actual, axis=0)
        np.testing.assert_allclose(observed, direct_mean, rtol=RTOL, atol=ATOL)
        arrays.update({label+'_decoded_first512': decoded[:, :, :SUPPORT],
                       label+'_clip_fraction_by_probe_station': np.array(clip).reshape(4, 3),
                       label+'_actual_probe_visibility': np.array(actual), label+'_direct_probe_visibility': direct_probe,
                       label+'_actual_mean': observed, label+'_direct_mean': direct_mean})
        records.append({'scale_label': label, 'decoded_scale': scale, 'VDIF_files': 12,
            'VDIF_bytes': 12*8224, 'API_calls': 4, 'all_full_frame_decoded_equal': True,
            'clipped_fraction_by_probe_station': np.array(clip).reshape(4, 3).tolist(),
            'maximum_corrected_voltage_error': voltage_error, 'maximum_visibility_error': visibility_error,
            'maximum_station_power_error': power_error, 'maximum_mean_error': float(abs(observed-direct_mean).max()),
            'relative_mean_difference_from_prequantized': float(np.linalg.norm(direct_mean-before_mean)/np.linalg.norm(before_mean)),
            'all_sidecars': sidecars, 'API_summaries': summaries})
    result = {'stage': 162, 'state': 'complete', 'conditions': records, 'station_count': 3,
        'raw_samples_per_station': COUNT, 'operator_support_samples': SUPPORT, 'fft': FFT, 'blocks': BLOCKS,
        'span_s': FFT*BLOCKS/FS, 'finite_sign_probes': 4, 'simultaneous_modes': 3,
        'mode_fractions_Fs': FRACTIONS.tolist(), 'line_power_fractions': WEIGHTS.tolist(),
        'actual_API_calls': 8, 'VDIF_files_each_environment': 24, 'VDIF_bytes_each_environment': 24*8224,
        'new_VDIF_sidecar_sha256': fingerprints, 'RTOL': RTOL, 'ATOL': ATOL,
        'sample_operator_sha256': hashlib.sha256(sample.tobytes()).hexdigest(),
        'FFT_operator_sha256': hashlib.sha256(fourier.tobytes()).hexdigest(),
        'fixed_geometry_replacement': True, 'reader_replaced': False, 'actual_new_VDIF_header_payload_decoded': True,
        'codec_float32_intermediate_in_independent_reference': True, 'unknown_clock_rate_estimated': False,
        'upper_InputIdentity_executed': False, 'real131_raw_payload_reprocessed': False,
        'MC_trials': 0, 'seed_MCSE_applicable': False, 'proper_complex_Gaussian_IID_claimed': False,
        'nonlinear_quantized_mean_computed_from_decoded_waveforms_not_mode_power_sum': True,
        'product_code_changed': False, 'image_Closure_RML_fit_calls': 0,
        'scope': 'Same four deterministic three-mode mixtures, supplied ADC scale 1/.125 and fixed synthetic geometry. Actual new one-frame VDIF codec/header, manifest/clock validation, FIR/interpolation/RF/FX/save. Independent scalar quantization and full decoded-waveform coefficients. No hardware, continuous PSD, noise covariance, calibrated Jy, unknown station inference, observed selection, image likelihood or confidence calibration.'}
    (out/'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    np.savez_compressed(out/'arrays.npz', **arrays)
    modules = {n: m.__file__ for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None)}
    (out/'runtime-private.json').write_text(json.dumps({'module_paths': modules, 'wall_s': time.monotonic()-began,
        'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}, indent=2)+'\n')
    assert sum(f.stat().st_size for f in out.rglob('*') if f.is_file()) < 64*1024**2
    print(json.dumps(result)); return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-reference', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); run(args.raw_reference, args.output)
