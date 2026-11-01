"""Inspect a limited SigMF pair without inventing station or clock calibration."""
import json
from pathlib import Path
import re

from .input_identity import SigMFInputIdentity


def inspect_sigmf(metadata_path, output_path=None, *, expected_data_sha256=None,
                  expected_metadata_sha256=None):
    """Return fresh byte identity and supplied fields; optionally save new JSON.

    Expected hashes must be supplied as a pair. A match is a local byte-identity
    check, not authentication of a producer's checksum or an observation.
    """
    expected = (expected_metadata_sha256, expected_data_sha256)
    if (expected[0] is None) != (expected[1] is None):
        raise ValueError('both expected metadata and data SHA256 values are required')
    if expected[0] is not None and any(
            not isinstance(h, str) or re.fullmatch(r'[0-9a-fA-F]{64}', h) is None for h in expected):
        raise ValueError('expected SHA256 values require 64 hexadecimal characters')
    if output_path is not None and Path(output_path).exists():
        raise FileExistsError('SigMF inspection output already exists')
    identity = SigMFInputIdentity(metadata_path)
    public = identity.public_identity
    if expected[0] is not None and any(
            public[role]['sha256'] != value.lower()
            for role, value in zip(('metadata', 'data'), expected)):
        raise ValueError('SigMF input SHA256 pair does not match expected bytes')
    record = identity.recording
    identity.assert_current()
    result = {
        'schema_version': 1,
        'format': 'sigmf-ci16-le-single-capture',
        'identity': public,
        'expected_sha256_pair_matched': True if expected[0] is not None else None,
        'sample_count': record.sample_count,
        'supplied_sample_rate_hz': record.sample_rate_hz,
        'supplied_capture_datetime': record.capture_datetime,
        'supplied_center_frequency_hz': record.center_frequency_hz,
        'voltage_unit': record.voltage_unit,
        'station_id': None,
        'actual_clock_measured': False,
        'producer_checksum_verified': False,
        'annotations_and_optional_extensions_interpreted': False,
        'identity_diagnostics': identity.diagnostics,
        'scope': 'Limited profile and byte identity only; no full waveform quality, RFI, sky detection, correlation or imaging validation.',
    }
    encoded = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if output_path is not None:
        with Path(output_path).open('x') as stream:
            stream.write(encoded)
    return result
