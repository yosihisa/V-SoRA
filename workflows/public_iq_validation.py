"""公開単局SigMF原本の復号・有限FFTを独立計算と照合する検証workflow。"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import struct
import sys
import time

import numpy as np

from vsora_formats.vdif import write_vdif

RTOL, ATOL = 1e-11, 1e-8
NFFT = 256
CHUNK = 65536


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(65536):
            digest.update(block)
    return digest.hexdigest()


def metadata(path):
    meta = json.loads(Path(path).read_text())
    g = meta['global']
    if g['core:datatype'] != 'ci16_le':
        raise ValueError('this reference accepts only ci16_le')
    if len(meta['captures']) != 1 or meta['captures'][0]['core:sample_start'] != 0:
        raise ValueError('single capture at sample zero required')
    if g['core:sample_rate'] != 20000000 or meta['captures'][0]['core:frequency'] != 410000000:
        raise ValueError('unexpected recording profile; review before execution')
    return meta


def run(directory, output):
    started = time.monotonic()
    root = Path(directory)
    out = Path(output)
    if out.exists():
        raise FileExistsError('use a new validation output directory')
    raw = root / 'crab-giantpulse.sigmf-data'
    metapath = root / 'crab-giantpulse.sigmf-meta'
    receipt = json.loads((root / 'acquisition.json').read_text())
    if not receipt['complete']:
        raise ValueError('incomplete acquisition')
    inputs = {entry['name']: entry['sha256'] for entry in receipt['files']}
    if any(sha(root / name) != digest for name, digest in inputs.items()):
        raise ValueError('original bytes changed since acquisition')
    meta = metadata(metapath)
    size = raw.stat().st_size
    if size == 0 or size % 4 or size > 32 * 1024**2:
        raise ValueError('whole complex int16 samples within the fixed byte budget required')
    out.mkdir(parents=True)
    sample_count = size // 4
    used = sample_count // NFFT * NFFT
    words = np.memmap(raw, dtype='<i2', mode='r', shape=(sample_count, 2))
    octets = np.memmap(raw, dtype=np.uint8, mode='r', shape=(sample_count, 4))
    total_power = 0.
    total_i = total_q = 0.
    endpoint_components = 0
    spectrum_sum = np.zeros(NFFT)
    block_power = []
    max_parseval = 0.
    for start in range(0, sample_count, CHUNK):
        stop = min(start + CHUNK, sample_count)
        # 二つのbyteから手書きで符号付き16bitを再構成し、全成分を確認する。
        b = np.asarray(octets[start:stop], dtype=np.int32)
        manual = np.column_stack((b[:, 0] + 256 * b[:, 1], b[:, 2] + 256 * b[:, 3]))
        manual[manual >= 32768] -= 65536
        np.testing.assert_array_equal(words[start:stop], manual)
        # structも最初の一組だけ確認し、I/Qの順序を別実装に対応付ける。
        if start == 0:
            with raw.open('rb') as stream:
                assert struct.unpack('<hh', stream.read(4)) == tuple(manual[0])
        x = manual[:, 0].astype(float) + 1j * manual[:, 1]
        total_i += float(manual[:, 0].sum(dtype=np.int64))
        total_q += float(manual[:, 1].sum(dtype=np.int64))
        p = manual[:, 0].astype(float)**2 + manual[:, 1].astype(float)**2
        total_power += float(p.sum())
        endpoint_components += int(np.count_nonzero((manual == -32768) | (manual == 32767)))
        fft_stop = min(stop, used) - start
        if fft_stop > 0:
            blocks = x[:fft_stop].reshape(-1, NFFT)
            power = np.abs(np.fft.fft(blocks, axis=1, norm='ortho'))**2
            direct_power = p[:fft_stop].reshape(-1, NFFT).mean(axis=1)
            np.testing.assert_allclose(power.mean(axis=1), direct_power, rtol=RTOL, atol=ATOL)
            max_parseval = max(max_parseval, float(np.max(np.abs(power.mean(axis=1) - direct_power))))
            spectrum_sum += power.sum(axis=0)
            block_power.extend(direct_power.tolist())
    # 位置は実行前固定。実データを見て検証箇所・許容を選ばない。
    dft = np.exp(-2j * np.pi * np.outer(np.arange(NFFT), np.arange(NFFT)) / NFFT) / np.sqrt(NFFT)
    dft_max = 0.
    for start in (0, used - NFFT):
        w = np.asarray(words[start:start + NFFT], dtype=float)
        x = w[:, 0] + 1j * w[:, 1]
        independent = dft.dot(x)
        observed = np.fft.fft(x, norm='ortho')
        np.testing.assert_allclose(observed, independent, rtol=RTOL, atol=ATOL)
        dft_max = max(dft_max, float(np.max(np.abs(observed - independent))))
    blocks = used // NFFT
    mean_spectrum = spectrum_sum / blocks
    block_power = np.asarray(block_power)
    np.testing.assert_allclose(mean_spectrum.mean(), block_power.mean(), rtol=RTOL, atol=ATOL)
    if used == sample_count:
        np.testing.assert_allclose(mean_spectrum.mean(), total_power / sample_count, rtol=RTOL, atol=ATOL)
    capture = meta['captures'][0]
    prefix = np.asarray(words[:4096], dtype=float)
    prefix = prefix[:, 0] + 1j * prefix[:, 1]
    try:
        write_vdif(out / 'native-profile-probe.vdif', prefix, capture['core:datetime'],
                   meta['global']['core:sample_rate'], 1, scale=1., voltage_unit='ADC')
    except ValueError as error:
        rejection = str(error)
        assert rejection == 'whole frames and integer frames/second required'
    else:
        raise AssertionError('adapter profile changed; review before converting real input')
    assert not (out / 'native-profile-probe.vdif').exists()
    assert not (out / 'native-profile-probe.json').exists()
    summary = {
        'scope': 'single telescope public voltage; finite numerical identities only',
        'input_sha256': inputs, 'raw_bytes': size, 'sample_count': sample_count,
        'all_components_equal': True, 'components_checked': 2 * sample_count,
        'supplied_sample_rate_hz': meta['global']['core:sample_rate'],
        'supplied_center_frequency_hz': capture['core:frequency'],
        'nominal_duration_s': sample_count / meta['global']['core:sample_rate'],
        'supplied_capture_datetime': capture['core:datetime'],
        'other_datetime_label': meta['global'].get('dt:datetime'),
        'actual_clock_accuracy': 'unmeasured; datetime labels not reconciled',
        'voltage_unit': 'uncalibrated integer ADC counts', 'power_unit': 'ADC^2',
        'mean_I': total_i / sample_count, 'mean_Q': total_q / sample_count,
        'finite_mean_power': total_power / sample_count,
        'int16_endpoint_component_count': endpoint_components,
        'endpoint_count_is_not_receiver_clipping_measurement': True,
        'fft_length': NFFT, 'fft_blocks': blocks, 'unused_tail_samples': sample_count - used,
        'max_parseval_absolute_difference': max_parseval, 'max_dft_absolute_difference': dft_max,
        'rtol': RTOL, 'atol': ATOL, 'native_adapter_rejection': rejection,
        'native_vdif_generated': False, 'station_count': 1, 'baseline_count': 0,
        'new_MC_trials': 0, 'MCSE': None, 'image_or_celestial_detection_verified': False,
    }
    np.savez_compressed(out / 'arrays.npz', mean_spectrum=mean_spectrum,
                        finite_block_power=block_power,
                        baseband_frequency_hz=np.fft.fftfreq(NFFT, 1 / meta['global']['core:sample_rate']))
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    modules = {n: str(m.__file__) for n, m in sys.modules.items()
               if n.startswith('vsora_') and getattr(m, '__file__', None)}
    environment = {'product_modules': modules, 'wall_s': time.monotonic() - started,
                   'lifetime_maxrss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
    (out / 'environment.json').write_text(json.dumps(environment, indent=2) + '\n')
    assert all(sha(root / name) == digest for name, digest in inputs.items())
    print(json.dumps({'state': 'complete', 'sample_count': sample_count, 'native_vdif_generated': False}))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(args.input, args.output)
