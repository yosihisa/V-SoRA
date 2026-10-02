from pathlib import Path
import numpy as np
import pytest
from astropy.io import fits
from astropy.coordinates import SkyCoord,FK5
from astropy.time import Time
import astropy.units as u
from vsora_observation import load_config
from vsora_observation.geometry import observation_geometry
from vsora_formats.fitsidi import write_fitsidi,read_fitsidi


def test_idi_roundtrip_and_independent_conventions(tmp_path):
    root=Path(__file__).resolve().parents[3]
    c=load_config(root/'configs/experiments/ideal-point.json');g=observation_geometry(c)
    rng=np.random.default_rng(9);shape=g['uvw_lambda'].shape[:-1]
    v=rng.normal(size=shape)+1j*rng.normal(size=shape);w=np.ones(shape)*.123;w[0,0]=0
    p=tmp_path/'vis.fits';write_fitsidi(p,g,v,w,c)
    data=read_fitsidi(p)
    np.testing.assert_allclose(data['vis_jy'],v,rtol=2e-7,atol=1e-7)
    np.testing.assert_allclose(data['uvw_lambda'],g['uvw_lambda'],atol=1e-12)
    np.testing.assert_allclose(data['time_mjd'],g['times_mjd'],atol=3e-10,rtol=0)
    np.testing.assert_allclose(data['weights'],w,rtol=1e-7)
    with fits.open(p) as hdus:
        hdus.verify('exception')
        assert all(h.verify_checksum()==1 for h in hdus)
        uv=hdus['UV_DATA'];ag=hdus['ARRAY_GEOMETRY']
        assert uv.header['WEIGHTYP']=='NORMAL'
        assert uv.header['STK_1']==-5 and uv.header['NMATRIX']==1
        # Independent check: the standard stores antenna1-antenna2 in seconds.
        np.testing.assert_allclose(uv.data['UU'],-g['uvw_lambda'][...,0].ravel()/1.42e9,atol=1e-15)
        assert uv.data['BASELINE'][0]==258
        flux=uv.data['FLUX'].reshape(-1,3)
        np.testing.assert_allclose(flux[:,0]+1j*flux[:,1],v.conj().ravel(),rtol=2e-7,atol=1e-7)
        decoded=Time(uv.data['DATE'],uv.data['TIME'],format='jd',scale='utc')
        expected=Time(np.repeat(g['times_mjd'],6),format='mjd',scale='utc')
        assert np.max(abs((decoded-expected).to_value(u.s)))<1e-6
        assert hdus['SOURCE'].data['EQUINOX'][0]=='J2000'
        xyz=ag.data['STABXYZ']+np.array([ag.header[k] for k in ['ARRAYX','ARRAYY','ARRAYZ']])
        np.testing.assert_allclose(xyz,g['station_ecef_m'],atol=1e-9)


def test_float32_overflow_is_rejected_before_writing(tmp_path):
    root=Path(__file__).resolve().parents[3]
    c=load_config(root/'configs/experiments/ideal-point.json');g=observation_geometry(c)
    shape=g['uvw_lambda'].shape[:-1];path=tmp_path/'overflow.fits'
    with pytest.raises(ValueError,match='float32'):
        write_fitsidi(path,g,np.ones(shape)*1e40,np.ones(shape),c)
    assert not path.exists()
