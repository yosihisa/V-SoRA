"""Explicit finite LBA band queries on a caller-supplied affine clock.

This API does not estimate a clock, authenticate RF metadata or run a session.
The source remains in DiFX code units, including its finite filter response.
"""
from copy import deepcopy
import datetime
import hashlib
import json
import math
import re

import numpy as np
from vsora_formats.lba_band import LBAComplexBandView
from .clock import interpolate_samples


_KEYS = {'schema_version', 'station_id', 'time_origin_utc', 'input_start_offset_s',
         'actual_sample_rate_hz', 'rf_band_edge_hz', 'output_center_frequency_hz',
         'phase_offset_rad', 'clock_provenance', 'rf_provenance'}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


class LBAClockedBandView:
    """Interpolate a live band view and change its declared RF phase origin.

    Provenance labels describe caller claims. They do not verify a measurement.
    Closed inputs and trusted Python are assumed; the source guard limitations
    (including all-stat-preserving raw changes) still apply.
    """
    voltage_unit = 'DiFX_s16_code_complex_band'

    def __init__(self, source, *, model, invalid_source_ranges=()):
        if not isinstance(source, LBAComplexBandView):
            raise TypeError('live LBAComplexBandView required')
        if not isinstance(model, dict) or set(model) != _KEYS:
            raise ValueError('explicit complete clock/RF model required')
        if type(model['schema_version']) is not int or model['schema_version'] != 1:
            raise ValueError('integer model schema_version 1 required')
        if (type(model['station_id']) is not str
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,31}', model['station_id'])):
            raise ValueError('explicit station identifier required')
        epoch = model['time_origin_utc']
        if type(epoch) is not str or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z', epoch):
            raise ValueError('UTC-Z model epoch with at most nine fractional digits required')
        datetime.datetime.fromisoformat(epoch.replace('Z', '+00:00'))
        for key in ('clock_provenance', 'rf_provenance'):
            if type(model[key]) is not str or model[key] not in ('supplied_model', 'estimated', 'measured'):
                raise ValueError('explicit caller-declared clock/RF provenance required')
        numeric = ('input_start_offset_s', 'actual_sample_rate_hz', 'rf_band_edge_hz',
                   'output_center_frequency_hz', 'phase_offset_rad')
        if not all(_finite(model[k]) for k in numeric):
            raise ValueError('finite numeric clock/RF values required; unknown values forbidden')
        rate = model['actual_sample_rate_hz']
        if (rate <= 0 or abs(rate/source.nominal_sample_rate_hz-1) > .001
                or abs(model['input_start_offset_s']) > 3
                or min(model['rf_band_edge_hz'], model['output_center_frequency_hz']) <= 0):
            raise ValueError('clock rate, local offset or RF model outside limited reference range')
        delta = (model['rf_band_edge_hz']-model['output_center_frequency_hz'])+rate/4
        if abs(delta) > rate/16:
            raise ValueError('RF center shift exceeds the fixed digital guard')
        if not isinstance(invalid_source_ranges, (tuple, list)):
            raise ValueError('sorted original-sample invalid intervals required')
        ranges = []
        previous = 0
        for interval in invalid_source_ranges:
            if (not isinstance(interval, (tuple, list)) or len(interval) != 2
                    or any(type(n) is not int for n in interval)):
                raise ValueError('integer half-open invalid interval required')
            left, right = interval
            if not previous <= left < right <= source.sample_count:
                raise ValueError('invalid intervals must be ordered, disjoint and inside the source')
            ranges.append((left, right)); previous = right
        self._source = source
        self._model = deepcopy(model)
        self._ranges = tuple(ranges)
        self._context = _canonical([self._model, self._ranges])
        self._identity = source.processing_identity
        self._identity_json = _canonical(self._identity)
        self._n0 = 2*self._identity['source_fragment_identity']['original_payload_offset_bytes']
        self._delta = delta
        # Reduce the constant before combining it with the small local-time term.
        self._constant = math.remainder((self._n0 % 4)/4
            - math.remainder(rate*model['input_start_offset_s']/4, 1)
            + math.remainder(model['phase_offset_rad'], math.tau)/math.tau, 1)
        self._guard()

    def _guard(self):
        if (type(self.voltage_unit) is not str or self.voltage_unit != 'DiFX_s16_code_complex_band'
                or _canonical([self._model, self._ranges]) != self._context
                or _canonical(self._source.processing_identity) != self._identity_json):
            raise ValueError('clock model or live source processing identity changed')

    @property
    def processing_identity(self):
        self._guard()
        return deepcopy({'source_processing_identity':self._identity, 'model':self._model,
            'declared_invalid_original_sample_ranges':self._ranges,
            'model_and_invalid_ranges_sha256':hashlib.sha256(self._context.encode()).hexdigest(),
            'interpolation':'existing radius32 normalized cosine-windowed sinc',
            'additional_causal_filter':False, 'sample_coordinate_rebased':False,
            'phase_cycles':'((E-F0)+R/4)*t-R*a/4+(N0 mod4)/4+phase_offset_rad/(2*pi)',
            'phase_convention':'USB positive component RF-edge oscillator anchored at model epoch',
            'voltage_unit':self.voltage_unit, 'caller_provenance_verified':False,
            'source_nominal_epoch_used_as_actual_clock':False,
            'clock_or_LO_estimated_by_this_API':False,
            'invalid_ranges_scope':'caller declaration; no gap or RFI detection',
            'general_antialias_or_ideal_analytic_signal':False})

    def query(self, query_times_s):
        if isinstance(query_times_s, (tuple, list)) and any(isinstance(x, (bool, np.bool_)) for x in query_times_s):
            raise ValueError('boolean query seconds forbidden')
        times = np.asarray(query_times_s)
        if (times.ndim != 1 or not 1 <= len(times) <= 2048 or times.dtype.kind not in 'iuf'
                or not np.isfinite(times).all()
                or np.any(abs(times) > 3)):
            raise ValueError('1..2048 increasing finite local query seconds within three seconds required')
        times = np.array(times, dtype=float, copy=True)
        if np.any(np.diff(times) <= 0):
            raise ValueError('increasing query times required')
        self._guard()
        positions = (times-self._model['input_start_offset_s'])*self._model['actual_sample_rate_hz']
        lo = math.floor(float(positions.min()))-32
        hi = math.floor(float(positions.max()))+34
        if (lo < self._source.first_valid_sample_index or hi > self._source.stop_valid_sample_index
                or hi-lo > 16384):
            raise ValueError('query needs bounded complete FIR and interpolation support')
        values = self._source.read_complex_samples(lo, hi-lo)
        centers = np.arange(lo, hi)
        valid = np.ones(hi-lo, dtype=bool)
        for left, right in self._ranges:
            valid &= ~((centers < right+64) & (centers >= left-64))
        result, good = interpolate_samples(values, positions-lo, valid=valid, radius=32)
        cycles = np.remainder(self._delta*times+self._constant, 1)
        # Scalar libm/complex arithmetic gives the same rounding for one point
        # and for a split batch, rather than length-dependent SIMD paths.
        result = np.array([complex(z)*complex(math.cos(math.tau*c), math.sin(math.tau*c))
                           for z,c in zip(result,cycles)])
        self._guard()
        return {'complex_samples':result, 'valid':good, 'source_positions':positions,
                'query_times_s':times, 'complex_input_start':lo, 'complex_input_count':hi-lo,
                'processing_identity':self.processing_identity}
