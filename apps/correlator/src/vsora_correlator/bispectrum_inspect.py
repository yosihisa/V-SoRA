"""Inspect stored raw U3 values without a noise likelihood or image inference."""
import hashlib
import json
from pathlib import Path

import numpy as np

from vsora_formats.bispectrum import (
    ARRAYS, arrays_for_version,
    load_bispectrum,
    reconstruct_bispectrum,
    validate_bispectrum,
)
from .bispectrum_power import normalize_common_power_bispectrum


def inspect_bispectrum_cell(data, time_index, channel_index):
    """Return finite complex values and availability for one time/RF cell.

    This array-only helper cannot establish source-file identity. A quality mask
    retains the raw value; fewer than three common FFT blocks yields JSON null.
    """
    if not isinstance(data, dict) or not ARRAYS <= set(data) or "metadata" not in data:
        raise ValueError("validated raw arrays and metadata required")
    version=data.get('schema_version',1)
    required=arrays_for_version(version)
    if not required<=set(data) or (version==1 and 'common_station_power_sums' in data):
        raise ValueError('explicit matching raw schema and common power arrays required')
    d, meta = validate_bispectrum({k:data[k] for k in required},data['metadata'],schema_version=version)
    nt, nf = d["edge_sums"].shape[:2]
    for value, size in ((time_index, nt), (channel_index, nf)):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, np.integer))
            or not 0 <= value < size
        ):
            raise ValueError("integer time/channel indices must select an existing raw cell")
    ti, fi = int(time_index), int(channel_index)
    u = reconstruct_bispectrum(d)[ti, fi]
    normalized=None
    if version==2:
        counts=d['common_fft_count'][ti]
        with np.errstate(over='ignore',invalid='ignore'):
            ordinary_selected=np.divide(np.prod(d['edge_sums'][ti,fi:fi+1],axis=-1),
                                        counts[None,:].astype(float)**3,
                                        out=np.zeros((1,len(counts)),complex),where=counts[None,:]>0)
        normalized=normalize_common_power_bispectrum({
            'triangles':d['triangles'],'common_sample_count':counts,
            'common_station_power_sums':d['common_station_power_sums'][ti,fi:fi+1],
            'distinct_sample_bispectrum':u[None,:],
            'ordinary_common_sample_product':ordinary_selected,
            'channel_triangle_usable':d['channel_triangle_usable'][ti,fi:fi+1]})
    rows = []
    for index, tri in enumerate(d["triangles"]):
        m = int(d["common_fft_count"][ti, index])
        available = m >= 3
        usable = bool(d["channel_triangle_usable"][ti, fi, index])
        with np.errstate(over="ignore", invalid="ignore"):
            ordinary = np.prod(d["edge_sums"][ti, fi, index]) / m**3 if m else None
        if ordinary is not None and not np.isfinite(ordinary):
            raise ValueError("ordinary raw product outside finite numerical range")
        value = u[index] if available else None
        state = (
            "insufficient_samples" if not available
            else "usable_raw_value" if usable
            else "masked_raw_value"
        )
        normalized_available=bool(normalized is not None and normalized['u3_available'][0,index])
        ordinary_available=bool(normalized is not None and normalized['ordinary_available'][0,index])
        normalization_state=('missing_common_power_v1' if normalized is None else
                             'insufficient_samples' if m<3 else
                             'zero_common_power' if not normalized['triangle_common_power_positive'][0,index] else
                             'usable_normalized_value' if usable else 'masked_normalized_value')
        rows.append({
            "triangle": tri.tolist(),
            "station_ids": [meta["station_ids"][i] for i in tri],
            "common_fft_count": m,
            "common_station_power_sums":None if normalized is None else d['common_station_power_sums'][ti,fi,index].tolist(),
            "observed_power_normalized_u3_available":normalized_available,
            "observed_power_normalized_ordinary_product_available":ordinary_available,
            "observed_power_normalized_u3_quality_usable":bool(normalized_available and usable),
            "observed_power_normalization_state":normalization_state,
            "observed_power_normalized_u3_real":float(normalized['observed_power_normalized_u3'][0,index].real) if normalized_available else None,
            "observed_power_normalized_u3_imag":float(normalized['observed_power_normalized_u3'][0,index].imag) if normalized_available else None,
            "observed_power_normalized_ordinary_product_real":float(normalized['observed_power_normalized_ordinary_product'][0,index].real) if ordinary_available else None,
            "observed_power_normalized_ordinary_product_imag":float(normalized['observed_power_normalized_ordinary_product'][0,index].imag) if ordinary_available else None,
            "distinct_sample_available": available,
            "channel_triangle_usable": usable,
            "state": state,
            "ordinary_common_sample_product_real": None if ordinary is None else float(ordinary.real),
            "ordinary_common_sample_product_imag": None if ordinary is None else float(ordinary.imag),
            "distinct_sample_bispectrum_real": None if value is None else float(value.real),
            "distinct_sample_bispectrum_imag": None if value is None else float(value.imag),
        })
    return {
        "type": "raw_bispectrum_inspection",
        "raw_schema_version":int(version),
        "observed_power_ratio_supported":version==2,
        "normalized_bispectrum_unit":'dimensionless' if version==2 else None,
        "common_power_sum_unit":meta.get('common_power_sum_unit'),
        "state": "complete",
        "time_index": ti,
        "channel_index": fi,
        "time_s": float(d["times_s"][ti]),
        "time_origin_utc": meta["time_origin_utc"],
        "frequency_hz": float(d["frequencies_hz"][fi]),
        "bispectrum_unit": meta["bispectrum_unit"],
        "nominal_fft_count": int(d["nominal_fft_count"][ti]),
        "triangles": rows,
        "source_visibility_verified": False,
        "noise_covariance_estimated": False,
        "input_sample_independence_verified": False,
        "input_mask_independence_verified": False,
        "closure_phase_unbiased_guarantee": False,
        "production_rml_noise_model_changed": False,
        "real_hardware_validation_performed": False,
        "scope": 'Stored common-FFT raw sums and complex U3 values only. M<3 is unavailable, not zero; masks retain raw values but do not qualify them for inference. No uncertainty, phase confidence, normalized flux, detection probability or image likelihood.' if version==1 else 'Stored common-FFT raw sums and complex U3 values only. M<3 is unavailable, not zero; masks retain raw values but do not qualify them for inference. Version2 ratios use the same triangle-common power sums; version1 values remain null. No uncertainty, phase confidence, normalized source flux, detection probability or image likelihood.',
    }


def _stamp(path):
    s = path.stat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def inspect_bispectrum_file(input, source_visibility, output, channel_index, time_index=0):
    """Check a closed sidecar and its companion, then create a new JSON file."""
    raw, source, out = Path(input), Path(source_visibility), Path(output)
    if out.suffix != ".json":
        raise ValueError("raw bispectrum inspection output must be JSON")
    if out.exists():
        raise FileExistsError("raw bispectrum inspection already exists")
    before = _stamp(raw), _stamp(source)
    with raw.open("rb") as stream:
        raw_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    loaded = load_bispectrum(raw, source)
    q = inspect_bispectrum_cell(loaded, time_index, channel_index)
    if before != (_stamp(raw), _stamp(source)):
        raise ValueError("input changed during raw inspection; use closed archives")
    q.update(
        source_visibility_verified=True,
        raw_bispectrum_sha256=raw_sha,
        source_visibility_sha256=loaded["metadata"]["visibility_sha256"],
    )
    encoded = json.dumps(q, indent=2, allow_nan=False) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as stream:
        stream.write(encoded)
    return q


def main():
    import argparse

    p = argparse.ArgumentParser(
        description="Inspect one raw bispectrum time/RF cell with source visibility identity"
    )
    p.add_argument("--input", required=True)
    p.add_argument("--source-visibility", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--time-index", type=int, default=0)
    p.add_argument("--channel-index", type=int, required=True)
    q = inspect_bispectrum_file(**vars(p.parse_args()))
    print(json.dumps({k: q[k] for k in ("state", "time_index", "channel_index", "frequency_hz")}))


if __name__ == "__main__":
    main()
