"""製品SigMF readerと実SampleBuffer APIを固定公開原本へ適用する。"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import resource
import sys
import time

import astropy.units as u
import numpy as np
from vsora_formats.sigmf import SigMFRecording
from vsora_correlator.aligned import SampleBuffer


spec = importlib.util.spec_from_file_location('existing_public_buffer_reference',
                                            Path(__file__).with_name('public_samplebuffer_validation.py'))
existing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(existing)


def run(directory, output):
    began = time.monotonic()
    baseline = int(Path('/proc/self/statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE')
    root, out = Path(directory), Path(output)
    if out.exists():
        raise FileExistsError('use a new validation output directory')
    receipt = json.loads((root / 'acquisition.json').read_text())
    assert receipt['complete']
    inputs = {x['name']: x['sha256'] for x in receipt['files']}
    assert all(existing.iq.sha(root / n) == h for n, h in inputs.items())
    metadata_path = root / 'crab-giantpulse.sigmf-meta'
    recording = SigMFRecording(metadata_path)
    assert recording.sample_rate_hz == existing.FS and recording.sample_count == existing.COUNT
    assert recording.voltage_unit == 'ADC' and recording.capture_datetime == recording.metadata['captures'][0]['core:datetime']
    out.mkdir(parents=True)
    frame_count = checked = 0
    maximum_time_error = 0.
    with recording.data_path.open('rb') as binary:
        for frame in recording.iter_frames():
            count = len(frame['data'])
            b = np.frombuffer(binary.read(count * 4), dtype=np.uint8).astype(np.int32).reshape(count, 4)
            manual = np.column_stack((b[:, 0] + 256 * b[:, 1], b[:, 2] + 256 * b[:, 3]))
            manual[manual >= 32768] -= 65536
            np.testing.assert_array_equal(frame['data'].real, manual[:, 0])
            np.testing.assert_array_equal(frame['data'].imag, manual[:, 1])
            assert frame['sample_index'] == checked and frame['valid'].all() and 'station_id' not in frame
            error = abs((frame['time'] - recording.start_time - checked / recording.sample_rate_hz * u.s).to_value(u.s))
            assert error < 1e-9
            maximum_time_error = max(maximum_time_error, error)
            checked += count
            frame_count += 1
        assert checked == existing.COUNT and binary.read(1) == b''
    words = np.memmap(recording.data_path, dtype='<i2', mode='r', shape=(existing.COUNT, 2))
    _, _, taps = existing.reference.finite_operator(1., 0.)
    arrays = {'independent_taps': taps}
    records = []
    for number, (start, fraction) in enumerate(existing.QUERIES):
        queries = start + fraction + np.arange(existing.LENGTH)
        expected = existing.independent_output(words, queries, taps)
        arrays[f'query_{number}'] = queries
        arrays[f'expected_{number}'] = expected
        for seek in (False, True):
            # readerの置換なし。製品の明示入口を実行する。
            buffer = SampleBuffer.from_sigmf(metadata_path, existing.FS, seek_input=seek, chunk_samples=existing.CHUNK)
            try:
                actual, valid = buffer.query(queries)
                assert valid.all()
                np.testing.assert_allclose(actual, expected, rtol=existing.RTOL, atol=existing.ATOL)
                np.testing.assert_allclose(buffer.taps, taps, rtol=existing.RTOL, atol=existing.TAP_ATOL)
                arrays[f'actual_{number}_{seek}'] = actual
                records.append({'query': number, 'seek': seek, 'frames': buffer.frames_read,
                                'first_sample': buffer.initial_sample_index,
                                'maximum_buffer_samples': buffer.maximum,
                                'max_absolute_error_ADC': float(abs(actual - expected).max())})
            finally:
                buffer.close()
    summary = {'stage': 168, 'state': 'complete', 'input_sha256': inputs,
               'sample_count': checked, 'components_checked': checked * 2,
               'all_components_exact': True, 'reader_frames': frame_count,
               'default_reader_chunk_samples': recording.chunk_samples,
               'last_chunk_samples': count, 'max_frame_time_error_s': maximum_time_error,
               'capture_datetime': recording.capture_datetime,
               'supplied_sample_rate_hz': recording.sample_rate_hz,
               'center_frequency_hz': recording.center_frequency_hz,
               'other_datetime_unresolved': recording.metadata['global'].get('dt:datetime'),
               'voltage_unit': recording.voltage_unit, 'reader_quantization_loss': 0,
               'records': records, 'rtol': existing.RTOL, 'atol_ADC': existing.ATOL,
               'reader_monkeypatched': False, 'actual_clock_measured': False,
               'physical_bandwidth_guard_validated': False, 'station_count': 1, 'baseline_count': 0,
               'new_MC_trials': 0, 'MCSE': None, 'new_real_Closure_image_fit': False,
               'session_CLI_InputIdentity_integration': False}
    np.savez_compressed(out / 'arrays.npz', **arrays)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    env = {'product_modules': {n: str(m.__file__) for n, m in sys.modules.items()
                              if n.startswith('vsora_') and getattr(m, '__file__', None)},
           'wall_s': time.monotonic() - began, 'import_current_rss_bytes': baseline,
           'final_lifetime_peak_bytes': peak, 'conservative_peak_minus_import_current_bytes': max(0, peak - baseline)}
    (out / 'environment.json').write_text(json.dumps(env, indent=2) + '\n')
    assert env['conservative_peak_minus_import_current_bytes'] <= 64 * 1024**2
    assert all(existing.iq.sha(root / n) == h for n, h in inputs.items())
    print(json.dumps({'state': 'complete', 'real_samples': checked, 'product_buffer_cases': len(records)}))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(args.input, args.output)
