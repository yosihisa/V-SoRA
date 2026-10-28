"""既知の短い色付けFIRを既存049へ合成し、直接電圧と独立traceへ照合する。"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
from scipy.signal import firwin, lfilter
from vsora_correlator.clock import interpolate_samples
from vsora_correlator.stream_fx import FXAccumulator
from vsora_simulator.filtered_noise import aligned_fft_kernel, filtered_visibility_moments


FFT = 8
BLOCKS = 16
TRIALS = 4096
OFFSETS = (0., .25, .5, .75)
CHANNELS = (3, 4, 5)


def dense_real_moments(station_covariance, kernels):
    """全出力時刻の実Gaussian二次形式。049のlag和やWick実装を呼ばない。"""
    n, width = kernels.shape
    length = (BLOCKS-1)*FFT+width
    operator = np.zeros((n, BLOCKS, length), complex)
    for station in range(n):
        for block in range(BLOCKS):
            operator[station, block, block*FFT:block*FFT+width] = kernels[station]
    covariance = np.block([[station_covariance[i, j]*(operator[i] @ operator[j].conj().T)
                            for j in range(n)] for i in range(n)])
    real = .5*np.block([[covariance.real, -covariance.imag],
                       [covariance.imag, covariance.real]])
    pairs = np.array([(i, j) for i in range(n) for j in range(i+1, n)])
    dimension = n*BLOCKS
    quadratic = np.zeros((2*len(pairs), 2*dimension, 2*dimension))
    for baseline, (i, j) in enumerate(pairs):
        for block in range(BLOCKS):
            ri = i*BLOCKS+block; rj = j*BLOCKS+block
            ii = ri+dimension; ij = rj+dimension
            for a, b in ((ri, rj), (ii, ij)):
                quadratic[baseline, a, b] = quadratic[baseline, b, a] = .5/BLOCKS
            for a, b, sign in ((ii, rj, 1), (ri, ij, -1)):
                quadratic[baseline+len(pairs), a, b] = quadratic[baseline+len(pairs), b, a] = sign*.5/BLOCKS
    product = quadratic @ real
    means = np.trace(product, axis1=1, axis2=2)
    return means, 2*np.einsum('aij,bji->ab', product, product)


def run(output):
    out = Path(output)
    if out.exists():
        raise FileExistsError('choose a new colored FFT validation output')
    began = time.monotonic()
    out.mkdir(parents=True)
    phase = np.exp(1j*np.array([0., .4, 1.1, 2.2]))
    station = np.ones((4, 4))+.7*phase[:, None]*phase.conj()[None, :]+1.5*np.eye(4)
    factor = np.linalg.cholesky(station)
    colors = [('white', np.array([1., 0., 0.], complex)),
              ('colored', np.array([1., .75j, .25])/np.sqrt(1+.75**2+.25**2))]
    taps = firwin(65, .35, fs=1., window=('kaiser', 8.6))
    length = BLOCKS*FFT+192+2
    pairs = np.array([(i, j) for i in range(4) for j in range(i+1, 4)])
    base_kernels = np.array([[aligned_fft_kernel(FFT, channel, offset)
                             for offset in OFFSETS] for channel in range(FFT)])
    arrays = {}; records = []
    for label, color in colors:
        kernels = np.array([[np.convolve(h, color[::-1]) for h in row] for row in base_kernels])
        expected = []
        for channel in CHANNELS:
            q = filtered_visibility_moments(station, kernels[channel], FFT, BLOCKS)
            mean, covariance = dense_real_moments(station, kernels[channel])
            np.testing.assert_allclose(mean, np.r_[q['mean'].real, q['mean'].imag], rtol=1e-11, atol=1e-11)
            np.testing.assert_allclose(covariance, q['real_covariance'], rtol=1e-11, atol=1e-11)
            expected.append(q)
        sums = np.zeros((len(CHANNELS), 12)); products = np.zeros((len(CHANNELS), 12, 12))
        squared = products.copy(); direct_difference = 0.; fx_difference = 0.
        # 両colorで同じ生乱数を使い、全channelも同じ電圧から作る。
        rng = np.random.default_rng(141)
        for first in range(0, TRIALS, 32):
            count = min(32, TRIALS-first)
            z = (rng.normal(size=(count, length, 4))+1j*rng.normal(size=(count, length, 4)))/np.sqrt(2)
            raw = (z @ factor.T).transpose(0, 2, 1)
            filtered = lfilter(taps, [1], lfilter(color, [1], raw, axis=-1), axis=-1)
            y = np.empty((count, 4, BLOCKS*FFT), complex)
            for station_index, offset in enumerate(OFFSETS):
                positions = (np.arange(count)[:, None]*length+98+offset+np.arange(BLOCKS*FFT)).ravel()
                values, good = interpolate_samples(filtered[:, station_index].ravel(), positions)
                assert good.all()
                y[:, station_index] = values.reshape(count, -1)
            spectrum = np.fft.fftshift(np.fft.fft(y.reshape(count, 4, BLOCKS, FFT), axis=-1, norm='ortho'), axes=-1)
            if first == 0:
                for trial in range(2):
                    direct = np.array([[[kernels[c, s] @ raw[trial, s, block*FFT:block*FFT+kernels.shape[-1]]
                                         for block in range(BLOCKS)] for s in range(4)] for c in range(FFT)])
                    actual = spectrum[trial].transpose(2, 0, 1)
                    np.testing.assert_allclose(actual, direct, rtol=1e-11, atol=1e-11)
                    direct_difference = max(direct_difference, float(np.max(abs(actual-direct))))
                    accumulator = FXAccumulator(4, 1., FFT, 0.)
                    accumulator.consume(y[trial]); fx = accumulator.finish()['vis_jy'][0]
                    manual = (spectrum[trial, pairs[:, 0]]*spectrum[trial, pairs[:, 1]].conj()).mean(axis=1).T
                    np.testing.assert_allclose(fx, manual, rtol=1e-11, atol=1e-11)
                    fx_difference = max(fx_difference, float(np.max(abs(fx-manual))))
            for row, channel in enumerate(CHANNELS):
                selected = spectrum[:, :, :, channel]
                values = (selected[:, pairs[:, 0], :]*selected[:, pairs[:, 1], :].conj()).mean(axis=-1)
                residual = values-expected[row]['mean']
                real = np.c_[residual.real, residual.imag]
                sums[row] += real.sum(axis=0)
                products[row] += real.T @ real
                squared[row] += (real**2).T @ (real**2)
        for row, channel in enumerate(CHANNELS):
            q = expected[row]; truth = q['real_covariance']
            measured = products[row]/TRIALS
            se = np.sqrt(np.maximum(0., (squared[row]-products[row]**2/TRIALS)/(TRIALS-1))/TRIALS)
            mean = sums[row]/TRIALS; mean_se = np.sqrt(np.maximum(0., np.diag(truth))/TRIALS)
            scale = np.sqrt(np.diag(truth)[:, None]*np.diag(truth)[None, :])
            assert np.all(abs(measured-truth) <= 6*se+1e-11*np.max(scale))
            assert np.all(abs(mean) <= 6*mean_se+1e-11*np.sqrt(np.max(np.diag(truth))))
            iid = q['iid_counterfactual_real_covariance']
            ratio = np.diag(truth)/np.diag(iid)
            key = f'{label}_channel{channel}'
            for name, value in [('known_mean', q['mean']), ('known_real_covariance', truth),
                                ('iid_real_covariance', iid), ('measured_real_covariance', measured),
                                ('covariance_mcse', se), ('measured_centered_mean', mean), ('mean_mcse', mean_se)]:
                arrays[key+'_'+name] = value
            records.append({'color': label, 'channel': channel, 'trials': TRIALS,
                'nominal_fft_blocks': BLOCKS, 'fixed_station_offsets_samples': list(OFFSETS),
                'input_fir_real': color.real.tolist(), 'input_fir_imag': color.imag.tolist(),
                'known_variance_to_iid_range': [float(ratio.min()), float(ratio.max())],
                'maximum_normalized_exact_iid_difference': float(np.max(abs(truth-iid)/scale)),
                'maximum_mean_difference_in_mcse': float(np.max(abs(mean)/(mean_se+1e-30))),
                'maximum_covariance_difference_in_mcse': float(np.max(abs(measured-truth)/(se+1e-30))),
                'dense_real_trace_matches_existing049': True, 'all_mc_means_and_covariances_within_fixed_6mcse': True,
                'direct_all_fft_channel_kernel_max_abs_error': direct_difference,
                'first_two_trials_fx_max_abs_error': fx_difference,
                'single_effective_count_assumed': False, 'observational_confidence_interval_calibrated': False})
        print(json.dumps({'color': label, 'trials': TRIALS, 'channels_shared': list(CHANNELS), 'complete': True}), flush=True)
    summary = {'stage': 141, 'state': 'complete', 'trials_per_color': TRIALS,
        'color_ensembles': 2, 'total_generated_trial_rows': 2*TRIALS,
        'same_raw_random_numbers_across_colors': True, 'same_voltages_across_channels': True,
        'cases': records, 'new_product_noise_api': False, 'production_rml_changed': False,
        'physical_adc_vdif_processed': False, 'matches131_periodic_colored_input': False,
        'variable_clock_geometry_rate_quantization_masks_verified': False,
        'unknown_gain_sefd_or_real_casa_verified': False,
        'scope': 'Known proper Gaussian raw covariance and fixed finite coloring/FIR/sinc/FFT operators; unselected voltages, no measured effective FFT count or coverage.'}
    (out/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
    np.savez_compressed(out/'arrays.npz', **arrays)
    modules = {n: m.__file__ for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None)}
    (out/'runtime-private.json').write_text(json.dumps({'module_paths': modules, 'wall_s': time.monotonic()-began,
        'peak_process_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}, indent=2)+'\n')
    assert sum(p.stat().st_size for p in out.iterdir()) < 16*1024**2
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    run(parser.parse_args().output)
