"""公開単局I/Qの供給Fs・小数秒epochと8bit量子化を照合する限定参照。"""
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import shutil
import struct
import sys
import time

import astropy.units as u
from astropy.time import Time
from baseband import vdif
import numpy as np

from vsora_formats.vdif import iter_vdif_frames, write_vdif


def helper(name):
    """既存workflowの独立式を再利用。installed検証もcheckoutのhelperを要する。"""
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


independent_quantize = helper('quantized_ensemble_validation').independent_quantize
metadata = helper('public_iq_validation').metadata
FS, COUNT, FRAME = 20000000, 4000000, 4000
SCALE = 256. * 35.5
FRAME_BYTES = 8032
TIME_ATOL_S = 1e-9
MAX_COMPONENT_ERROR_ADC = 129.
EXPECTED_SHA = {
    'crab-giantpulse.sigmf-data': 'e12a408af4d963802623a95ee732c20b0b6b0cbf787454f5b10753d6d04f992e',
    'crab-giantpulse.sigmf-meta': '42878700f4cc91c4cda249ec1d958cea6c7e78fc1b13f3af714f654956f4f188',
}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(65536):
            digest.update(block)
    return digest.hexdigest()


def run(directory, output):
    started = time.monotonic()
    baseline_rss = int(Path('/proc/self/statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE')
    import_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    root, out = Path(directory), Path(output)
    if out.exists():
        raise FileExistsError('use a new validation output directory')
    if shutil.disk_usage(out.parent).free < 10 * 1024**3:
        raise OSError('10 GiB free-space reserve required')
    if any(sha(root / name) != digest for name, digest in EXPECTED_SHA.items()):
        raise ValueError('review changed original input before execution')
    receipt = json.loads((root / 'acquisition.json').read_text())
    assert receipt['complete']
    assert {x['name']: x['sha256'] for x in receipt['files']} == EXPECTED_SHA
    meta = metadata(root / 'crab-giantpulse.sigmf-meta')
    raw = root / 'crab-giantpulse.sigmf-data'
    assert raw.stat().st_size == COUNT * 4
    words = np.memmap(raw, dtype='<i2', mode='r', shape=(COUNT, 2))
    capture = meta['captures'][0]['core:datetime']
    supplied_start = Time(capture, scale='utc')
    dt = datetime.fromisoformat(capture.replace('Z', '+00:00'))
    epoch = datetime(dt.year, 1 if dt.month <= 6 else 7, 1, tzinfo=timezone.utc)
    ref_epoch = 2 * (dt.year - 2000) + (dt.month > 6)
    delta = dt - epoch
    supplied_seconds = Fraction(delta.days * 86400 + delta.seconds) + Fraction(delta.microseconds, 1000000)
    assert FS % FRAME == 0 and COUNT % FRAME == 0
    rate = FS // FRAME
    assert (supplied_seconds % 1) * rate == 985
    out.mkdir(parents=True)
    target = out / 'reference-only.vdif'
    # 全int16範囲から固定したscale。元の実電圧・利得を推定しない。
    with vdif.open(target, 'ws', sample_rate=FS * u.Hz, samples_per_frame=FRAME,
                   nchan=1, nthread=1, complex_data=True, bps=8, edv=0,
                   station=1, time=supplied_start) as writer:
        for offset in range(0, COUNT, FRAME):
            w = words[offset:offset + FRAME].astype(float)
            writer.write((w[:, 0] + 1j * w[:, 1]) / SCALE)
    assert target.stat().st_size == COUNT // FRAME * FRAME_BYTES
    # 書込APIの制約は、そのまま実行して負対照として残す。
    w = words[:FRAME].astype(float)
    try:
        write_vdif(out / 'native-writer-probe.vdif', w[:, 0] + 1j * w[:, 1],
                   capture, FS, 1, SCALE, samples_per_frame=FRAME, voltage_unit='ADC')
    except ValueError as error:
        rejection = str(error)
        assert rejection == 'initial adapter requires UTC integer-second start'
    else:
        raise AssertionError('native writer changed; review this reference')
    assert not (out / 'native-writer-probe.vdif').exists()
    assert not (out / 'native-writer-probe.json').exists()
    frame_error, time_error, sample_indices = [], [], []
    component_max = squared_error = original_power = decoded_power = 0.
    endpoint_codes = 0
    frames = 0
    with target.open('rb') as binary:
        for number, item in enumerate(iter_vdif_frames(target, FS, 1, SCALE)):
            offset = number * FRAME
            assert item['sample_index'] == offset and item['station_id'] == 1
            assert len(item['data']) == FRAME and item['valid'].all()
            seconds = supplied_seconds + Fraction(offset, FS)
            coarse = seconds.numerator // seconds.denominator
            frame_number = (seconds - coarse) * rate
            assert frame_number.denominator == 1
            h = struct.unpack('<8I', binary.read(32))
            # EDV0 headerをBasebandから独立にbit分解する。
            assert h[0] & 0x3fffffff == coarse and h[0] >> 30 == 0
            assert h[1] & 0xffffff == frame_number.numerator
            assert (h[1] >> 24) & 63 == ref_epoch
            assert (h[2] & 0xffffff) * 8 == FRAME_BYTES
            assert (h[2] >> 24) & 31 == 0  # log2(channel数)=0
            assert h[3] & 0xffff == 1 and (h[3] >> 16) & 1023 == 0
            assert (h[3] >> 26) & 31 == 7 and h[3] >> 31 == 1
            assert h[4] >> 24 == 0
            error_s = abs((item['time'] - (supplied_start + offset / FS * u.s)).to_value(u.s))
            assert error_s <= TIME_ATOL_S
            w = words[offset:offset + FRAME].astype(float)
            original = w[:, 0] + 1j * w[:, 1]
            expected = independent_quantize(original, SCALE)
            np.testing.assert_array_equal(item['data'], expected)
            codes = np.column_stack((np.rint(expected.real / SCALE * 35.5 + 127.5),
                                     np.rint(expected.imag / SCALE * 35.5 + 127.5))).astype(np.uint8)
            assert binary.read(FRAME_BYTES - 32) == codes.tobytes()
            endpoint_codes += int(np.count_nonzero((codes == 0) | (codes == 255)))
            diff = item['data'] - original
            maximum = float(max(abs(diff.real).max(), abs(diff.imag).max()))
            assert maximum <= MAX_COMPONENT_ERROR_ADC
            mse_sum = float(np.sum(diff.real**2 + diff.imag**2))
            squared_error += mse_sum
            original_power += float(np.sum(original.real**2 + original.imag**2))
            decoded_power += float(np.sum(item['data'].real**2 + item['data'].imag**2))
            component_max = max(component_max, maximum)
            frame_error.append(mse_sum / FRAME)
            time_error.append(error_s)
            sample_indices.append(offset)
            frames += 1
        assert binary.read(1) == b''
    assert frames == COUNT // FRAME
    selected = next(iter_vdif_frames(target, FS, 1, SCALE, start_sample=FRAME + 1))
    assert selected['sample_index'] == FRAME
    w = words[FRAME:2 * FRAME].astype(float)
    np.testing.assert_array_equal(selected['data'], independent_quantize(w[:, 0] + 1j * w[:, 1], SCALE))
    assert abs((selected['time'] - (supplied_start + FRAME / FS * u.s)).to_value(u.s)) <= TIME_ATOL_S
    summary = {
        'scope': 'single station codec/time reference; no physical clock calibration',
        'input_sha256': EXPECTED_SHA, 'supplied_sample_rate_hz': FS,
        'supplied_capture_datetime': capture, 'other_datetime_unresolved': meta['global'].get('dt:datetime'),
        'actual_clock_accuracy': 'unmeasured', 'sample_count': COUNT,
        'samples_per_frame': FRAME, 'frames_per_second': rate, 'frame_count': frames,
        'frame_bytes': FRAME_BYTES, 'vdif_bytes': target.stat().st_size,
        'vdif_sha256': sha(target), 'first_frame_number': 985,
        'all_header_sample_times_rational_exact': True, 'payload_bytes_checked': COUNT * 2,
        'all_decoded_components_exact_to_independent_quantizer': True,
        'component_count': COUNT * 2, 'scale_ADC': SCALE,
        'max_component_error_ADC': component_max,
        'max_component_error_limit_ADC': MAX_COMPONENT_ERROR_ADC,
        'finite_mean_squared_complex_error_ADC2': squared_error / COUNT,
        'finite_original_mean_power_ADC2': original_power / COUNT,
        'finite_decoded_mean_power_ADC2': decoded_power / COUNT,
        'encoded_endpoint_component_count': endpoint_codes,
        'endpoint_count_is_not_receiver_clipping_measurement': True,
        'time_atol_s': TIME_ATOL_S, 'max_frame_time_error_s': max(time_error),
        'range_first_sample_index': selected['sample_index'],
        'native_writer_rejection': rejection, 'production_writer_modified': False,
        'resampled_dropped_padded_samples': 0, 'station_count': 1, 'baseline_count': 0,
        'station_id_is_local_codec_identifier': True, 'MCSE': None, 'new_MC_trials': 0,
        'physical_flux_or_image_validation': False,
    }
    np.savez_compressed(out / 'arrays.npz', frame_mean_squared_error_ADC2=frame_error,
                        frame_time_error_s=time_error, frame_sample_index=sample_indices)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    # 外部Fs/scaleは検証summaryに保持。VDIF EDV0自身にはFsが格納されない。
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    environment = {
        'product_modules': {n: str(m.__file__) for n, m in sys.modules.items()
                            if n.startswith('vsora_') and getattr(m, '__file__', None)},
        'checkout_helpers': ['quantized_ensemble_validation.py', 'public_iq_validation.py'],
        'wall_s': time.monotonic() - started, 'import_current_rss_bytes': baseline_rss,
        'import_lifetime_peak_bytes': import_peak, 'final_lifetime_peak_bytes': peak,
        'conservative_peak_minus_import_current_bytes': max(0, peak - baseline_rss),
    }
    (out / 'environment.json').write_text(json.dumps(environment, indent=2) + '\n')
    assert environment['conservative_peak_minus_import_current_bytes'] <= 64 * 1024**2
    assert all(sha(root / name) == digest for name, digest in EXPECTED_SHA.items())
    print(json.dumps({'state': 'complete', 'sample_count': COUNT, 'frames': frames}))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(args.input, args.output)
