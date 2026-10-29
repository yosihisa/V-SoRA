"""固定8電圧の量子化前後の有限平均・共分散。実機の較正ではない。"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from vsora_formats.vdif import write_vdif, read_vdif
from vsora_correlator.fx import fx_correlate

FS = 2048000
COUNT = 4096
FFT = 8
RTOL, ATOL = 1e-9, 1e-10


def independent_quantize(x, scale):
    """scalar roundのties-to-evenと飽和、仕様のfloat32復号を直接記述。"""
    def component(v):
        codes = np.array([min(255, max(0, round(float(np.float32(np.float32(np.float32(a / scale) * np.float32(35.5)) + np.float32(127.5))))))
                          for a in v.ravel()], dtype=np.uint8).reshape(v.shape)
        decoded = codes.astype(np.float32)
        decoded -= 127.5
        decoded /= 35.5
        return decoded.astype(float) * scale
    return component(x.real) + 1j * component(x.imag)


def direct_fx(x):
    n = np.arange(FFT)
    dft = np.exp(-2j*np.pi*n[:, None]*n[None, :]/FFT)/np.sqrt(FFT)
    z = np.einsum('kn,sbn->sbk', dft, x.reshape(2, -1, FFT))
    return np.sum(z[0]*z[1].conj(), axis=0)/(COUNT//FFT)


def moments(v):
    """分母8の有限集合。推定分散や不偏標本共分散とは区別する。"""
    x = np.concatenate([v.real, v.imag], axis=1)
    mean = x.mean(axis=0)
    centered = x-mean
    cov = centered.T@centered/len(x)
    direct = sum(np.outer(row, row) for row in centered)/len(x)
    np.testing.assert_allclose(cov, direct, rtol=RTOL, atol=ATOL)
    return mean, cov


def run(output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    n = np.arange(COUNT)
    inputs = []
    for k in range(8):
        phase = 2*np.pi*k/8
        wave = (1+.15*np.cos(phase))*(np.exp(1j*(2*np.pi*.03125*n+phase))
                                       +.3*np.exp(1j*(2*np.pi*.1875*n-2*phase)))
        inputs.append(np.array([wave, .83*np.exp(.6j)*wave]))
    inputs = np.array(inputs)
    pre = np.array([direct_fx(x) for x in inputs])
    pre_mean, pre_cov = moments(pre)
    arrays = {'pre_visibility': pre, 'pre_mean_reim': pre_mean, 'pre_covariance_reim': pre_cov}
    records = []
    for label, scale in [('unclipped', 1.), ('clipped', .125)]:
        folder = out/label
        folder.mkdir()
        actual, reference, fractions = [], [], []
        for k, x in enumerate(inputs):
            expected = independent_quantize(x, scale)
            decoded = []
            clips = []
            for station in range(2):
                target = folder/f'probe{k}-station{station+1}.vdif'
                meta = write_vdif(target, x[station], '2026-10-02T08:00:00Z', FS,
                                  station+1, scale, voltage_unit='ADC')
                y, valid, header = read_vdif(target, FS, station+1, scale)
                np.testing.assert_array_equal(y, expected[station])
                assert valid.all() and header['station_id'] == station+1
                assert target.stat().st_size == 8224
                normalized = x[station]/scale
                clipped = np.mean((abs(normalized.real) > 127.5/35.5)
                                  | (abs(normalized.imag) > 127.5/35.5))
                assert meta['clipped_fraction'] == clipped
                clips.append(float(clipped))
                decoded.append(y)
            fx = fx_correlate(np.array(decoded), FS, fft_length=FFT)
            np.testing.assert_array_equal(fx['pairs'], [[0, 1]])
            np.testing.assert_array_equal(fx['valid_fft_count'], [COUNT//FFT])
            direct = direct_fx(expected)
            np.testing.assert_allclose(fx['vis_jy'][:, 0], direct, rtol=RTOL, atol=ATOL)
            actual.append(fx['vis_jy'][:, 0]); reference.append(direct); fractions.append(clips)
        actual, reference, fractions = map(np.array, [actual, reference, fractions])
        mean, cov = moments(actual)
        ref_mean, ref_cov = moments(reference)
        np.testing.assert_allclose(mean, ref_mean, rtol=RTOL, atol=ATOL)
        np.testing.assert_allclose(cov, ref_cov, rtol=RTOL, atol=ATOL)
        assert (np.max(fractions) == 0) if label == 'unclipped' else (np.min(fractions) > 0)
        arrays.update({label+'_visibility': actual, label+'_reference_visibility': reference,
                       label+'_mean_reim': mean, label+'_covariance_reim': cov,
                       label+'_clipped_fraction': fractions})
        records.append({'label': label, 'scale_supplied_ADC': scale,
                        'clipped_fraction_min': float(fractions.min()),
                        'clipped_fraction_max': float(fractions.max()),
                        'maximum_FX_reference_difference': float(np.max(abs(actual-reference))),
                        'mean_difference_norm_over_pre_mean_norm': float(np.linalg.norm(mean-pre_mean)/np.linalg.norm(pre_mean)),
                        'covariance_difference_norm_over_pre_covariance_norm': float(np.linalg.norm(cov-pre_cov)/np.linalg.norm(pre_cov)),
                        'real_VDIF_files': 16})
    np.savez_compressed(out/'arrays.npz', **arrays)
    summary = {'stage': 153, 'state': 'complete', 'cases': records, 'station_count': 2,
               'finite_probes_shared_across_cases': 8, 'samples_per_station': COUNT,
               'FFT_length': FFT, 'blocks_per_probe': COUNT//FFT,
               'real_VDIF_files': 32, 'VDIF_bytes': 32*8224, 'MC_trials': 0,
               'seed_MCSE_applicable': False, 'rtol': RTOL, 'atol': ATOL,
               'covariance_definition': 'finite eight-probe ReIm population covariance, denominator 8',
               'physical_unit': 'supplied uncalibrated ADC counts; legacy FX vis_jy key is ADC squared here',
               'product_code_changed': False,
               'limits': 'Deterministic shared ensemble; actual codec and plain FX, no FIR/alignment/geometry/rate inference/selection/Closure/RML. No Gaussian/IID/physical coherence, correction factor, real receiver or image calibration.'}
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    origins = {name: module.__file__ for name, module in sys.modules.items()
               if name.startswith('vsora_') and getattr(module, '__file__', None)}
    (out/'module-paths-private.json').write_text(json.dumps(origins, indent=2)+'\n')
    print(json.dumps(summary))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    run(parser.parse_args().output)
