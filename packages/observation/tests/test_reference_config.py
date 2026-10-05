from pathlib import Path
import hashlib,json
import pytest
from vsora_observation.reference import reference_path


def test_bundled_configuration_bytes_match_frozen_experiment_fixture():
    asset=reference_path('known-array-scale-config.json')
    fixture=Path(__file__).resolve().parents[3]/'configs/experiments/ideal-point.json'
    assert asset.read_bytes()==fixture.read_bytes()
    assert json.loads(asset.read_text())['site']['description'].startswith('Assumed public synthetic site')
    assert len(hashlib.sha256(asset.read_bytes()).hexdigest())==64


def test_config_asset_does_not_allow_other_paths():
    with pytest.raises(ValueError):reference_path('../configs/experiments/ideal-point.json')
