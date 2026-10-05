"""Closed raw sidecar selection and inspection for the local observer UI."""
import hashlib
import json
from pathlib import Path

from vsora_correlator.bispectrum_inspect import inspect_bispectrum_cell
from vsora_formats.bispectrum import load_bispectrum


def _input(workspace, value):
    path = Path(value)
    path = path if path.is_absolute() else Path(workspace) / path
    if path.suffix.lower() != '.npz' or not path.is_file():
        raise ValueError('existing raw/source NPZ files required')
    return path.resolve()


def _stamp(path):
    s = path.stat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def _read_pair(workspace, input, source_visibility):
    raw, source = _input(workspace, input), _input(workspace, source_visibility)
    before = _stamp(raw), _stamp(source)
    with raw.open('rb') as stream:
        raw_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    data = load_bispectrum(raw, source)
    if before != (_stamp(raw), _stamp(source)):
        raise ValueError('input changed during raw inspection; use closed archives')
    return data, raw_sha, data['metadata']['visibility_sha256']


def input_axes(workspace, input, source_visibility):
    data, raw_sha, source_sha = _read_pair(workspace, input, source_visibility)
    return {
        'times_s': data['times_s'].tolist(),
        'frequencies_hz': data['frequencies_hz'].tolist(),
        'time_origin_utc': data['metadata']['time_origin_utc'],
        'station_ids': data['metadata']['station_ids'],
        'bispectrum_unit': data['metadata']['bispectrum_unit'],
        'source_visibility_verified': True,
        'raw_bispectrum_sha256': raw_sha,
        'source_visibility_sha256': source_sha,
    }


def inspect_selected_file(workspace, request, output):
    data, raw_sha, source_sha = _read_pair(workspace, request.input, request.source_visibility)
    if (raw_sha, source_sha) != (request.raw_bispectrum_sha256, request.source_visibility_sha256):
        raise ValueError('selected raw/source identity changed; read input axes again')
    result = inspect_bispectrum_cell(data, request.time_index, request.channel_index)
    result.update(
        source_visibility_verified=True,
        raw_bispectrum_sha256=raw_sha,
        source_visibility_sha256=source_sha,
    )
    text = json.dumps(result, indent=2, allow_nan=False) + '\n'
    with Path(output).open('x', encoding='utf-8') as stream:
        stream.write(text)
    return result
