"""Create a sanitized numerical reference from the original CDS image.

Only whitelisted WCS/beam fields are retained, never HISTORY or OBSERVER.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from astropy.io import fits

EXPECTED_SHA512 = "0ab1caa9113f0af140ef688d8bea77edf9e6946bd2ebecd8170c5f3a4f8fbc206e3fb0119debb28ef220764324afcae2bfc80428e680a531dbd7391e0e511d41"


def import_reference(source, destination):
    digest = hashlib.sha512(Path(source).read_bytes()).hexdigest()
    if digest != EXPECTED_SHA512:
        raise ValueError("Source checksum differs from the documented CDS reference")
    data, h = fits.getdata(source, header=True)
    if data.ndim != 2 or h["BUNIT"].strip().lower() != "jy/beam":
        raise ValueError("2D Jy/beam image required")
    beam_deg2 = np.pi * h["BMAJ"] * h["BMIN"] / (4 * np.log(2))
    pixel_deg2 = abs(h["CDELT1"] * h["CDELT2"])
    converted = np.asarray(data, dtype=np.float64) * pixel_deg2 / beam_deg2
    if not np.isfinite(converted).all():
        raise ValueError("nonfinite reference pixels")
    header = fits.Header()
    for k in ("OBJECT", "BMAJ", "BMIN", "BPA", "EQUINOX", "RADESYS", "CTYPE1", "CTYPE2",
              "CRVAL1", "CRVAL2", "CDELT1", "CDELT2", "CRPIX1", "CRPIX2", "CUNIT1", "CUNIT2",
              "PC01_01", "PC01_02", "PC02_01", "PC02_02", "LONPOLE", "LATPOLE"):
        if k in h:
            # Normalize historical zero-padded PC keywords to FITS-WCS form.
            normalized = {"PC01_01":"PC1_1", "PC01_02":"PC1_2", "PC02_01":"PC2_1", "PC02_02":"PC2_2"}.get(k,k)
            header[normalized] = h[k]
    header["BUNIT"] = "Jy/pixel"
    header["ORIGIN"] = "V-SoRA"
    header["SRCDOI"] = "10.1051/0004-6361/201732411"
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fits.writeto(dest, converted.astype("float32"), header, overwrite=False, checksum=True)
    metadata = {
        "source_url": "https://cdsarc.cds.unistra.fr/ftp/J/A+A/612/A110/fits/VLA_lband_2017.fits",
        "source_sha512": digest, "derived_sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
        "paper_doi": "10.1051/0004-6361/201732411", "catalogue": "J/A+A/612/A110",
        "observed_spectral_windows_mhz": [1378, 1750], "single_reference_frequency_hz": None,
        "observed_epoch": "2017-08-13", "shape": list(data.shape),
        "beam_arcsec": [h["BMAJ"] * 3600, h["BMIN"] * 3600], "pixel_arcsec": 2.0,
        "conversion": "Jy/pixel = Jy/beam * pixel_area / (pi*BMAJ*BMIN/(4*ln(2)))",
        "integrated_flux_jy": float(converted.sum()),
        "negative_pixel_count": int((converted < 0).sum()),
        "policy": "Original observer names, HISTORY, host paths and processing logs omitted; data unchanged except units.",
        "use": "Morphology template; total flux at 1.42 GHz is a separate simulation assumption."
    }
    dest.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("destination")
    a = p.parse_args()
    print(json.dumps(import_reference(a.source, a.destination), indent=2))
