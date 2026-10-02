"""Geocentric geometric model for simulation, not a VLBI propagation model."""
import warnings
import numpy as np
import astropy.units as u
from astropy.coordinates import EarthLocation, SkyCoord, GCRS, AltAz
from astropy.time import Time
from astropy.utils import iers

C_M_S = 299792458.0
ARCSEC_RAD = np.pi / (180 * 3600)


def tangent_grid(pixels, pixel_arcsec):
    axis = (np.arange(pixels) - pixels // 2) * pixel_arcsec * ARCSEC_RAD
    l, m = np.meshgrid(axis, axis)
    if np.any(l*l + m*m >= 1):
        raise ValueError("field extends beyond tangent hemisphere")
    return l, m


def enu_to_ecef(enu, latitude_deg, longitude_deg):
    lat, lon = np.deg2rad([latitude_deg, longitude_deg])
    rotation = np.array([
        [-np.sin(lon), -np.sin(lat)*np.cos(lon), np.cos(lat)*np.cos(lon)],
        [np.cos(lon), -np.sin(lat)*np.sin(lon), np.cos(lat)*np.sin(lon)],
        [0, np.cos(lat), np.sin(lat)]
    ])
    return np.asarray(enu) @ rotation.T


def uvw_from_vectors(baselines, ra_rad, dec_rad):
    """Baselines (...,3) and same-frame sky coordinates, output in input units."""
    ra, dec = np.broadcast_arrays(ra_rad, dec_rad)
    east = np.stack([-np.sin(ra), np.cos(ra), np.zeros_like(ra)], axis=-1)
    north = np.stack([-np.sin(dec)*np.cos(ra), -np.sin(dec)*np.sin(ra), np.cos(dec)], axis=-1)
    toward = np.stack([np.cos(dec)*np.cos(ra), np.cos(dec)*np.sin(ra), np.sin(dec)], axis=-1)
    basis = np.stack([east, north, toward], axis=-2)
    return np.einsum("...ij,...j->...i", basis, baselines)


def observation_geometry(config):
    """Midpoint geometry. Integration smearing is not modeled in this stage."""
    obs, site, source = config["observation"], config["site"], config["source"]
    offsets = (np.arange(round(obs["duration_s"]/obs["integration_s"])) + .5) * obs["integration_s"]
    times = Time(obs["start_utc"], scale="utc") + offsets * u.s
    location = EarthLocation.from_geodetic(site["longitude_deg"] * u.deg,
                                          site["latitude_deg"] * u.deg, site["height_m"] * u.m)
    origin = np.array([v.to_value(u.m) for v in location.geocentric])
    enu = np.array([s["enu_m"] for s in config["stations"]])
    ecef = origin + enu_to_ecef(enu, site["latitude_deg"], site["longitude_deg"])
    target = SkyCoord(source["ra_deg"]*u.deg, source["dec_deg"]*u.deg, frame="icrs")
    # Explicitly avoid network access. The bundled table provenance and warnings
    # must be recorded; predicted/stale EOP must not be called measured EOP.
    with iers.conf.set_temp("auto_download", False), iers.conf.set_temp("auto_max_age", None):
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            celestial = target.transform_to(GCRS(obstime=times))
            elevation = target.transform_to(AltAz(obstime=times, location=location, pressure=0*u.hPa)).alt.deg
            positions = np.stack([
                EarthLocation.from_geocentric(*xyz, unit=u.m).get_gcrs_posvel(times)[0].xyz.to_value(u.m).T
                for xyz in ecef
            ], axis=1)
            table = iers.IERS_Auto.open()
            _, _, status = table.pm_xy(times, return_status=True)
    pairs = np.array([(i, j) for i in range(len(enu)) for j in range(i+1, len(enu))])
    b = positions[:, pairs[:,1], :] - positions[:, pairs[:,0], :]
    uvw_m = uvw_from_vectors(b, celestial.ra.rad[:,None], celestial.dec.rad[:,None])
    valid = elevation >= obs["elevation_min_deg"]
    if not valid.any():
        raise ValueError("source below elevation limit throughout observation")
    warnings_text = sorted({str(w.message) for w in captured})
    return {
        "uvw_lambda": uvw_m[valid] * obs["frequency_hz"] / C_M_S,
        "pairs": pairs, "times_mjd": times.mjd[valid], "elevation_deg": elevation[valid],
        "station_ecef_m": ecef,
        "model": "Astropy geocentric GCRS; no atmosphere, ionosphere or antenna propagation delays",
        "eop_status": sorted(set(int(v) for v in status)),
        "eop_warnings": warnings_text,
        "dropped_time_count": int((~valid).sum())
    }
