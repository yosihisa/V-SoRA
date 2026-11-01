"""単局・単captureのci16_le SigMFを、追加量子化なしで有界読込する。"""
import json
import math
import os
from pathlib import Path
import re
import stat

import astropy.units as u
from astropy.time import Time
import numpy as np


MAX_METADATA_BYTES = 1024**2
MAX_CHUNK_SAMPLES = 65536


def _integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError):
        return False


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate SigMF metadata key')
        result[key] = value
    return result


def _signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


class SigMFRecording:
    """限定profileの読取記述子。供給clockの精度やSHA512を自動保証しない。

    validはbyte読込成功だけを表す。annotation/任意拡張の品質指定は
    解釈しない。sample_indexはこのdatasetの先頭を0とする。
    """
    voltage_unit = 'ADC'

    def __init__(self, metadata_path, *, chunk_samples=4096):
        if not _integer(chunk_samples, 1, MAX_CHUNK_SAMPLES):
            raise ValueError('chunk_samples requires integer 1..65536')
        path = Path(metadata_path)
        if not path.name.endswith('.sigmf-meta'):
            raise ValueError('SigMF metadata filename must end in .sigmf-meta')
        with path.open('rb') as stream:
            encoded = stream.read(MAX_METADATA_BYTES + 1)
        if len(encoded) > MAX_METADATA_BYTES:
            raise ValueError('SigMF metadata exceeds 1 MiB')
        meta = json.loads(encoded, object_pairs_hook=_unique_object)
        if not isinstance(meta, dict) or not isinstance(meta.get('global'), dict):
            raise ValueError('SigMF global object required')
        global_ = meta['global']
        version = global_.get('core:version')
        if not isinstance(version, str) or not re.fullmatch(r'1\.[0-9]+\.[0-9]+', version):
            raise ValueError('limited SigMF reader requires core version 1.x.y')
        if global_.get('core:datatype') != 'ci16_le':
            raise ValueError('only SigMF ci16_le is supported')
        if not _integer(global_.get('core:num_channels', 1), 1, 1):
            raise ValueError('single SigMF channel required')
        if not _integer(global_.get('core:offset', 0), 0, 0):
            raise ValueError('SigMF offset must be zero')
        if ('core:dataset' in global_ or not _integer(global_.get('core:trailing_bytes', 0), 0, 0)
                or global_.get('core:metadata_only', False) is not False):
            raise ValueError('non-conforming or metadata-only SigMF is unsupported')
        rate = global_.get('core:sample_rate')
        if not _finite(rate) or rate <= 0:
            raise ValueError('positive finite SigMF sample rate required')
        extensions = global_.get('core:extensions', [])
        if not isinstance(extensions, list):
            raise ValueError('SigMF extensions must be an array')
        for item in extensions:
            if (not isinstance(item, dict) or set(item) != {'name', 'version', 'optional'}
                    or not isinstance(item['name'], str) or not isinstance(item['version'], str)
                    or type(item['optional']) is not bool or not item['optional']):
                raise ValueError('unsupported required or malformed SigMF extension')
        captures = meta.get('captures')
        if not isinstance(captures, list) or len(captures) != 1 or not isinstance(captures[0], dict):
            raise ValueError('one SigMF capture required')
        capture = captures[0]
        if not _integer(capture.get('core:sample_start'), 0, 0):
            raise ValueError('SigMF capture must start at sample zero')
        if (not _integer(capture.get('core:header_bytes', 0), 0, 0)
                or not _integer(capture.get('core:global_index', 0), 0, 0)):
            raise ValueError('SigMF headers/global index mapping is unsupported')
        epoch = capture.get('core:datetime')
        if not isinstance(epoch, str) or not re.fullmatch(
                r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z', epoch):
            raise ValueError('explicit UTC-Z SigMF capture datetime required')
        self.start_time = Time(epoch[:-1], format='isot', scale='utc', precision=9)
        frequency = capture.get('core:frequency')
        if frequency is not None and not _finite(frequency):
            raise ValueError('finite SigMF center frequency required when supplied')
        self.metadata_path = path
        self.data_path = path.with_name(path.name[:-len('.sigmf-meta')] + '.sigmf-data')
        info = self.data_path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size == 0 or info.st_size % 4:
            raise ValueError('nonempty whole ci16_le samples in a regular file required')
        self._signature = _signature(info)
        self.sample_count = info.st_size // 4
        self.sample_rate_hz = rate
        self.center_frequency_hz = frequency
        self.capture_datetime = epoch
        self.chunk_samples = chunk_samples
        self.metadata = meta
        self.checksum_verified = False

    def iter_frames(self, *, start_sample=0):
        """開始をchunkへ切り下げる。短い末尾を保持し、局ID/値/時刻を捏造しない。"""
        if not _integer(start_sample, 0, self.sample_count - 1):
            raise ValueError('start_sample requires an in-range nonnegative integer')
        first = start_sample // self.chunk_samples * self.chunk_samples
        with self.data_path.open('rb') as stream:
            if _signature(os.fstat(stream.fileno())) != self._signature:
                raise ValueError('SigMF dataset changed after metadata validation')
            stream.seek(first * 4)
            for index in range(first, self.sample_count, self.chunk_samples):
                if _signature(os.fstat(stream.fileno())) != self._signature:
                    raise ValueError('SigMF dataset changed during reading')
                count = min(self.chunk_samples, self.sample_count - index)
                payload = stream.read(count * 4)
                if len(payload) != count * 4:
                    raise EOFError('truncated SigMF dataset')
                words = np.frombuffer(payload, dtype='<i2').reshape(count, 2)
                data = np.empty(count, dtype=np.complex128)
                data.real, data.imag = words[:, 0], words[:, 1]
                yield {'data': data, 'valid': np.ones(count, dtype=bool),
                       'sample_index': index, 'time': self.start_time + index / self.sample_rate_hz * u.s}
            if (_signature(os.fstat(stream.fileno())) != self._signature
                    or _signature(self.data_path.stat()) != self._signature):
                raise ValueError('SigMF dataset changed during reading')
