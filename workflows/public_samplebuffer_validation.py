"""実ci16_leを保持するreader prototypeと既存単局SampleBufferの限定照合。"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import time
from unittest.mock import patch

import numpy as np
from vsora_correlator import aligned


def helper(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reference = helper('clock_operator_validation')
iq = helper('public_iq_validation')
FS, COUNT, CHUNK, LENGTH = 20000000, 4000000, 4000, 256
QUERIES = ((128, .25), (3904, .75), (2000000, .25), (3999000, .75))
RTOL, ATOL, TAP_ATOL = 1e-11, 1e-8, 1e-12


class RawFrames:
    """検証専用。局時計/session/CLI/InputIdentityの製品実装ではない。"""
    def __init__(self, path):
        self.path = Path(path)
        self.words = np.memmap(path, dtype='<i2', mode='r', shape=(COUNT, 2))
        self.requested = []
        self.frames = self.samples_checked = self.bytes_read = 0

    def __call__(self, path, nominal_rate, station_id, scale, *, start_sample=0):
        assert Path(path) == self.path and nominal_rate == FS and station_id == 1 and scale == 1.
        assert type(start_sample) is int and 0 <= start_sample < COUNT
        first = start_sample // CHUNK * CHUNK
        self.requested.append({'requested_sample': start_sample, 'first_sample': first})
        for offset in range(first, COUNT, CHUNK):
            words = self.words[offset:offset + CHUNK]
            data = words[:, 0].astype(float) + 1j * words[:, 1].astype(float)
            # int16はfloat64で厳密表現できる。gain/8bit量子化を導入しない。
            np.testing.assert_array_equal(data.real, words[:, 0])
            np.testing.assert_array_equal(data.imag, words[:, 1])
            self.frames += 1
            self.samples_checked += len(data)
            self.bytes_read += len(data) * 4
            yield {'data': data, 'valid': np.ones(len(data), bool), 'sample_index': offset}


def independent_output(words, queries, taps):
    """有限畳み込みと明示sinc/cosine式。productionのFIR/補間は呼ばない。"""
    first = int(np.floor(queries.min())) - 64
    last = int(np.floor(queries.max())) + 65
    w = np.asarray(words[first:last], dtype=float)
    voltage = w[:, 0] + 1j * w[:, 1]
    filtered = np.convolve(voltage, taps, mode='full')
    compensated = queries + 32
    index = np.floor(compensated).astype(int)[:, None] + np.arange(-32, 33)
    distance = compensated[:, None] - index
    weights = np.sinc(distance) * np.where(abs(distance) <= 32, (1 + np.cos(np.pi * distance / 32)) / 2, 0.)
    weights /= weights.sum(axis=1)[:, None]
    assert index.min() - first >= 64 and index.max() - first < len(voltage)
    return np.sum(filtered[index - first] * weights, axis=1)


def run(directory, output):
    began = time.monotonic()
    baseline = int(Path('/proc/self/statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE')
    root, out = Path(directory), Path(output)
    if out.exists():
        raise FileExistsError('use a new validation output directory')
    if shutil.disk_usage(out.parent).free < 10 * 1024**3:
        raise OSError('10 GiB free-space reserve required')
    receipt = json.loads((root / 'acquisition.json').read_text())
    assert receipt['complete']
    inputs = {x['name']: x['sha256'] for x in receipt['files']}
    assert all(iq.sha(root / name) == digest for name, digest in inputs.items())
    meta = iq.metadata(root / 'crab-giantpulse.sigmf-meta')
    raw = root / 'crab-giantpulse.sigmf-data'
    assert raw.stat().st_size == COUNT * 4
    words = np.memmap(raw, dtype='<i2', mode='r', shape=(COUNT, 2))
    _, _, taps = reference.finite_operator(1., 0.)
    out.mkdir(parents=True)
    arrays = {'independent_taps': taps}
    records = []
    for number, (start, fraction) in enumerate(QUERIES):
        queries = start + fraction + np.arange(LENGTH)
        expected = independent_output(words, queries, taps)
        both = []
        arrays[f'query_{number}'] = queries
        arrays[f'expected_{number}'] = expected
        for seek in (False, True):
            frames = RawFrames(raw)
            with patch.object(aligned, 'iter_vdif_frames', frames):
                buffer = aligned.SampleBuffer(raw, FS, 1, 1., FS, seek_input=seek)
                try:
                    actual, good = buffer.query(queries)
                    assert good.all()
                    np.testing.assert_allclose(buffer.taps, taps, rtol=RTOL, atol=TAP_ATOL)
                    np.testing.assert_allclose(actual, expected, rtol=RTOL, atol=ATOL)
                    assert buffer.frames_read == frames.frames
                    records.append({'query': number, 'start_sample': start, 'fraction': fraction,
                                    'seek': seek, 'requested_sample': frames.requested[0]['requested_sample'],
                                    'first_sample': buffer.initial_sample_index, 'frames': frames.frames,
                                    'samples_checked_exact': frames.samples_checked,
                                    'raw_bytes_read': frames.bytes_read, 'maximum_buffer_samples': buffer.maximum,
                                    'max_absolute_error_ADC': float(abs(actual - expected).max())})
                    arrays[f'actual_{number}_{seek}'] = actual
                    both.append(actual)
                finally:
                    buffer.close()
        np.testing.assert_allclose(both[0], both[1], rtol=RTOL, atol=ATOL)
    controls = []
    for query, message in [(-1., 'query before available guard samples'),
                           (float(COUNT), 'input ends before requested aligned chunk')]:
        frames = RawFrames(raw)
        with patch.object(aligned, 'iter_vdif_frames', frames):
            buffer = aligned.SampleBuffer(raw, FS, 1, 1., FS)
            try:
                buffer.query(np.array([query]))
            except ValueError as error:
                assert str(error) == message
                controls.append({'query': query, 'rejection': str(error)})
            else:
                raise AssertionError('out-of-record query accepted')
            finally:
                buffer.close()
    frames = RawFrames(raw)
    with patch.object(aligned, 'iter_vdif_frames', frames):
        buffer = aligned.SampleBuffer(raw, FS, 1, 1., FS)
        try:
            guard_value, guard_good = buffer.query(np.array([0.]))
            assert not guard_good.any() and np.array_equal(guard_value, [0.j])
        finally:
            buffer.close()
    summary = {
        'stage': 166, 'scope': 'single-station real ci16 reader prototype and fixed finite SampleBuffer queries',
        'input_sha256': inputs, 'supplied_sample_rate_hz': FS,
        'supplied_capture_datetime': meta['captures'][0]['core:datetime'],
        'other_datetime_unresolved': meta['global'].get('dt:datetime'),
        'actual_clock_rate_measured': False, 'voltage_unit': 'uncalibrated ADC counts',
        'input_count': COUNT, 'reader_chunk_samples': CHUNK, 'reader_quantization_loss': 0,
        'records': records, 'query_windows': len(QUERIES), 'query_points_per_window': LENGTH,
        'nominal_identity_rate_not_inferred': True, 'rtol': RTOL, 'atol_ADC': ATOL, 'tap_atol': TAP_ATOL,
        'out_of_record_controls': controls, 'initial_FIR_guard_masked_zero': True,
        'fullband_physical_resampling_validity': 'unvalidated; fixed FIR changes the supplied signal',
        'station_count': 1, 'baseline_count': 0, 'product_code_changed': False,
        'session_CLI_InputIdentity_integration': False, 'new_MC_trials': 0, 'MCSE': None,
        'physical_flux_clock_or_image_validation': False,
    }
    np.savez_compressed(out / 'arrays.npz', **arrays)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    environment = {'product_modules': {n: str(m.__file__) for n, m in sys.modules.items()
                                      if n.startswith('vsora_') and getattr(m, '__file__', None)},
                   'checkout_helpers': ['clock_operator_validation.py', 'periodic_fft_noise_validation.py',
                                        'public_iq_validation.py'],
                   'wall_s': time.monotonic() - began, 'import_current_rss_bytes': baseline,
                   'final_lifetime_peak_bytes': peak,
                   'conservative_peak_minus_import_current_bytes': max(0, peak - baseline)}
    (out / 'environment.json').write_text(json.dumps(environment, indent=2) + '\n')
    assert environment['conservative_peak_minus_import_current_bytes'] <= 64 * 1024**2
    assert all(iq.sha(root / name) == digest for name, digest in inputs.items())
    print(json.dumps({'state': 'complete', 'cases': len(records), 'input_quantization_loss': 0}))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(args.input, args.output)
