import hashlib
import json
from pathlib import Path
import numpy as np
from astropy.io import fits

ROOT = Path(__file__).resolve().parents[3]


def test_reference_integrity_units_and_privacy():
    p = ROOT / "data/reference/casa-template-jy-pixel.fits"
    meta = json.loads(p.with_suffix(".json").read_text())
    assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["derived_sha256"]
    with fits.open(p, checksum=True) as hdus:
        hdu = hdus[0]
        assert hdu.verify_checksum() == 1
        assert hdu.verify_datasum() == 1
        assert hdu.header["BUNIT"] == "Jy/pixel"
        assert hdu.data.shape == (512, 512)
        assert np.isfinite(hdu.data).all()
        assert abs(hdu.data.sum(dtype=np.float64)-meta["integrated_flux_jy"]) < 1e-4
        assert not any(k in hdu.header for k in ["OBSERVER", "HISTORY", "AUTHOR"])
