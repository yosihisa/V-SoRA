import numpy as np
from vsora_imaging.__main__ import compare_models


def test_metrics_do_not_hide_flux_error():
    image=np.zeros((32,32));image[16,16]=10
    m,_,_=compare_models(image,image.copy(),16)
    assert m['nrmse']<1e-12 and abs(m['correlation']-1)<1e-12
    m,_,_=compare_models(image,image*.5,16)
    assert abs(m['nrmse']-.5)<1e-12
    assert m['model_flux_ratio']==.5
