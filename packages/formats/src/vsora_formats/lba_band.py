"""Explicit USB complex-band view of one real LBA polarization.

This finite digital operator preserves nominal sample coordinates. It does not
provide a measured clock, calibrated voltage, ideal analytic signal or session.
"""
from copy import deepcopy
import hashlib
import json

import numpy as np
from scipy.signal import firwin

from .lba import LBAFragmentRecording


RADIUS = 64
MAX_COMPLEX_SAMPLES = 16384
_TAPS = np.asarray(firwin(129, 7/32, window=('kaiser', 8.6), fs=1), dtype='<f8')
_TAPS.setflags(write=False)
_NCO = np.array([1, -1j, -1, 1j], dtype=np.complex128)
_NCO.setflags(write=False)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _mix_and_filter(real, source_first):
    """Internal finite operator; callers of the view receive guarded code data."""
    phases = (source_first+np.arange(len(real), dtype=np.int64)) % 4
    mixed = 2.0*real*_NCO[phases]
    return np.asarray(np.convolve(mixed, _TAPS, mode='valid'), dtype=np.complex128)


class LBAComplexBandView:
    """Select one supplied-USB real polarization with fixed mixing and FIR.

    The live source reader supplies identity and read guards. Closed inputs and
    trusted Python are assumed; all-stat-preserving raw changes and changes
    after the final check are not excluded. No persistent digest cache is used.
    """
    voltage_unit = 'DiFX_s16_code_complex_band'
    is_complex = True
    actual_sample_rate_hz = None
    clock_accuracy_measured = False
    station_id = None
    band_edge_frequency_hz = None
    center_frequency_hz = None
    producer_checksum_verified = False

    def __init__(self, recording, *, recorded_pol_index, sideband, chunk_samples=4096):
        if not isinstance(recording, LBAFragmentRecording):
            raise TypeError('live LBAFragmentRecording source required')
        if type(recorded_pol_index) is not int or recorded_pol_index not in (0, 1):
            raise ValueError('explicit recorded_pol_index 0 or 1 required')
        if type(sideband) is not str or sideband != 'U':
            raise ValueError('explicit supplied USB sideband U required')
        if type(chunk_samples) is not int or not 1 <= chunk_samples <= MAX_COMPLEX_SAMPLES:
            raise ValueError('chunk_samples requires integer 1..16384')
        if (type(recording.sample_count) is not int or recording.sample_count <= 2*RADIUS
                or type(recording.nominal_sample_rate_hz) is not int
                or recording.nominal_sample_rate_hz != 8000000
                or recording.voltage_unit != 'DiFX_s16_code'
                or recording.is_complex is not False
                or recording.actual_sample_rate_hz is not None):
            raise ValueError('limited real code source with support and unknown actual clock required')
        self._source = recording
        self._identity = recording.fragment_identity
        self._identity_json = _canonical(self._identity)
        self._context_json = self._context()
        self.recorded_pol_index = recorded_pol_index
        self.polarization_label = recording.recorded_pol_order[recorded_pol_index]
        self.sideband = sideband
        self.chunk_samples = chunk_samples
        self.sample_count = recording.sample_count
        self.nominal_sample_rate_hz = recording.nominal_sample_rate_hz
        self.nominal_start_utc = recording.nominal_start_utc
        self.first_valid_sample_index = RADIUS
        self.stop_valid_sample_index = self.sample_count-RADIUS
        self.valid_sample_count = self.sample_count-2*RADIUS
        self._view_context_json = self._view_context()
        self._assert_source()

    def _context(self):
        try:
            return _canonical({name:getattr(self._source, name) for name in (
                'sample_count', 'nominal_sample_rate_hz', 'original_payload_offset_bytes',
                'recorded_pol_order', 'voltage_unit', 'is_complex', 'actual_sample_rate_hz',
                'station_id', 'band_edge_frequency_hz', 'sideband')})
        except (TypeError, ValueError) as error:
            raise ValueError('LBA source context changed or unsupported') from error

    def _assert_source(self):
        if self._view_context() != self._view_context_json:
            raise ValueError('LBA complex-band view context changed')
        if (_canonical(self._source.fragment_identity) != self._identity_json
                or self._context() != self._context_json):
            raise ValueError('LBA source identity or context changed')

    def _view_context(self):
        try:
            return _canonical({name:getattr(self, name) for name in (
                'recorded_pol_index', 'polarization_label', 'sideband', 'chunk_samples',
                'sample_count', 'nominal_sample_rate_hz', 'nominal_start_utc',
                'first_valid_sample_index', 'stop_valid_sample_index', 'valid_sample_count',
                'voltage_unit', 'actual_sample_rate_hz', 'is_complex', 'station_id',
                'band_edge_frequency_hz', 'center_frequency_hz')})
        except (TypeError, ValueError) as error:
            raise ValueError('LBA complex-band view context changed or unsupported') from error

    @property
    def filter_coefficients(self):
        return _TAPS.copy()

    @property
    def processing_identity(self):
        self._assert_source()
        return deepcopy({
            'source_fragment_identity':self._identity,
            'operator':'real USB quarter-band mixing and finite centered FIR',
            'recorded_pol_index':self.recorded_pol_index,
            'polarization_label':self.polarization_label,
            'supplied_sideband':self.sideband,
            'digital_center_cycles_per_sample':0.25,
            'real_to_complex_amplitude_factor':2,
            'filter_numtaps':129, 'filter_window':'symmetric Kaiser', 'filter_beta':8.6,
            'filter_cutoff_cycles_per_sample':7/32,
            'filter_coefficients_sha256':hashlib.sha256(_TAPS.tobytes()).hexdigest(),
            'coefficient_encoding':'little-endian float64',
            'recommended_retained_half_band_cycles_per_sample':3/16,
            'ideal_analytic_or_perfect_image_rejection':False,
            'filter_center_input_sample_index_preserved':True,
            'required_support_each_side_samples':RADIUS,
            'first_valid_sample_index':self.first_valid_sample_index,
            'stop_valid_sample_index':self.stop_valid_sample_index,
            'downsampled':False, 'voltage_unit':self.voltage_unit,
            'actual_sample_rate_hz':None, 'actual_clock_measured':False,
            'station_id':None, 'rf_assignment':None,
            'physical_voltage_calibration_verified':False,
            'producer_checksum_verified':False})

    def read_complex_samples(self, start_sample, count):
        if (type(start_sample) is not int or type(count) is not int
                or not 1 <= count <= MAX_COMPLEX_SAMPLES
                or start_sample < self.first_valid_sample_index
                or start_sample+count > self.stop_valid_sample_index):
            raise ValueError('bounded integer centers require full FIR support on both sides')
        self._assert_source()
        first = start_sample-RADIUS
        real = self._source.read_real_samples(first, count+2*RADIUS,
                                             recorded_pol_index=self.recorded_pol_index)
        source_first = self._source.original_payload_offset_bytes*2+first
        result = _mix_and_filter(real, source_first)
        self._assert_source()
        return result

    def iter_complex_chunks(self, *, start_sample=None, sample_count=None):
        first = self.first_valid_sample_index if start_sample is None else start_sample
        if type(first) is not int or not self.first_valid_sample_index <= first < self.stop_valid_sample_index:
            raise ValueError('integer first center requires full FIR support')
        total = self.stop_valid_sample_index-first if sample_count is None else sample_count
        if type(total) is not int or total <= 0 or first+total > self.stop_valid_sample_index:
            raise ValueError('positive integer count requires full FIR support')
        for start in range(first, first+total, self.chunk_samples):
            count = min(self.chunk_samples, first+total-start)
            yield {'complex_samples':self.read_complex_samples(start, count),
                   'sample_index':start, 'recorded_pol_index':self.recorded_pol_index,
                   'polarization_label':self.polarization_label,
                   'nominal_source_sample_index':self._source.original_payload_offset_bytes*2+start,
                   'nominal_offset_s':start/self.nominal_sample_rate_hz}
        self._assert_source()
