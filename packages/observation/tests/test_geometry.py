import numpy as np
from vsora_observation.geometry import uvw_from_vectors, enu_to_ecef, observation_geometry, C_M_S
from vsora_observation import load_config
from pathlib import Path


def test_axes_and_baseline_reversal():
    b=np.array([[1.,2.,3.]])
    result=uvw_from_vectors(b,0.,0.)
    np.testing.assert_allclose(result,[[2,3,1]])
    np.testing.assert_allclose(uvw_from_vectors(-b,0.,0.),-result)


def test_rotation_preserves_norm():
    rng=np.random.default_rng(1)
    b=rng.normal(size=(50,3))
    v=uvw_from_vectors(b,rng.uniform(0,6,size=50),rng.uniform(-1,1,size=50))
    np.testing.assert_allclose(np.linalg.norm(v,axis=-1),np.linalg.norm(b,axis=-1),atol=1e-14)
    e=enu_to_ecef(b,35,135)
    np.testing.assert_allclose(np.linalg.norm(e,axis=-1),np.linalg.norm(b,axis=-1),atol=1e-14)


def test_observation_norm_time_and_elevation():
    c=load_config(Path(__file__).resolve().parents[3]/'configs/experiments/ideal-point.json')
    g=observation_geometry(c)
    pos=np.array([s['enu_m'] for s in c['stations']])
    expected=np.linalg.norm(pos[g['pairs'][:,1]]-pos[g['pairs'][:,0]],axis=1)
    actual=np.linalg.norm(g['uvw_lambda'],axis=-1)*C_M_S/c['observation']['frequency_hz']
    np.testing.assert_allclose(actual,np.broadcast_to(expected,actual.shape),atol=2e-8)
    assert (g['elevation_deg']>=15).all()
    np.testing.assert_allclose(np.diff(g['times_mjd'])*86400,60,atol=2e-6)
