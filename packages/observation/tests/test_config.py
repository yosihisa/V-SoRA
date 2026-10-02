import copy
import json
from pathlib import Path
import pytest
from vsora_observation import load_config, validate_config

ROOT = Path(__file__).resolve().parents[3]


def example():
    return json.loads((ROOT / "configs/experiments/ideal-point.json").read_text())


def test_example_and_independent_copy():
    c = example()
    checked = validate_config(c)
    checked["stations"][0]["enu_m"][0] += 1
    assert checked != c
    assert load_config(ROOT / "configs/experiments/ideal-point.json") == c


@pytest.mark.parametrize("section,key,value", [
    ("observation", "frequency_hz", -1), ("observation", "duration_s", float("nan")),
    ("observation", "start_utc", "2026-10-02T00:00:00"),
    ("observation", "duration_s", 601), ("source", "frame", "fk5"),
    ("source", "dec_deg", 91), ("image", "pixels", 31), ("noise", "efficiency", 2),
])
def test_invalid(section, key, value):
    c = example()
    c[section][key] = value
    with pytest.raises(ValueError):
        validate_config(c)


def test_duplicate_station():
    c = example()
    c["stations"][1]["id"] = c["stations"][0]["id"]
    with pytest.raises(ValueError):
        validate_config(c)


def test_unknown_top_level():
    c = example()
    c["unknown"] = 1
    with pytest.raises(ValueError):
        validate_config(c)
