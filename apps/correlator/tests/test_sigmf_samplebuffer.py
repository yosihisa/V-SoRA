"""明示SigMF入口と既存整列guard/seekの受入。"""
import json

import numpy as np
import pytest

from vsora_correlator.aligned import SampleBuffer


def fixture(tmp_path):
    fs = 1000000
    meta = {'global': {'core:version': '1.2.0', 'core:datatype': 'ci16_le', 'core:sample_rate': fs},
            'captures': [{'core:sample_start': 0, 'core:datetime': '2024-07-30T09:19:20.197Z'}]}
    path = tmp_path / 'raw.sigmf-meta'
    path.write_text(json.dumps(meta))
    words = np.empty((12003, 2), dtype='<i2')
    words[:, 0], words[:, 1] = 320, -64
    path.with_suffix('.sigmf-data').write_bytes(words.tobytes())
    return path, fs


def test_direct_ADC_reader_and_bounded_seek_without_VDIF(tmp_path):
    path, fs = fixture(tmp_path)
    buffers = [SampleBuffer.from_sigmf(path, fs, seek_input=seek, chunk_samples=1000) for seek in (False, True)]
    try:
        values = []
        for buffer in buffers:
            value, valid = buffer.query(10000.25 + np.arange(128))
            assert valid.all() and buffer.sigmf_recording.voltage_unit == 'ADC'
            np.testing.assert_allclose(value, 320 - 64j, rtol=0, atol=1e-10)
            assert buffer.maximum <= 2000
            values.append(value)
        np.testing.assert_array_equal(values[0], values[1])
        assert buffers[1].frames_read < buffers[0].frames_read
        assert buffers[1].initial_sample_index == 9000
    finally:
        for buffer in buffers:
            buffer.close()


@pytest.mark.parametrize('rate', [True, None, '1000000', 0, -1, float('nan'), float('inf'), 10**400, 1001001, 998999])
def test_actual_clock_must_be_explicit_finite_and_in_range(tmp_path, rate):
    path, _ = fixture(tmp_path)
    with pytest.raises(ValueError):
        SampleBuffer.from_sigmf(path, rate)


@pytest.mark.parametrize('rate', [999000, 1001000])
def test_rate_contract_includes_both_1000ppm_endpoints(tmp_path, rate):
    path, _ = fixture(tmp_path)
    buffer = SampleBuffer.from_sigmf(path, rate)
    buffer.close()


def test_sigmf_guard_and_explicit_seek_flag(tmp_path):
    path, fs = fixture(tmp_path)
    with pytest.raises(ValueError, match='seek_input'):
        SampleBuffer.from_sigmf(path, fs, seek_input=1)
    buffer = SampleBuffer.from_sigmf(path, fs)
    try:
        value, valid = buffer.query(np.array([0.]))
        assert not valid.any() and np.array_equal(value, [0.j])
        with pytest.raises(ValueError, match='ends before'):
            buffer.query(np.array([12003.]))
    finally:
        buffer.close()
