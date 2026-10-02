from pathlib import Path
import numpy as np
from vsora_observation import load_config
from vsora_observation.geometry import observation_geometry
from vsora_simulator.visibility import direct_visibility
from vsora_imaging.dirty import dirty_image,point_response
from vsora_imaging.clean import clean


def test_off_center_full_field_clean_uses_exact_w_response():
    root=Path(__file__).resolve().parents[3];c=load_config(root/'configs/experiments/ideal-point.json');g=observation_geometry(c)
    image=np.zeros((64,64));image[34,29]=1000
    v=direct_visibility(g['uvw_lambda'],image,16);w=np.ones(v.shape)
    dirty,psf=dirty_image(g['uvw_lambda'],v,64,16,w)
    r=point_response(g['uvw_lambda'],w,64,16,34,29)
    np.testing.assert_allclose(dirty,1000*r,atol=1e-10)
    result=clean(dirty,psf,threshold=1,response_function=lambda y,x:point_response(g['uvw_lambda'],w,64,16,y,x))
    assert result['converged'] and result['iterations']<100
    assert np.unravel_index(np.argmax(result['model_jy_pixel']),image.shape)==(34,29)
    assert abs(result['model_jy_pixel'].sum()-1000)<1
