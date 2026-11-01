"""限定SigMF readerのbyte/時刻/不正profile/途中変更を検証する。"""
import json
import struct

import astropy.units as u
from astropy.time import Time
import numpy as np
import pytest

from vsora_formats.sigmf import MAX_METADATA_BYTES, SigMFRecording


def fixture(tmp_path, changes=None):
    meta = {'global': {'core:version': '1.2.0', 'core:datatype': 'ci16_le',
                       'core:sample_rate': 20000000},
            'captures': [{'core:sample_start': 0, 'core:frequency': 410000000,
                          'core:datetime': '2024-07-30T09:19:20.197123456Z'}], 'annotations': []}
    if changes is not None:
        scope, key, value = changes
        if scope == 'global':
            meta['global'][key] = value
        elif scope == 'capture':
            meta['captures'][0][key] = value
        else:
            meta[key] = value
    path = tmp_path / 'raw.sigmf-meta'
    path.write_text(json.dumps(meta))
    values = [(-32768, 32767), (0, -1), (1, -2), (30000, -30000), (-7, 11), (16, -32), (2, 3)]
    path.with_suffix('.sigmf-data').write_bytes(b''.join(struct.pack('<hh', *v) for v in values))
    return path, meta, np.array([complex(*v) for v in values])


def test_exact_signed_IQ_timestamp_seek_and_short_tail(tmp_path):
    path, meta, expected = fixture(tmp_path)
    record = SigMFRecording(path, chunk_samples=3)
    frames = list(record.iter_frames())
    assert [x['sample_index'] for x in frames] == [0, 3, 6]
    assert [len(x['data']) for x in frames] == [3, 3, 1]
    np.testing.assert_array_equal(np.concatenate([x['data'] for x in frames]), expected)
    assert all(x['data'].dtype == np.complex128 and x['valid'].all() for x in frames)
    assert all('station_id' not in x for x in frames)
    assert record.sample_count == 7 and record.voltage_unit == 'ADC'
    assert record.sample_rate_hz == 20000000 and record.center_frequency_hz == 410000000
    start = Time(meta['captures'][0]['core:datetime'], scale='utc')
    for x in frames:
        assert abs((x['time'] - start - x['sample_index'] / record.sample_rate_hz * u.s).to_value(u.s)) < 1e-9
    sought = list(record.iter_frames(start_sample=4))
    assert sought[0]['sample_index'] == 3
    np.testing.assert_array_equal(np.concatenate([x['data'] for x in sought]), expected[3:])


BAD_METADATA = [
    ('global', 'core:datatype', 'cf32_le'), ('global', 'core:datatype', 'ci16_be'),
    ('global', 'core:sample_rate', True), ('global', 'core:sample_rate', None),
    ('global', 'core:sample_rate', 0), ('global', 'core:sample_rate', -1),
    ('global', 'core:sample_rate', '20000000'), ('global', 'core:sample_rate', float('inf')),
    ('global', 'core:sample_rate', float('nan')), ('global', 'core:sample_rate', 10**400),
    ('global', 'core:version', '2.0.0'), ('global', 'core:version', True),
    ('global', 'core:num_channels', 2), ('global', 'core:num_channels', True),
    ('global', 'core:offset', 1), ('global', 'core:offset', False),
    ('global', 'core:dataset', 'elsewhere.dat'), ('global', 'core:trailing_bytes', 4),
    ('global', 'core:metadata_only', True), ('global', 'core:metadata_only', 0),
    ('global', 'core:extensions', {}),
    ('global', 'core:extensions', [{'name': 'clock', 'version': '1.0.0', 'optional': False}]),
    ('global', 'core:extensions', [{'name': 'clock', 'version': '1.0.0', 'optional': 1}]),
    ('capture', 'core:sample_start', 1), ('capture', 'core:sample_start', False),
    ('capture', 'core:header_bytes', 4), ('capture', 'core:global_index', 10),
    ('capture', 'core:datetime', '2024-07-30T09:19:20.197'),
    ('capture', 'core:datetime', '2024-07-30T09:19:20.197+01:00'),
    ('capture', 'core:datetime', None), ('capture', 'core:frequency', float('nan')),
    ('root', 'captures', []), ('root', 'captures', [{}, {}]), ('root', 'global', []),
]


@pytest.mark.parametrize('change', BAD_METADATA)
def test_unsupported_or_ambiguous_profile_rejected(tmp_path, change):
    path, _, _ = fixture(tmp_path, change)
    with pytest.raises(ValueError):
        SigMFRecording(path)


@pytest.mark.parametrize('chunk', [0, -1, True, 1.5, 65537])
def test_chunk_is_bounded_integer(tmp_path, chunk):
    path, _, _ = fixture(tmp_path)
    with pytest.raises(ValueError, match='chunk_samples'):
        SigMFRecording(path, chunk_samples=chunk)


@pytest.mark.parametrize('start', [-1, True, 1.5, 7])
def test_seek_rejects_outside_or_noninteger_index(tmp_path, start):
    path, _, _ = fixture(tmp_path)
    with pytest.raises(ValueError, match='start_sample'):
        next(SigMFRecording(path).iter_frames(start_sample=start))


@pytest.mark.parametrize('payload', [b'', b'123', b'12345'])
def test_partial_complex_sample_or_empty_file_rejected(tmp_path, payload):
    path, _, _ = fixture(tmp_path)
    path.with_suffix('.sigmf-data').write_bytes(payload)
    with pytest.raises(ValueError, match='whole ci16_le'):
        SigMFRecording(path)


def test_optional_metadata_preserved_without_claiming_calibration_or_checksum(tmp_path):
    path, meta, expected = fixture(tmp_path)
    meta['global'].update({'core:sha512': '0' * 128, 'dt:datetime': 'unresolved',
                           'core:extensions': [{'name': 'example', 'version': '1.0.0', 'optional': True}]})
    meta['annotations'] = [{'core:sample_start': 0, 'core:sample_count': 1, 'core:label': 'uninterpreted'}]
    path.write_text(json.dumps(meta))
    record = SigMFRecording(path)
    assert record.metadata == meta and not record.checksum_verified
    frame = next(record.iter_frames())
    np.testing.assert_array_equal(frame['data'], expected)
    assert frame['valid'].all()  # annotationの科学的品質を解釈したmaskではない。


def test_metadata_limit_and_duplicate_keys(tmp_path):
    path, _, _ = fixture(tmp_path)
    path.write_bytes(b' ' * (MAX_METADATA_BYTES + 1))
    with pytest.raises(ValueError, match='1 MiB'):
        SigMFRecording(path)
    path.write_text('{"global": {}, "global": {}}')
    with pytest.raises(ValueError, match='duplicate'):
        SigMFRecording(path)


def test_dataset_mutation_before_and_during_iteration_rejected(tmp_path):
    path, _, _ = fixture(tmp_path)
    record = SigMFRecording(path, chunk_samples=3)
    iterator = record.iter_frames()
    next(iterator)
    with path.with_suffix('.sigmf-data').open('ab') as stream:
        stream.write(b'1234')
    with pytest.raises(ValueError, match='changed'):
        next(iterator)
    with pytest.raises(ValueError, match='changed'):
        next(record.iter_frames())
