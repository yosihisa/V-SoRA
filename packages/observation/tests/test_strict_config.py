from pathlib import Path
import pytest
from vsora_observation import load_config,validate_config


@pytest.mark.parametrize('section',['site','source','observation','image','noise'])
def test_unknown_nested_keys_are_rejected(section):
    root=Path(__file__).resolve().parents[3];c=load_config(root/'configs/experiments/ideal-point.json')
    c[section]['misspelled_parameter']=1
    with pytest.raises(ValueError,match='keys'): validate_config(c)


@pytest.mark.parametrize('replacement',[None,[],True])
def test_malformed_root_rejected(replacement):
    with pytest.raises(ValueError): validate_config(replacement)
