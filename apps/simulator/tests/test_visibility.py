import numpy as np
from vsora_simulator.visibility import direct_visibility, thermal_noise
from vsora_observation.geometry import ARCSEC_RAD


def test_offcenter_point_against_scalar_analytic_solution():
    rng=np.random.default_rng(3)
    uvw=rng.uniform(-3000,3000,size=(30,3))
    image=np.zeros((32,32));image[18,13]=12
    l,m=-3*10*ARCSEC_RAD,2*10*ARCSEC_RAD
    expected=np.array([12*np.exp(-2j*np.pi*(u*l+v*m+w*(np.sqrt(1-l*l-m*m)-1))) for u,v,w in uvw])
    np.testing.assert_allclose(direct_visibility(uvw,image,10),expected,atol=1e-12)
    np.testing.assert_allclose(direct_visibility(-uvw,image,10),expected.conj(),atol=1e-12)


def test_zero_baseline_flux_and_center_source():
    image=np.zeros((32,32));image[16,16]=17
    assert direct_visibility(np.zeros((1,3)),image,10)[0]==17
    np.testing.assert_allclose(direct_visibility(np.ones((5,3))*1000,image,10),17)


def test_noise_statistics_and_seed():
    c={'stations':[{'sefd_jy':10000},{'sefd_jy':40000}],
       'observation':{'bandwidth_hz':2e6,'integration_s':1},'noise':{'efficiency':1},'seed':4}
    n,s=thermal_noise(c,np.array([[0,1]]),(100000,1))
    assert s[0,0]==10
    assert abs(n.real.std()/10-1)<.01
    assert abs(n.imag.std()/10-1)<.01
    np.testing.assert_array_equal(n,thermal_noise(c,np.array([[0,1]]),(100000,1))[0])
