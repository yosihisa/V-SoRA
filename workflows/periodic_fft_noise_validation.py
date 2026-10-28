"""有限周期の矩形bandlimitを、実補間FFTと既知Gaussian全雑音へ照合する。"""
import argparse
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
from scipy.signal import firwin, lfilter
from vsora_correlator.clock import interpolate_samples
from vsora_correlator.stream_fx import FXAccumulator
from vsora_simulator.filtered_noise import aligned_fft_kernel
from vsora_simulator.visibility_moments import visibility_noise_moments


FFT = 8
BLOCKS = 16
PERIOD = 512
REFERENCE131_PERIOD = 1520*4096
TRIALS = 4096
OFFSETS = (0., .25, .5, .75)
CHANNELS = (3, 4, 5)


def temporal_lags(period, length):
    """±Fs/4を含む矩形bin列のDirichlet和。Noneは無限周期極限。"""
    d = np.arange(length, dtype=float)
    if period is None:
        return np.sinc(d/2)
    bins = 2*(period//4)+1
    result = np.ones(length)
    different = np.remainder(d, period) != 0
    result[different] = np.sin(np.pi*bins*d[different]/period)/(bins*np.sin(np.pi*d[different]/period))
    return result


def finite_output_covariance(station, kernels, period):
    """既知入力Kと有限な各局operatorから全局/時刻のCを作る。"""
    n, width = kernels.shape; length = (BLOCKS-1)*FFT+width
    h = np.zeros((n, BLOCKS, length), complex)
    for i in range(n):
        for a in range(BLOCKS):
            h[i, a, a*FFT:a*FFT+width] = kernels[i]
    lags = temporal_lags(period, length)
    temporal = lags[abs(np.arange(length)[:, None]-np.arange(length)[None, :])]
    covariance = np.block([[station[i, j]*(h[i] @ temporal @ h[j].conj().T)
                            for j in range(n)] for i in range(n)])
    if period == PERIOD:
        frequencies = np.fft.fftfreq(period)
        active = abs(frequencies) <= .25
        transform_lags = (np.fft.ifft(active)*period/active.sum())[:length]
        np.testing.assert_allclose(transform_lags, lags, rtol=1e-11, atol=1e-11)
        # 時間領域Kとは別に、独立な周波数modeの作用を直接足す。
        response = np.fft.ifft(kernels, n=period, axis=-1)*period
        phase = np.exp(2j*np.pi*np.arange(BLOCKS)[:, None]*FFT*frequencies[active])
        modes = response[:, None, active]*phase[None]
        spectral = np.block([[station[i, j]*(modes[i] @ modes[j].conj().T)/active.sum()
                              for j in range(n)] for i in range(n)])
        np.testing.assert_allclose(spectral, covariance, rtol=1e-11, atol=1e-11)
    return covariance, lags


def quadratic_moments(covariance, stations=4):
    """既知proper Gaussian yのyᴴAyをtraceで計算する検証helper。"""
    pairs = np.array([(i, j) for i in range(stations) for j in range(i+1, stations)])
    a = np.zeros((len(pairs), len(covariance), len(covariance)), complex)
    for b, (i, j) in enumerate(pairs):
        for t in range(BLOCKS):
            a[b, j*BLOCKS+t, i*BLOCKS+t] = 1/BLOCKS
    ac = a @ covariance
    ahc = a.conj().transpose(0, 2, 1) @ covariance
    gamma = np.einsum('aij,bji->ab', ac, ahc)
    pseudo = np.einsum('aij,bji->ab', ac, ac)
    real = .5*np.block([[np.real(gamma+pseudo), np.imag(pseudo-gamma)],
                       [np.imag(pseudo+gamma), np.real(gamma-pseudo)]])
    return {'pairs': pairs, 'mean': np.trace(ac, axis1=1, axis2=2),
            'complex_covariance': gamma, 'complex_pseudocovariance': pseudo,
            'real_covariance': .5*(real+real.T)}


def run(output):
    out = Path(output)
    if out.exists():
        raise FileExistsError('choose a new periodic FFT validation output')
    began = time.monotonic(); out.mkdir(parents=True)
    mode = np.exp(1j*np.array([0., .4, 1.1, 2.2]))
    station = np.ones((4, 4))+.7*mode[:, None]*mode.conj()[None, :]+1.5*np.eye(4)
    kernels = np.array([[aligned_fft_kernel(FFT, c, offset) for offset in OFFSETS] for c in range(FFT)])
    arrays = {'all8_fft_station_kernels': kernels}; records = []; theoretical = {}
    for label, period in [('period512', PERIOD), ('period131', REFERENCE131_PERIOD), ('infinite', None)]:
        for channel in CHANNELS:
            covariance, lags = finite_output_covariance(station, kernels[channel], period)
            q = quadratic_moments(covariance)
            output_station = covariance[np.ix_(np.arange(4)*BLOCKS, np.arange(4)*BLOCKS)]
            iid = visibility_noise_moments(output_station, BLOCKS)
            np.testing.assert_allclose(q['mean'], iid['mean'], rtol=1e-11, atol=1e-11)
            assert np.linalg.eigvalsh(q['real_covariance']).min() >= -1e-11
            key = f'{label}_channel{channel}'
            for name in ['mean', 'complex_covariance', 'complex_pseudocovariance', 'real_covariance']:
                arrays[key+'_'+name] = q[name]
            arrays[key+'_iid_mean'] = iid['mean']; arrays[key+'_iid_real_covariance'] = iid['real_covariance']
            arrays[key+'_station_output_covariance'] = output_station
            arrays[label+'_input_temporal_lags'] = lags
            ratios = np.diag(q['real_covariance'])/np.diag(iid['real_covariance'])
            norm = np.sqrt(np.diag(q['real_covariance'])[:, None]*np.diag(q['real_covariance'])[None, :])
            records.append({'model': label, 'period_raw_samples': period, 'channel': channel,
                'known_variance_to_iid_range': [float(ratios.min()), float(ratios.max())],
                'maximum_normalized_exact_iid_difference': float(np.max(abs(q['real_covariance']-iid['real_covariance'])/norm)),
                'iid_is_counterfactual_only': True, 'nominal_blocks': BLOCKS,
                'dirichlet_fft_and_frequency_projection_checked': period == PERIOD,
                'mc_executed': period == PERIOD, 'mc_trials': TRIALS if period == PERIOD else 0,
                'real131_voltage_or_geometry_processed': False})
            theoretical[label, channel] = q
    rng = np.random.default_rng(142); factor = np.linalg.cholesky(station)
    active = abs(np.fft.fftfreq(PERIOD)) <= .25
    taps = firwin(65, .35, fs=1., window=('kaiser', 8.6))
    pairs = theoretical['period512', CHANNELS[0]]['pairs']
    sums = np.zeros((3, 12)); products = np.zeros((3, 12, 12)); squared = products.copy()
    direct_difference = fx_difference = 0.
    for first in range(0, TRIALS, 32):
        count = min(32, TRIALS-first)
        z = (rng.normal(size=(count, PERIOD, 4))+1j*rng.normal(size=(count, PERIOD, 4)))/np.sqrt(2)
        raw = (z @ factor.T).transpose(0, 2, 1)
        colored = np.fft.ifft(np.fft.fft(raw, axis=-1)*active/np.sqrt(active.mean()), axis=-1)
        filtered = lfilter(taps, [1], colored, axis=-1)
        y = np.empty((count, 4, BLOCKS*FFT), complex)
        for i, offset in enumerate(OFFSETS):
            positions = (np.arange(count)[:, None]*PERIOD+96+offset+np.arange(BLOCKS*FFT)).ravel()
            values, good = interpolate_samples(filtered[:, i].ravel(), positions)
            assert good.all(); y[:, i] = values.reshape(count, -1)
        spectrum = np.fft.fftshift(np.fft.fft(y.reshape(count, 4, BLOCKS, FFT), axis=-1, norm='ortho'), axes=-1)
        if first == 0:
            for trial in range(2):
                direct = np.array([[[kernels[c, s] @ colored[trial, s, block*FFT:block*FFT+kernels.shape[-1]]
                                     for block in range(BLOCKS)] for s in range(4)] for c in range(FFT)])
                actual = spectrum[trial].transpose(2, 0, 1)
                np.testing.assert_allclose(actual, direct, rtol=1e-11, atol=1e-11)
                direct_difference = max(direct_difference, float(np.max(abs(actual-direct))))
                accumulator = FXAccumulator(4, 1., FFT, 0.); accumulator.consume(y[trial])
                fx = accumulator.finish()['vis_jy'][0]
                manual = (spectrum[trial, pairs[:, 0]]*spectrum[trial, pairs[:, 1]].conj()).mean(axis=1).T
                np.testing.assert_allclose(fx, manual, rtol=1e-11, atol=1e-11)
                fx_difference = max(fx_difference, float(np.max(abs(fx-manual))))
        for row, channel in enumerate(CHANNELS):
            selected = spectrum[:, :, :, channel]
            visibility = (selected[:, pairs[:, 0]]*selected[:, pairs[:, 1]].conj()).mean(axis=-1)
            residual = visibility-theoretical['period512', channel]['mean']
            values = np.c_[residual.real, residual.imag]
            sums[row] += values.sum(axis=0); products[row] += values.T @ values
            squared[row] += (values**2).T @ (values**2)
    for row, channel in enumerate(CHANNELS):
        truth = theoretical['period512', channel]['real_covariance']
        measured = products[row]/TRIALS
        se = np.sqrt(np.maximum(0., (squared[row]-products[row]**2/TRIALS)/(TRIALS-1))/TRIALS)
        mean = sums[row]/TRIALS; mean_se = np.sqrt(np.diag(truth)/TRIALS)
        assert np.all(abs(measured-truth) <= 6*se+1e-11*np.max(np.diag(truth)))
        assert np.all(abs(mean) <= 6*mean_se+1e-11*np.sqrt(np.max(np.diag(truth))))
        key = f'period512_channel{channel}'
        arrays[key+'_mc_real_covariance'] = measured; arrays[key+'_mc_covariance_se'] = se
        arrays[key+'_mc_centered_mean'] = mean; arrays[key+'_mc_mean_se'] = mean_se
        record = next(v for v in records if v['model'] == 'period512' and v['channel'] == channel)
        record.update(all_means_and_covariances_within_fixed_6mcse=True,
            maximum_mean_difference_in_mcse=float(np.max(abs(mean)/(mean_se+1e-30))),
            maximum_covariance_difference_in_mcse=float(np.max(abs(measured-truth)/(se+1e-30))))
    for record in records:
        q = theoretical[record['model'], record['channel']]['real_covariance']
        infinite = theoretical['infinite', record['channel']]['real_covariance']
        scale = np.sqrt(np.diag(infinite)[:, None]*np.diag(infinite)[None, :])
        record['maximum_covariance_difference_to_infinite_normalized'] = float(np.max(abs(q-infinite)/scale))
    result = {'stage': 142, 'state': 'complete', 'cases': records, 'seed': 142,
        'independent_base_trials': TRIALS, 'mc_model_count': 1, 'channels_shared_per_trial': 3,
        'analytic_only_models': ['period131', 'infinite'], 'first_two_trials_all8channel_kernel_max_abs_error': direct_difference,
        'first_two_trials_actual_fx_max_abs_error': fx_difference,
        'new_product_noise_api': False, 'production_rml_changed': False,
        'real131_period_processed_as_raw_voltage': False, 'physical_adc_vdif_processed': False,
        'effective_fft_count_measured': False, 'confidence_interval_calibrated': False,
        'scope': 'Known stationary periodic proper Gaussian, fixed FIR/offset/FFT. Large131 period and infinite limit are analytic-only small-operator conditional references; no geometry, LO fitting, ADC, masks, unknown receiver or image likelihood calibration.'}
    (out/'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    np.savez_compressed(out/'arrays.npz', **arrays)
    origins = {n: m.__file__ for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None)}
    (out/'runtime-private.json').write_text(json.dumps({'module_paths': origins, 'wall_s': time.monotonic()-began,
        'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}, indent=2)+'\n')
    assert sum(p.stat().st_size for p in out.iterdir()) < 16*1024**2
    print(json.dumps({'state': 'complete', 'mc_trials': TRIALS, 'shared_channels': 3, 'analytic_only_models': 2}), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    run(parser.parse_args().output)
