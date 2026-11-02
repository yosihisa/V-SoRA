"""Limited old-header LBASTD fragments: two real polarizations, supplied 8 MHz.

Reads return DiFX s16 convention codes, not calibrated voltage or complex I/Q.
This module does not supply a measured clock, RF assignment or session reader.
"""
from copy import deepcopy
import datetime as dt
import hashlib
import os
from pathlib import Path
import re
import stat

import numpy as np

MAX_CHUNK_SAMPLES = 65536
_LEVELS = np.array([8191, -8192, 24575, -24576], dtype=np.int16)
_LEVELS.setflags(write=False)


def parse_old_lba_header(data):
    if not isinstance(data, bytes) or re.fullmatch(rb'\d{8}:\d{6}\n', data) is None:
        raise ValueError('limited old LBA timestamp header required')
    try:
        return dt.datetime.strptime(data.decode('ascii'), '%Y%m%d:%H%M%S\n').replace(tzinfo=dt.timezone.utc)
    except ValueError as error:
        raise ValueError('invalid old LBA calendar') from error


def decode_lba_std(raw):
    """Decode caller-owned whole u16 words into time x recorded-band arrays."""
    if not isinstance(raw, bytes) or not raw or len(raw) % 2:
        raise ValueError('positive whole little-endian u16 payload required')
    bits = np.unpackbits(np.frombuffer(raw, np.uint8), bitorder='little').reshape(-1, 2)
    codes = (bits[:, 0]+2*bits[:, 1]).reshape(-1, 2)
    return codes, _LEVELS[codes]


def _signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class LBAFragmentRecording:
    """Bounded real-code reads with fresh local fragment identities.

    Original byte offset, nominal Fs and polarization labels are supplied
    context. They are not authenticated against the unacquired original file.
    Closed files and trusted Python callers are assumed; raw changes retaining
    every stat field may escape later guards. There is no permanent file lock.
    """
    voltage_unit = 'DiFX_s16_code'
    is_complex = False
    actual_sample_rate_hz = None
    clock_accuracy_measured = False
    producer_checksum_verified = False
    station_id = None
    band_edge_frequency_hz = None
    sideband = None

    def __init__(self, header_path, payload_path, original_payload_offset_bytes, *,
                 nominal_sample_rate_hz, recorded_pol_order, chunk_samples=4096,
                 expected_header_sha256=None, expected_payload_sha256=None):
        if type(chunk_samples) is not int or not 1 <= chunk_samples <= MAX_CHUNK_SAMPLES:
            raise ValueError('chunk_samples requires integer 1..65536')
        if type(original_payload_offset_bytes) is not int or not 0 <= original_payload_offset_bytes <= 2**53:
            raise ValueError('nonnegative integer original payload byte offset required')
        if type(nominal_sample_rate_hz) is not int or nominal_sample_rate_hz != 8000000:
            raise ValueError('limited reader requires supplied integer nominal 8 MHz')
        if not isinstance(recorded_pol_order, (tuple, list)) or tuple(recorded_pol_order) not in [('R','L'), ('L','R')]:
            raise ValueError('explicit recorded real polarization order required')
        expected = (expected_header_sha256, expected_payload_sha256)
        if (any(v is not None for v in expected) and not all(isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v) for v in expected)):
            raise ValueError('both expected fragment SHA256 values required as lowercase hex')
        self.header_path, self.payload_path = Path(header_path), Path(payload_path)
        self._paths = (self.header_path, self.payload_path)
        self._resolved = tuple(p.resolve() for p in self._paths)
        info = tuple(p.stat() for p in self._paths)
        if any(not stat.S_ISREG(v.st_mode) for v in info) or info[0].st_size != 16 or not info[1].st_size or info[1].st_size % 2:
            raise ValueError('16-byte header and nonempty whole u16 regular payload files required')
        if (info[0].st_dev,info[0].st_ino) == (info[1].st_dev,info[1].st_ino):
            raise ValueError('header and payload must be different real files')
        self._signature = tuple(_signature(v) for v in info)
        header = self.header_path.read_bytes();epoch = parse_old_lba_header(header)
        self._header_sha = hashlib.sha256(header).hexdigest();self._payload_sha = _sha(self.payload_path)
        self._guard()
        if expected[0] is not None and expected != (self._header_sha,self._payload_sha):
            raise ValueError('fresh fragment SHA256 differs from expected pair')
        self.expected_pair_verified = expected[0] is not None
        self.sample_count = info[1].st_size*2
        self.nominal_sample_rate_hz = nominal_sample_rate_hz
        self.recorded_pol_order = tuple(recorded_pol_order)
        self.chunk_samples = chunk_samples
        self.original_payload_offset_bytes = original_payload_offset_bytes
        seconds,ns = divmod(original_payload_offset_bytes*250,1000000000)
        try:
            nominal = epoch+dt.timedelta(seconds=seconds)
        except OverflowError as error:
            raise ValueError('nominal fragment epoch outside calendar range') from error
        self.original_header_datetime = header[:15].decode('ascii')
        self.nominal_start_utc = nominal.strftime('%Y-%m-%dT%H:%M:%S')+f'.{ns:09d}Z'
        self.payload_hash_reads = 1
        self.payload_hash_bytes = info[1].st_size
        self.payload_read_calls = self.payload_bytes_read = self.maximum_payload_read_bytes = 0

    def _guard(self):
        try:
            if (tuple(p.resolve() for p in self._paths) != self._resolved
                    or tuple(_signature(p.stat()) for p in self._paths) != self._signature
                    or _sha(self.header_path) != self._header_sha):
                raise ValueError('LBA fragment changed after identity capture')
        except OSError as error:
            raise ValueError('LBA fragment changed or became unavailable') from error

    @property
    def fragment_identity(self):
        self._guard()
        return deepcopy({'header':{'sha256':self._header_sha,'bytes':16},
            'payload':{'sha256':self._payload_sha,'bytes':self._signature[1][2]},
            'original_payload_offset_bytes':self.original_payload_offset_bytes,
            'nominal_sample_rate_hz':self.nominal_sample_rate_hz,'nominal_start_utc':self.nominal_start_utc,
            'recorded_pol_order':list(self.recorded_pol_order),'voltage_unit':self.voltage_unit,
            'actual_sample_rate_hz':None,'clock_accuracy_measured':False,'producer_checksum_verified':False,
            'station_id':None,'rf_assignment':None,'original_member_full_sha256':None,'archive_full_sha256':None})

    def read_real_samples(self, start_sample, count, *, recorded_pol_index):
        if type(start_sample) is not int or type(count) is not int or not 1 <= count <= MAX_CHUNK_SAMPLES or not 0 <= start_sample < self.sample_count or start_sample+count > self.sample_count:
            raise ValueError('bounded in-range integer sample start/count required')
        if type(recorded_pol_index) is not int or recorded_pol_index not in (0,1):
            raise ValueError('explicit recorded_pol_index 0 or 1 required')
        self._guard()
        first = start_sample//4;last = (start_sample+count+3)//4;byte_count = (last-first)*2
        with self.payload_path.open('rb') as stream:
            if _signature(os.fstat(stream.fileno())) != self._signature[1]:
                raise ValueError('LBA fragment changed while opening')
            stream.seek(first*2);raw = stream.read(byte_count)
            if len(raw) != byte_count:raise EOFError('truncated LBA fragment')
            if _signature(os.fstat(stream.fileno())) != self._signature[1]:
                raise ValueError('LBA fragment changed during reading')
        self._guard()
        _,values = decode_lba_std(raw)
        result = values[start_sample-first*4:start_sample-first*4+count,recorded_pol_index].copy()
        self.payload_read_calls += 1;self.payload_bytes_read += byte_count
        self.maximum_payload_read_bytes = max(self.maximum_payload_read_bytes,byte_count)
        return result

    def iter_real_chunks(self, *, recorded_pol_index, start_sample=0, sample_count=None):
        if type(start_sample) is not int or not 0 <= start_sample < self.sample_count:
            raise ValueError('in-range integer start_sample required')
        total = self.sample_count-start_sample if sample_count is None else sample_count
        if type(total) is not int or total <= 0 or start_sample+total > self.sample_count:
            raise ValueError('in-range positive integer sample_count required')
        for first in range(start_sample,start_sample+total,self.chunk_samples):
            count = min(self.chunk_samples,start_sample+total-first)
            values = self.read_real_samples(first,count,recorded_pol_index=recorded_pol_index)
            yield {'real_samples':values,'sample_index':first,'read_ok':True,
                   'recorded_pol_index':recorded_pol_index,'polarization_label':self.recorded_pol_order[recorded_pol_index],
                   'nominal_source_sample_index':self.original_payload_offset_bytes*2+first,
                   'nominal_offset_s':first/self.nominal_sample_rate_hz}
        self._guard()
