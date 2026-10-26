"""粗格子と参照格子で同じ物理座標とClosureを表すことを確認する。"""
from itertools import combinations
import numpy as np
import pytest
from workflows.image_grid_validation import embed_on_32
from vsora_simulator.visibility import direct_visibility
from vsora_imaging.objective_evaluation import evaluate_closure_image


def image(pixels):
    q=np.ones((pixels,pixels));q[pixels//2,pixels//2]=8.;q/=q.sum();return q


@pytest.mark.parametrize('pixels',[8,16,32])
def test_flux_and_original_are_preserved(pixels):
    q=image(pixels);before=q.copy();embedded=embed_on_32(q)
    assert embedded.sum()==pytest.approx(q.sum(),abs=1e-15)
    embedded[:]=0;np.testing.assert_array_equal(q,before)


@pytest.mark.parametrize('pixels',[8,16])
def test_model_visibility_matches_same_physical_point_positions(pixels):
    uv=np.random.default_rng(119).uniform(-1200,1200,(2,3,6,3));q=image(pixels)
    np.testing.assert_allclose(direct_visibility(uv,q,512./pixels),direct_visibility(uv,embed_on_32(q),16.),rtol=1e-12,atol=1e-14)


@pytest.mark.parametrize('pixels',[8,16])
def test_closure_data_loss_and_centroid_match_embedding(pixels):
    pairs=np.array(list(combinations(range(4),2)));uv=np.random.default_rng(19).uniform(-100,100,(1,1,6,3))
    vis=np.ones((1,1,6),complex);weights=np.full(vis.shape,1e3);q=image(pixels)
    a=evaluate_closure_image(uv,vis,weights,pairs,q,pixel_arcsec=512./pixels)
    b=evaluate_closure_image(uv,vis,weights,pairs,embed_on_32(q),pixel_arcsec=16.)
    for key in ('data_loss','centroid_loss'):assert a['metrics'][key]==pytest.approx(b['metrics'][key],rel=1e-9,abs=1e-11)


@pytest.mark.parametrize('q',[np.zeros((8,8)),np.ones((8,8),complex),np.ones((8,9)),np.full((8,8),np.nan)])
def test_invalid_grid(q):
    with pytest.raises(ValueError):embed_on_32(q)
