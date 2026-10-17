"""Conditional whole-window symmetry from closed common-power raw archives."""
import hashlib
import json
from pathlib import Path

import numpy as np

from vsora_formats.bispectrum import load_bispectrum
from vsora_imaging.window_symmetry import exact_window_sign_flip_test
from vsora_correlator.bispectrum_inspect import inspect_bispectrum_cell, _stamp


def window_symmetry_from_bispectrum(data, channel_index):
    """Use every saved window and triangle, without selection or zero filling.

    A conditional p value requires joint whole-window sign invariance of the
    imaginary normalized features, including any upstream quality selection.
    Neither unique timestamps nor a source SHA establishes that assumption.
    """
    if not isinstance(data, dict) or data.get("schema_version") != 2:
        raise ValueError("version2 common-power raw data required")
    times = np.asarray(data.get("times_s"))
    if times.ndim != 1 or not 1 <= len(times) <= 12:
        raise ValueError("all saved windows must fit the supported range1..12")
    cells = [inspect_bispectrum_cell(data, ti, channel_index) for ti in range(len(times))]
    for cell in cells:
        if not all(row["observed_power_normalized_u3_available"] and
                   row["observed_power_normalized_u3_quality_usable"]
                   for row in cell["triangles"]):
            raise ValueError("every window/triangle needs available, quality-usable U3; no automatic selection")
    first = cells[0]
    vectors = np.array([[row["observed_power_normalized_u3_imag"]
                         for row in cell["triangles"]] for cell in cells])
    result = exact_window_sign_flip_test(vectors)
    return {
        "type": "stored_bispectrum_window_symmetry", "state": "complete",
        "raw_schema_version": 2, "channel_index": int(channel_index),
        "frequency_hz": first["frequency_hz"], "time_origin_utc": first["time_origin_utc"],
        "times_s": times.tolist(), "station_ids": list(data["metadata"]["station_ids"]),
        "triangles": [row["triangle"] for row in first["triangles"]],
        "triangle_station_ids": [row["station_ids"] for row in first["triangles"]],
        "common_fft_count": [[row["common_fft_count"] for row in cell["triangles"]] for cell in cells],
        "imaginary_normalized_u3": vectors.tolist(), "conditional_test": result,
        "nominal_five_percent_resolution_available": result["minimum_two_sided_resolution"] <= .05,
        "all_saved_windows_and_triangles_used": True, "automatic_selection_performed": False,
        "source_visibility_verified": False, "joint_window_sign_invariance_verified": False,
        "window_independence_verified": False, "upstream_selection_invariance_verified": False,
        "constant_within_window_station_gains_verified": False,
        "source_detection_claimed": False, "source_extent_claimed": False,
        "image_confidence_claimed": False, "unknown_lo_estimated": False,
        "production_rml_noise_model_changed": False, "real_hardware_validation_performed": False,
        "scope": "Conditional whole-window sign-flip p value on every saved usable normalized imaginary feature. "
                 "Joint invariance, including upstream selection, is assumed and not established by archive identity. "
                 "No source detection, extent, LO estimate, image likelihood or confidence.",
    }


def inspect_bispectrum_window_file(input, source_visibility, output, channel_index):
    """Verify both closed archives and create one new result JSON."""
    raw, source, out = Path(input), Path(source_visibility), Path(output)
    if out.suffix != ".json":
        raise ValueError("window symmetry output must be JSON")
    if out.exists():
        raise FileExistsError("window symmetry result already exists")
    before = _stamp(raw), _stamp(source)
    with raw.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    data = load_bispectrum(raw, source)
    result = window_symmetry_from_bispectrum(data, channel_index)
    if before != (_stamp(raw), _stamp(source)):
        raise ValueError("input changed during inspection; use closed archives")
    result.update(source_visibility_verified=True, raw_bispectrum_sha256=digest,
                  source_visibility_sha256=data["metadata"]["visibility_sha256"])
    encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as stream:
        stream.write(encoded)
    return result


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True)
    p.add_argument("--source-visibility", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--channel-index", required=True, type=int)
    q = inspect_bispectrum_window_file(**vars(p.parse_args()))
    print(json.dumps({"state": q["state"], "windows": q["conditional_test"]["windows"],
                      "conditional_p_value": q["conditional_test"]["upper_tail_p_value"],
                      "joint_invariance_verified": False}))


if __name__ == "__main__":
    main()
