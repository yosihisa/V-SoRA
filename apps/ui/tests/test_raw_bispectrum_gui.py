"""Stored-value GUI transport; no receiver or image quality certification."""
import hashlib
import os
import time
from itertools import combinations

import numpy as np
import pytest

pytest.importorskip('fastapi')
pytest.importorskip('httpx')
from fastapi.testclient import TestClient
from vsora_correlator.bispectrum_accumulator import BispectrumAccumulator
from vsora_correlator.bispectrum_inspect import inspect_bispectrum_cell
from vsora_formats.bispectrum import load_bispectrum, save_bispectrum
from vsora_formats.spectral import save_spectral
from vsora_ui import raw_bispectrum
from vsora_ui.server import create_app

HEADERS = {'X-VSoRA-Request': '1'}


def fixture_pair(path, blocks=7):
    rng = np.random.default_rng(67)
    x = rng.normal(size=(max(blocks, 1), 4, 4)) + 1j * rng.normal(size=(max(blocks, 1), 4, 4))
    good = np.full((len(x), 4), blocks > 0, dtype=bool)
    acc = BispectrumAccumulator(4, 4)
    acc.consume(x, good)
    q = acc.finish()
    pairs = np.array(list(combinations(range(4), 2)))
    count = np.array([(good[:, i] & good[:, j]).sum() for i, j in pairs])
    means = np.zeros((4, 6), complex)
    for k, (i, j) in enumerate(pairs):
        if count[k]:
            means[:, k] = (x[:, :, i] * x[:, :, j].conj())[good[:, i] & good[:, j]].mean(axis=0)
    times = np.array([.01, .02])
    frequencies = 1.42e9 + np.arange(4, dtype=float)
    weights = np.broadcast_to(count > 0, (2, 4, 6)).astype(float).copy()
    weights[:, 0] = 0
    source = path / 'source.npz'
    raw = path / 'raw.npz'
    save_spectral(source, {'visibilities': np.stack([means] * 2), 'weights': weights,
        'pairs': pairs, 'times_s': times, 'frequencies_hz': frequencies,
        'uvw_lambda': np.zeros((2, 4, 6, 3)), 'valid_fft_count': np.stack([count] * 2)},
        {'visibility_unit': 'ADC^2', 'time_origin_utc': '2026-10-05T00:00:00Z',
         'config': {'stations': [{'id': 'A' + str(i)} for i in range(4)]},
         'fft_length': 4, 'fft_sample_rate_hz': 1024.})
    usable = np.broadcast_to(q['common_sample_count'] >= 3, (2, 4, 4)).copy()
    usable[:, 0] = False
    data = {'triangles': q['triangles'], 'times_s': times, 'frequencies_hz': frequencies,
        'common_fft_count': np.stack([q['common_sample_count']] * 2), 'nominal_fft_count': np.full(2, len(x)),
        'edge_sums': np.stack([q['edge_sums']] * 2), 'paired_edge_sums': np.stack([q['paired_edge_sums']] * 2),
        'triple_edge_sum': np.stack([q['triple_edge_sum']] * 2), 'channel_triangle_usable': usable}
    save_bispectrum(raw, data, {'station_ids': ['A' + str(i) for i in range(4)],
        'time_origin_utc': '2026-10-05T00:00:00Z', 'voltage_unit': 'ADC',
        'fft_length': 4, 'sample_rate_hz': 1024., 'visibility_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'processing_notes': ['Synthetic independent spectra, stored-value GUI transport only.']})
    return raw, source


def wait(client, job_id):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        data = client.get('/api/jobs/' + job_id).json()
        if data['state'] not in ('queued', 'running'):
            return data
        time.sleep(.05)
    raise AssertionError('raw inspection worker timed out')


def selection(client):
    response = client.post('/api/bispectrum-input', json={'input': 'raw.npz', 'source_visibility': 'source.npz'}, headers=HEADERS)
    assert response.status_code == 200
    axes = response.json()
    return {'kind': 'bispectrum_inspection', 'input': 'raw.npz', 'source_visibility': 'source.npz',
        'time_index': 1, 'channel_index': 2, 'raw_bispectrum_sha256': axes['raw_bispectrum_sha256'],
        'source_visibility_sha256': axes['source_visibility_sha256']}, axes


@pytest.mark.parametrize('blocks', [0, 1, 2, 7])
def test_axes_worker_exact_values_and_json(tmp_path, blocks):
    raw, source = fixture_pair(tmp_path, blocks)
    before = raw.read_bytes(), source.read_bytes()
    with TestClient(create_app(tmp_path), base_url='http://127.0.0.1') as client:
        assert '保存した三次統計' in client.get('/').text
        assert client.post('/api/bispectrum-input', json={'input': 'raw.npz', 'source_visibility': 'source.npz'}).status_code == 403
        request, axes = selection(client)
        assert axes['times_s'] == [.01, .02] and axes['source_visibility_verified']
        response = client.post('/api/jobs', json=request, headers=HEADERS)
        assert response.status_code == 202
        job = wait(client, response.json()['id'])
        assert job['state'] == 'complete', job
        expected = inspect_bispectrum_cell(load_bispectrum(raw, source), 1, 2)
        expected.update(source_visibility_verified=True, raw_bispectrum_sha256=request['raw_bispectrum_sha256'], source_visibility_sha256=request['source_visibility_sha256'])
        assert job['summary'] == expected
        assert client.get(f"/api/jobs/{job['id']}/artifacts/bispectrum-inspection.json").json() == expected
        for row in expected['triangles']:
            assert row['state'] == ('usable_raw_value' if blocks >= 3 else 'insufficient_samples')
            if blocks < 3:
                assert row['distinct_sample_bispectrum_real'] is None
        request['channel_index'] = 0
        job = wait(client, client.post('/api/jobs', json=request, headers=HEADERS).json()['id'])
        assert job['state'] == 'complete'
        assert all(row['state'] == ('masked_raw_value' if blocks >= 3 else 'insufficient_samples') for row in job['summary']['triangles'])
        assert not job['summary']['noise_covariance_estimated'] and not job['summary']['production_rml_noise_model_changed']
    assert before == (raw.read_bytes(), source.read_bytes())


@pytest.mark.parametrize('field,value', [('channel_index', True), ('channel_index', 1.5), ('time_index', -1),
    ('time_index', True), ('raw_bispectrum_sha256', 'g' * 64), ('source_visibility_sha256', '0' * 63),
    ('source_visibility', ''), ('command', 'sh')])
def test_strict_request_rejection(tmp_path, field, value):
    fixture_pair(tmp_path)
    with TestClient(create_app(tmp_path), base_url='http://127.0.0.1') as client:
        request, _ = selection(client)
        request[field] = value
        assert client.post('/api/jobs', json=request, headers=HEADERS).status_code == 422
        assert client.get('/api/jobs').json() == []


def test_missing_corrupt_mismatched_input_and_out_of_range(tmp_path):
    raw, source = fixture_pair(tmp_path)
    (tmp_path / 'corrupt.npz').write_bytes(b'not an npz')
    (tmp_path / 'wrong.npz').write_bytes(source.read_bytes() + b'different')
    with TestClient(create_app(tmp_path), base_url='http://127.0.0.1') as client:
        for a, b in [('missing.npz', 'source.npz'), ('corrupt.npz', 'source.npz'), ('raw.npz', 'wrong.npz')]:
            r = client.post('/api/bispectrum-input', json={'input': a, 'source_visibility': b}, headers=HEADERS)
            assert r.status_code == 400 and '照合' in r.json()['detail']
        request, _ = selection(client)
        request['channel_index'] = 4
        job = wait(client, client.post('/api/jobs', json=request, headers=HEADERS).json()['id'])
        assert job['state'] == 'failed' and '範囲外' in job['error_message'] and job['summary'] is None


@pytest.mark.parametrize('field', ['raw_bispectrum_sha256', 'source_visibility_sha256'])
def test_selection_identity_checked_again_by_worker(tmp_path, field):
    fixture_pair(tmp_path)
    with TestClient(create_app(tmp_path), base_url='http://127.0.0.1') as client:
        request, _ = selection(client)
        request[field] = '0' * 64
        job = wait(client, client.post('/api/jobs', json=request, headers=HEADERS).json()['id'])
        assert job['state'] == 'failed' and '読み直' in job['error_message'] and job['summary'] is None
        assert not client.get(f"/api/jobs/{job['id']}/artifacts/bispectrum-inspection.json").status_code == 200


@pytest.mark.parametrize('name', ['raw.npz', 'source.npz'])
def test_changed_during_axes_read(tmp_path, monkeypatch, name):
    fixture_pair(tmp_path)
    original = raw_bispectrum.load_bispectrum
    def changed(*args, **kwargs):
        data = original(*args, **kwargs)
        path = tmp_path / name
        stamp = path.stat()
        # touch() may retain the same coarse filesystem timestamp.
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000_000))
        return data
    monkeypatch.setattr(raw_bispectrum, 'load_bispectrum', changed)
    with pytest.raises(ValueError, match='changed'):
        raw_bispectrum.input_axes(tmp_path, 'raw.npz', 'source.npz')


def test_matching_pair_replaced_after_axes_selection(tmp_path):
    raw, source = fixture_pair(tmp_path)
    with TestClient(create_app(tmp_path), base_url='http://127.0.0.1') as client:
        request, _ = selection(client)
        replacement = tmp_path / 'replacement'
        replacement.mkdir()
        new_raw, new_source = fixture_pair(replacement, 6)
        new_source.replace(source)
        new_raw.replace(raw)
        job = wait(client, client.post('/api/jobs', json=request, headers=HEADERS).json()['id'])
        assert job['state'] == 'failed' and '読み直' in job['error_message'] and job['summary'] is None
