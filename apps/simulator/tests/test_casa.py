from pathlib import Path
import numpy as np
from vsora_observation import load_config
from vsora_simulator.sky import casa_sky
from vsora_simulator.visibility import direct_visibility


def test_reference_model_flux_and_extent():
    root=Path(__file__).resolve().parents[3]
    c=load_config(root/'configs/experiments/ideal-point.json');c['source']['model']='casa'
    image=casa_sky(c)
    assert image.shape==(64,64)
    assert image.min()==0
    assert abs(image.sum()-1000)<1e-10
    assert np.count_nonzero(image)>100
    np.testing.assert_allclose(direct_visibility(np.zeros((1,3)),image,16),1000,atol=1e-10)
