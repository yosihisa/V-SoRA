from pathlib import Path
import numpy as np
from vsora_observation import load_config
from vsora_observation.geometry import observation_geometry
from vsora_formats.fitsidi import write_fitsidi
from vsora_imaging.__main__ import image_visibility


def test_idi_to_image_preserves_point_amplitude(tmp_path):
    root=Path(__file__).resolve().parents[2]
    c=load_config(root/'configs/experiments/ideal-point.json')
    g=observation_geometry(c);shape=g['uvw_lambda'].shape[:-1]
    write_fitsidi(tmp_path/'visibility.fits',g,np.full(shape,1000+0j),np.full(shape,.0043333),c)
    result=image_visibility(tmp_path/'visibility.fits',tmp_path/'imaging')
    assert result['converged']
    assert abs(result['image_peak_jy']/1000-1)<.002
