import numpy as np
from pathlib import Path
from astropy.io import fits
from vsora_observation import load_config
from vsora_observation.geometry import observation_geometry
from vsora_formats.fitsidi import write_fitsidi,read_fitsidi


def test_multichannel_matrix_axis_units_flags_and_roundtrip(tmp_path):
    root=Path(__file__).resolve().parents[3];c=load_config(root/'configs/experiments/ideal-point.json');g=observation_geometry(c)
    frequencies=1.42e9+np.arange(-4,4)*256000;shape=(len(g['times_mjd']),8,len(g['pairs']))
    rng=np.random.default_rng(5);v=rng.normal(size=shape)+1j*rng.normal(size=shape)
    w=rng.uniform(.1,2,shape);w[0,0,0]=0;p=tmp_path/'spectral.fits'
    write_fitsidi(p,g,v,w,c,frequencies_hz=frequencies)
    d=read_fitsidi(p)
    np.testing.assert_allclose(d['vis_jy'],v,rtol=1e-6,atol=1e-7)
    np.testing.assert_allclose(d['weights'],w,rtol=1e-6)
    np.testing.assert_allclose(d['uvw_lambda'],g['uvw_lambda'][:,None,:,:]*(frequencies[None,:,None,None]/1.42e9),atol=1e-12)
    np.testing.assert_array_equal(d['frequencies_hz'],frequencies)
    with fits.open(p) as f:
        f.verify('exception');assert all(h.verify_checksum()==1 for h in f)
        uv=f['UV_DATA'];matrix=uv.data['FLUX'].reshape(shape[0],shape[-1],8,3)
        assert uv.header['NO_CHAN']==8 and uv.header['CHAN_BW']==256000
        np.testing.assert_allclose(matrix[...,0]+1j*matrix[...,1],v.conj().transpose(0,2,1),atol=1e-7)
        assert matrix[0,0,0,2]==0
