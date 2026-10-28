"""供給clock傾きと実SampleBufferの全有限係数を照合する検証workflow。"""
import argparse
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
from vsora_simulator.filtered_noise import aligned_fft_kernel, filtered_visibility_moments
from vsora_simulator.visibility_moments import visibility_noise_moments


spec = importlib.util.spec_from_file_location('existing_periodic_reference',
                                            Path(__file__).with_name('periodic_fft_noise_validation.py'))
existing = importlib.util.module_from_spec(spec); spec.loader.exec_module(existing)
FFT, BLOCKS, LENGTH, FS = 8, 16, 512, 2048000.
OFFSETS = np.array([0., .25, .5])
CHANNELS = (3, 4, 5)
RTOL, ATOL = 1e-11, 1e-12


def finite_operator(ratio, offset):
    """実補間/FIRを呼ばず、I0 Kaiser・sinc・DFTの係数を直接合成する。"""
    m = np.arange(-32, 33)
    taps = (.7/ratio)*np.sinc((.7/ratio)*m)
    taps *= np.i0(8.6*np.sqrt(1-(m/32)**2))/np.i0(8.6)
    taps /= taps.sum()
    queries = (96+offset+np.arange(BLOCKS*FFT))*ratio
    compensated = queries+32
    indices = np.floor(compensated).astype(int)[:, None]+m
    distance = compensated[:, None]-indices
    weights = np.sinc(distance)*np.where(abs(distance) <= 32, (1+np.cos(np.pi*distance/32))/2, 0.)
    weights /= weights.sum(axis=1)[:, None]
    operator = np.zeros((BLOCKS*FFT, LENGTH))
    rows = np.broadcast_to(np.arange(BLOCKS*FFT)[:, None], indices.shape)
    for lag, tap in enumerate(taps):
        raw_indices = indices-lag
        assert raw_indices.min() >= 0 and raw_indices.max() < LENGTH
        np.add.at(operator, (rows.ravel(), raw_indices.ravel()), (weights*tap).ravel())
    channels = (np.arange(FFT)+FFT//2) % FFT
    fourier = np.exp(-2j*np.pi*channels[:, None]*np.arange(FFT)/FFT)/np.sqrt(FFT)
    h = np.einsum('cs,bsr->cbr', fourier, operator.reshape(BLOCKS, FFT, LENGTH))
    return h, queries, taps


def actual_buffer(raw, ratio, queries, chunk):
    """readerだけを合成decoded frameへ置換する。VDIF codecは検証しない。"""
    def frames(*args, start_sample=0):
        assert start_sample == 0
        for first in range(0, LENGTH, 64):
            yield {'sample_index': first, 'data': raw[first:first+64], 'valid': np.ones(64, bool)}
    with patch.object(aligned, 'iter_vdif_frames', frames):
        buffer = aligned.SampleBuffer('synthetic-decoded-only', FS, 1, 1., FS*ratio, seek_input=False)
        try:
            values = []; masks = []
            for first in range(0, len(queries), chunk):
                value, good = buffer.query(queries[first:first+chunk])
                values.append(value); masks.append(good)
            assert np.concatenate(masks).all()
            return np.concatenate(values), buffer.frames_read, buffer.taps.copy()
        finally:
            buffer.close()


def wick_moments(covariance):
    """既存142の二次形式traceとは別に、全block対を直接縮約する。"""
    pairs = np.array([(0, 1), (0, 2), (1, 2)])
    c = covariance.reshape(3, BLOCKS, 3, BLOCKS)
    mean = np.array([np.trace(c[i, :, j, :])/BLOCKS for i, j in pairs])
    gamma = np.empty((3, 3), complex); pseudo = gamma.copy()
    for b, (i, j) in enumerate(pairs):
        for d, (k, l) in enumerate(pairs):
            gamma[b, d] = np.sum(c[i, :, k, :]*c[l, :, j, :].T)/BLOCKS**2
            pseudo[b, d] = np.sum(c[i, :, l, :]*c[k, :, j, :].T)/BLOCKS**2
    real = .5*np.block([[np.real(gamma+pseudo), np.imag(pseudo-gamma)],
                       [np.imag(pseudo+gamma), np.real(gamma-pseudo)]])
    return {'mean': mean, 'complex_covariance': gamma, 'complex_pseudocovariance': pseudo,
            'real_covariance': .5*(real+real.T)}


def run(output):
    out = Path(output)
    if out.exists():
        raise FileExistsError('choose a new clock operator validation output')
    out.mkdir(parents=True); began = time.monotonic()
    assert existing.BLOCKS == BLOCKS
    station = np.eye(3)+.3*np.ones((3, 3)); factor = np.linalg.cholesky(station)
    arrays = {'input_station_covariance': station}; records = []; control_h = None; control_moments = {}
    for label, ppm in [('clock0', np.zeros(3)), ('clock_drift', np.array([-200., 0., 200.]))]:
        ratios = 1+ppm*1e-6
        constructed = [finite_operator(ratio, offset) for ratio, offset in zip(ratios, OFFSETS)]
        h = np.stack([v[0] for v in constructed]); queries = np.stack([v[1] for v in constructed])
        actual_h = np.empty_like(h); impulse_calls = 0; impulse_frames = 0; tap_error = 0.
        for station_index in range(3):
            for raw_index in range(LENGTH):
                raw = np.zeros(LENGTH, complex); raw[raw_index] = 1.
                y, frames, taps = actual_buffer(raw, ratios[station_index], queries[station_index], BLOCKS*FFT)
                actual_h[station_index, :, :, raw_index] = np.fft.fftshift(
                    np.fft.fft(y.reshape(BLOCKS, FFT), axis=1, norm='ortho'), axes=1).T
                np.testing.assert_allclose(taps, constructed[station_index][2], rtol=RTOL, atol=ATOL)
                tap_error = max(tap_error, float(np.max(abs(taps-constructed[station_index][2]))))
                impulse_calls += 1; impulse_frames += frames
        np.testing.assert_allclose(actual_h, h, rtol=RTOL, atol=ATOL)
        if label == 'clock0':
            control_h = h.copy()
            for i, offset in enumerate(OFFSETS):
                for channel in range(FFT):
                    kernel = aligned_fft_kernel(FFT, channel, float(offset))
                    expected = np.zeros((BLOCKS, LENGTH), complex)
                    for block in range(BLOCKS):
                        first = 32+block*FFT
                        expected[block, first:first+len(kernel)] = kernel
                    np.testing.assert_allclose(h[i, channel], expected, rtol=RTOL, atol=ATOL)
        direct_error = 0.; chunk_error = 0.; fx_error = 0.; fx_calls = 0
        for seed in (146, 147):
            rng = np.random.default_rng(seed)
            z = (rng.normal(size=(LENGTH, 3))+1j*rng.normal(size=(LENGTH, 3)))/np.sqrt(2)
            raw = (z @ factor.T).T
            whole = []; chunks = []
            for i in range(3):
                whole.append(actual_buffer(raw[i], ratios[i], queries[i], BLOCKS*FFT)[0])
                chunks.append(actual_buffer(raw[i], ratios[i], queries[i], 32)[0])
            whole, chunks = np.asarray(whole), np.asarray(chunks)
            np.testing.assert_allclose(chunks, whole, rtol=RTOL, atol=ATOL)
            spectrum = np.fft.fftshift(np.fft.fft(whole.reshape(3, BLOCKS, FFT), axis=-1, norm='ortho'), axes=-1)
            direct = np.einsum('icbr,ir->ibc', h, raw)
            np.testing.assert_allclose(spectrum, direct, rtol=RTOL, atol=ATOL)
            direct_error = max(direct_error, float(np.max(abs(spectrum-direct))))
            chunk_error = max(chunk_error, float(np.max(abs(chunks-whole))))
            for chunk in (BLOCKS*FFT, 32):
                accumulator = FXAccumulator(3, FS, FFT, 1.42e9)
                for first in range(0, BLOCKS*FFT, chunk):
                    accumulator.consume(whole[:, first:first+chunk])
                result = accumulator.finish(); fx_calls += 1
                expected = np.array([np.mean(spectrum[i]*spectrum[j].conj(), axis=0) for i, j in result['pairs']]).T
                np.testing.assert_allclose(result['vis_jy'][0], expected, rtol=RTOL, atol=ATOL)
                fx_error = max(fx_error, float(np.max(abs(result['vis_jy'][0]-expected))))
                np.testing.assert_array_equal(result['valid_fft_count'], np.full((1, 3), BLOCKS))
            arrays[f'{label}_seed{seed}_input_voltages'] = raw
            arrays[f'{label}_seed{seed}_actual_fft'] = spectrum
        channels = []
        for channel in CHANNELS:
            hc = h[:, channel]
            covariance = np.block([[station[i, j]*(hc[i] @ hc[j].conj().T) for j in range(3)] for i in range(3)])
            q = existing.quadratic_moments(covariance, stations=3); independent = wick_moments(covariance)
            for key, value in independent.items():
                np.testing.assert_allclose(q[key], value, rtol=RTOL, atol=ATOL)
            average = np.array([[np.trace(covariance[i*BLOCKS:(i+1)*BLOCKS, j*BLOCKS:(j+1)*BLOCKS])/BLOCKS
                                 for j in range(3)] for i in range(3)])
            iid = visibility_noise_moments(average, BLOCKS, q['pairs'])
            ratio = np.diag(q['real_covariance'])/np.diag(iid['real_covariance'])
            if label == 'clock0':
                old = filtered_visibility_moments(station, np.stack([aligned_fft_kernel(FFT, channel, float(o)) for o in OFFSETS]), FFT, BLOCKS)
                for key in independent:
                    np.testing.assert_allclose(old[key], q[key], rtol=RTOL, atol=ATOL)
                control_moments[channel] = q
            relative = float(np.max(abs(q['real_covariance']-control_moments[channel]['real_covariance']))/
                             np.max(abs(control_moments[channel]['real_covariance'])))
            for key in independent:
                arrays[f'{label}_channel{channel}_{key}'] = q[key]
            arrays[f'{label}_channel{channel}_station_time_covariance'] = covariance
            arrays[f'{label}_channel{channel}_nominal_iid_real_covariance'] = iid['real_covariance']
            channels.append({'channel': channel, 'known_model_variance_to_nominal_iid_range': [float(ratio.min()), float(ratio.max())],
                             'normalized_covariance_difference_from_clock0': relative,
                             'trace_and_direct_block_pair_contractions_match': True})
        arrays[f'{label}_all_channel_direct_operator'] = h
        arrays[f'{label}_all_channel_actual_basis_operator'] = actual_h
        arrays[f'{label}_queries_before_group_delay_compensation'] = queries
        arrays[f'{label}_direct_fir_taps'] = np.stack([v[2] for v in constructed])
        record = {'label': label, 'station_clock_ppm': ppm.tolist(), 'actual_sample_rates_hz': (ratios*FS).tolist(),
                  'impulse_buffer_calls': impulse_calls, 'synthetic_decoded_frames_for_impulses': impulse_frames,
                  'maximum_basis_coefficient_error': float(np.max(abs(h-actual_h))), 'maximum_fir_tap_error': tap_error,
                  'maximum_seed_voltage_operator_error': direct_error, 'maximum_chunk_value_error': chunk_error,
                  'actual_fx_finish_calls': fx_calls, 'maximum_fx_visibility_error': fx_error,
                  'relative_operator_difference_from_clock0': float(np.linalg.norm(h-control_h)/np.linalg.norm(control_h)),
                  'channels': channels}
        records.append(record); print(json.dumps(record), flush=True)
    result = {'stage': 146, 'state': 'complete', 'cases': records, 'stations': 3, 'raw_samples': LENGTH,
              'fft_length': FFT, 'nominal_blocks': BLOCKS, 'fixed_offsets_samples': OFFSETS.tolist(),
              'fixed_input_start_s': (-(96+OFFSETS)/FS).tolist(), 'nominal_sample_rate_hz': FS,
              'query_formula': '(96 + station_offset + output_sample_index) * actual_rate / nominal_rate; SampleBuffer adds 32',
              'reader_adapter': 'Synthetic decoded complex frames of 64 samples, all valid, no binary VDIF decoder; seek_input=False',
              'all_channel_actual_basis_matches_independent_operator': True, 'existing049_zero_slope_control_matches': True,
              'existing142_trace_helper_reused': True, 'monte_carlo_trials': 0, 'mcse_applicable': False,
              'fixed_random_seed_vectors_not_mc_calibration': [146, 147], 'seeds_and_clock_conditions_share_input_voltages': True,
              'physical_adc_vdif_codec_processed': False, 'geometry_rf_rate_phase_path_executed': False,
              'unknown_clock_estimation_performed': False, 'real131_raw_reprocessed': False,
              'effective_fft_count_or_coverage_calibrated': False, 'production_rml_changed': False,
              'scope': 'Known finite white proper Gaussian input and supplied clock slopes. Actual SampleBuffer FIR/state/guard/interpolation with synthetic decoded-frame reader, then actual FX. No quantization, flags, geometry/rate phase, same-pilot inference, observed selection, real hardware or image calibration.'}
    (out/'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    np.savez_compressed(out/'arrays.npz', **arrays)
    origins = {n: m.__file__ for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None)}
    (out/'runtime-private.json').write_text(json.dumps({'module_paths': origins, 'wall_s': time.monotonic()-began,
        'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}, indent=2)+'\n')
    assert sum(p.stat().st_size for p in out.iterdir()) < 16*1024**2
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    run(parser.parse_args().output)
