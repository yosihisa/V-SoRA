from pathlib import Path
import numpy as np
import pytest
from astropy.io import fits
from vsora_observation import load_config
from vsora_simulator.__main__ import simulate
from vsora_imaging.__main__ import image_visibility
from vsora_formats.visibility import load_visibility


def test_point_end_to_end(tmp_path):
    root=Path(__file__).resolve().parents[2]
    config=load_config(root/'configs/experiments/ideal-point.json')
    path=simulate(config,tmp_path/'sim')
    v=load_visibility(path)
    np.testing.assert_allclose(v['vis_jy'],1000,atol=1e-9)
    report=image_visibility(path,tmp_path/'image')
    assert report['converged']
    assert abs(report['model_flux_jy']/1000-1)<.002
    image=fits.getdata(tmp_path/'image/restored.fits')
    assert np.unravel_index(image.argmax(),image.shape)==(32,32)
    assert abs(image.max()/1000-1)<.002
    with pytest.raises(FileExistsError): simulate(config,tmp_path/'sim')
