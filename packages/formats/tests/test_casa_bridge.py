import json
from pathlib import Path
import numpy as np
import pytest
from astropy.io import fits
from vsora_formats.casa import prepare_casa_input


def fixture():
    return Path(__file__).resolve().parents[3]/'validation/runs/stage013/point-8channel.fits'


def test_bridge_uses_actual_fits_weights_and_flags(tmp_path):
    target=tmp_path/'bridge.npz';r=prepare_casa_input(fixture(),target)
    assert r['channels']==8 and r['rows']==60 and r['flagged_channel_rows']==1
    with np.load(target,allow_pickle=False) as b, fits.open(fixture()) as h:
        packed=h['UV_DATA'].data['FLUX'].reshape(60,8,3)
        np.testing.assert_array_equal(b['weights'],packed[:,:,2].T)
        np.testing.assert_array_equal(b['visibilities'],(packed[:,:,0]-1j*packed[:,:,1]).T)
    with pytest.raises(FileExistsError): prepare_casa_input(fixture(),target)


def test_old_profile_is_rejected(tmp_path):
    p=tmp_path/'old.fits'
    with fits.open(fixture()) as h:
        m=json.loads(h['VSORA_META'].data['JSON'][0]);m['schema_version']=1
        m['visibility_storage']='unconjugated'
        h['VSORA_META'].data['JSON'][0]=json.dumps(m)
        h.writeto(p,checksum=True)
    with pytest.raises(ValueError,match='re-export'): prepare_casa_input(p,tmp_path/'b.npz')


def test_missing_checksums_rejected(tmp_path):
    p=tmp_path/'unchecked.fits'
    with fits.open(fixture()) as h:
        for ext in h:
            for key in ['CHECKSUM','DATASUM']:
                if key in ext.header: del ext.header[key]
        h.writeto(p)
    with pytest.raises(ValueError,match='checksums'): prepare_casa_input(p,tmp_path/'b.npz')
