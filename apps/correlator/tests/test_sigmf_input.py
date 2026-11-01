import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time

import pytest

from vsora_correlator.input_identity import SigMFInputIdentity
from vsora_correlator.sigmf_inspect import inspect_sigmf
from vsora_correlator.__main__ import main


@pytest.fixture
def pair(tmp_path):
    metadata = tmp_path / 'record.sigmf-meta'
    metadata.write_text(json.dumps({
        'global': {'core:version': '1.2.0', 'core:datatype': 'ci16_le',
                   'core:sample_rate': 20000000, 'core:sha512': '0' * 128},
        'captures': [{'core:sample_start': 0, 'core:datetime': '2024-07-30T09:19:20.197000Z',
                      'core:frequency': 410000000}],
        'annotations': [{'core:sample_start': 0, 'core:label': 'not interpreted'}],
    }))
    metadata.with_suffix('.sigmf-data').write_bytes(b''.join(struct.pack('<hh', i, -i) for i in range(32)))
    return metadata


def digests(pair):
    return {role: hashlib.sha256(path.read_bytes()).hexdigest()
            for role, path in [('metadata', pair), ('data', pair.with_suffix('.sigmf-data'))]}


def test_fresh_pair_hash_once_per_instance_and_defensive_result(pair, monkeypatch):
    import vsora_correlator.input_identity as module
    original = module.digest_file
    calls = []
    def counted(path):
        calls.append(path)
        return original(path)
    monkeypatch.setattr(module, 'digest_file', counted)
    identity = SigMFInputIdentity(pair)
    data = pair.with_suffix('.sigmf-data')
    assert calls.count(data.resolve()) == 1
    for _ in range(3):
        identity.assert_current(pair)
    assert calls.count(data.resolve()) == 1
    public = identity.public_identity
    for role, h in digests(pair).items():
        assert public[role]['sha256'] == h
    public['data']['sha256'] = 'untrusted'
    assert identity.public_identity['data']['sha256'] == digests(pair)['data']
    stats = identity.diagnostics
    stats['data_hash_file_reads'] = 0
    assert identity.diagnostics['data_hash_file_reads'] == 1
    SigMFInputIdentity(pair)
    assert calls.count(data.resolve()) == 2


@pytest.mark.parametrize('role', ['metadata', 'data'])
def test_same_size_rewrite_with_restored_mtime_detected(pair, role):
    identity = SigMFInputIdentity(pair)
    path = pair if role == 'metadata' else pair.with_suffix('.sigmf-data')
    before = path.stat()
    # A write within the same filesystem timestamp tick may preserve ctime too.
    # This test covers observable stat changes, not the documented blind spot.
    time.sleep(.02)
    payload = bytearray(path.read_bytes());payload[-1] ^= 1
    path.write_bytes(payload)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert path.stat().st_ctime_ns != before.st_ctime_ns
    with pytest.raises(ValueError, match='changed'):
        identity.assert_current()


@pytest.mark.parametrize('role', ['metadata', 'data'])
def test_replacement_and_missing_input_detected(pair, role):
    identity = SigMFInputIdentity(pair)
    path = pair if role == 'metadata' else pair.with_suffix('.sigmf-data')
    new = path.with_suffix('.replacement');new.write_bytes(path.read_bytes());new.replace(path)
    with pytest.raises(ValueError, match='changed'):
        identity.assert_current()
    identity = SigMFInputIdentity(pair);path.unlink()
    with pytest.raises(ValueError, match='unavailable'):
        identity.assert_current()


@pytest.mark.parametrize('role', ['metadata', 'data'])
def test_symlink_retarget_detected(pair, role):
    path = pair if role == 'metadata' else pair.with_suffix('.sigmf-data')
    first = path.with_suffix('.first');second = path.with_suffix('.second')
    path.rename(first);second.write_bytes(first.read_bytes());path.symlink_to(first.name)
    identity = SigMFInputIdentity(pair);path.unlink();path.symlink_to(second.name)
    with pytest.raises(ValueError, match='changed'):
        identity.assert_current()


def test_identity_different_pair_and_metadata_content_guard(pair, monkeypatch):
    import vsora_correlator.input_identity as module
    identity = SigMFInputIdentity(pair)
    with pytest.raises(ValueError, match='different input paths'):
        identity.assert_current(pair.with_name('other.sigmf-meta'))
    # Force unchanged stat to isolate the additional metadata content check.
    monkeypatch.setattr(module, 'snapshot_paths', lambda paths: identity._snapshot)
    pair.write_bytes(pair.read_bytes() + b' ')
    with pytest.raises(ValueError, match='metadata content changed'):
        identity.assert_current()


@pytest.mark.parametrize('role', ['metadata', 'data'])
def test_change_during_hashing_rejected(pair, role, monkeypatch):
    import vsora_correlator.input_identity as module
    original = module.digest_file
    def changing(path):
        digest = original(path)
        if path.suffix == '.sigmf-meta':
            target = pair if role == 'metadata' else pair.with_suffix('.sigmf-data')
            target.write_bytes(target.read_bytes() + b'    ')
        return digest
    monkeypatch.setattr(module, 'digest_file', changing)
    with pytest.raises(ValueError, match='changed'):
        SigMFInputIdentity(pair)


def test_metadata_and_data_cannot_alias(pair):
    data = pair.with_suffix('.sigmf-data');data.unlink();data.symlink_to(pair.name)
    with pytest.raises(ValueError, match='distinct files'):
        SigMFInputIdentity(pair)


def test_inspect_sha_pair_and_supplied_fields_without_paths(pair, tmp_path):
    expected = digests(pair)
    out = tmp_path / 'inspection.json'
    result = inspect_sigmf(pair, out, expected_data_sha256=expected['data'].upper(),
                           expected_metadata_sha256=expected['metadata'].upper())
    assert json.loads(out.read_text()) == result
    assert result['expected_sha256_pair_matched'] is True
    assert result['sample_count'] == 32 and result['supplied_sample_rate_hz'] == 20000000
    assert result['voltage_unit'] == 'ADC' and result['station_id'] is None
    assert result['supplied_capture_datetime'] == '2024-07-30T09:19:20.197000Z'
    assert result['supplied_center_frequency_hz'] == 410000000
    assert not result['producer_checksum_verified'] and not result['actual_clock_measured']
    assert result['identity_diagnostics']['data_hash_file_reads'] == 1
    assert str(tmp_path) not in out.read_text() and 'record.sigmf' not in out.read_text()
    assert inspect_sigmf(pair)['expected_sha256_pair_matched'] is None
    assert digests(pair) == expected


@pytest.mark.parametrize('metadata,data', [
    (None, '0'*64), ('0'*64, None), ('z'*64, '0'*64),
    ('0'*63, '0'*64), (True, '0'*64), ('0'*64, '0'*64),
])
def test_expected_pair_errors_do_not_create_output(pair, tmp_path, metadata, data):
    out = tmp_path / 'rejected.json'
    with pytest.raises(ValueError):
        inspect_sigmf(pair, out, expected_metadata_sha256=metadata, expected_data_sha256=data)
    assert not out.exists()


@pytest.mark.parametrize('destination', ['json', 'metadata', 'data'])
def test_existing_output_including_input_pair_is_never_overwritten(pair, tmp_path, destination):
    out = {'json': tmp_path/'result.json', 'metadata': pair, 'data': pair.with_suffix('.sigmf-data')}[destination]
    if destination == 'json':
        out.write_text('keep')
    before = out.read_bytes()
    with pytest.raises(FileExistsError):
        inspect_sigmf(pair, out)
    assert out.read_bytes() == before


def test_inspection_cli_stdout_saved_result_and_failure(pair, tmp_path, monkeypatch, capsys):
    out = tmp_path / 'cli.json';expected = digests(pair)
    argv = ['vsora-correlate', 'inspect-sigmf', '--metadata', str(pair), '--output', str(out),
            '--expect-metadata-sha256', expected['metadata'], '--expect-data-sha256', expected['data']]
    monkeypatch.setattr(sys, 'argv', argv);main()
    assert json.loads(capsys.readouterr().out) == json.loads(out.read_text())
    with pytest.raises(FileExistsError):
        main()
