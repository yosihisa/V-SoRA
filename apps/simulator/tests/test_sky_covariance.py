from itertools import combinations
import numpy as np
import pytest
from vsora_simulator.sky_covariance import sky_station_covariance
from vsora_simulator.visibility import direct_visibility


def inputs():
    rng=np.random.default_rng(76)
    return rng.normal(size=(4,3))*1000,rng.uniform(size=(8,8)),16.,np.array([100.,120.,80.,50.])


def test_known_gram_matches_direct_visibility_power_and_psd():
    coords,sky,pixel,sefd=inputs();before=[v.copy() for v in (coords,sky,sefd)]
    q=sky_station_covariance(coords,sky,pixel,sefd);s=q['station_covariance_jy']
    for i,j in combinations(range(4),2):
        v=direct_visibility(coords[j]-coords[i],sky,pixel)
        np.testing.assert_allclose(s[i,j],v,rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(s.diagonal(),sky.sum()+sefd,rtol=1e-13)
    np.testing.assert_allclose(q['normalized_station_covariance'].diagonal(),1.,atol=1e-15)
    assert np.linalg.eigvalsh(s).min()>0
    for old,new in zip(before,(coords,sky,sefd)):np.testing.assert_array_equal(old,new)
    assert not q['observed_power_normalization_performed'] and q['target_source_power_added_to_receiver_background']


def test_point_zero_sky_and_coordinate_translation():
    coords,sky,pixel,sefd=inputs();sky[:]=0
    q=sky_station_covariance(coords,sky,pixel,sefd)
    np.testing.assert_array_equal(q['normalized_station_covariance'],np.eye(4))
    sky[4,4]=1000.;q=sky_station_covariance(coords,sky,pixel,sefd)
    np.testing.assert_allclose(q['station_covariance_jy'],1000*np.ones((4,4))+np.diag(sefd),atol=1e-12)
    translated=sky_station_covariance(coords+[100,-50,20],sky,pixel,sefd)
    np.testing.assert_allclose(q['station_covariance_jy'],translated['station_covariance_jy'],rtol=1e-13)


@pytest.mark.parametrize('coords',[np.zeros((2,3)),np.zeros((9,3)),np.zeros((4,2)),np.full((4,3),np.nan),np.ones((4,3),complex),np.ma.array(np.zeros((4,3)),mask=False)])
def test_invalid_coordinates(coords):
    _,sky,pixel,sefd=inputs()
    with pytest.raises(ValueError):sky_station_covariance(coords,sky,pixel,sefd)


@pytest.mark.parametrize('sky',[np.ones((1,1)),np.ones((4,3)),np.ones((129,129)),np.ones((4,4),complex),-np.ones((4,4)),np.full((4,4),np.inf),np.ma.array(np.ones((4,4)),mask=False)])
def test_invalid_sky(sky):
    coords,_,pixel,sefd=inputs()
    with pytest.raises(ValueError):sky_station_covariance(coords,sky,pixel,sefd)


@pytest.mark.parametrize('noise',[[1,2,3],[1,2,3,0],[1,2,3,np.inf],np.ones(4,complex),np.ma.array(np.ones(4),mask=False)])
def test_invalid_receiver_power(noise):
    coords,sky,pixel,_=inputs()
    with pytest.raises(ValueError):sky_station_covariance(coords,sky,pixel,noise)


@pytest.mark.parametrize('pixel',[True,0,-1,np.nan,1e10])
def test_invalid_pixel_size(pixel):
    coords,sky,_,sefd=inputs()
    with pytest.raises(ValueError):sky_station_covariance(coords,sky,pixel,sefd)


def test_overflow_rejected():
    coords,_,pixel,sefd=inputs()
    with pytest.raises(ValueError):sky_station_covariance(coords,np.full((8,8),1e308),pixel,sefd)
