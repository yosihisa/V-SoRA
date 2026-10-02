"""Explicit units; fail on unsupported or ambiguous configurations."""
import copy
import json
import math
from pathlib import Path
from datetime import datetime


def keys(value,required,name,optional=()):
    if not isinstance(value,dict) or not set(required)<=set(value) or set(value)-set(required)-set(optional):
        raise ValueError(f'{name}: missing or unsupported keys')


def number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name}: finite numeric value required")
    if positive and value <= 0:
        raise ValueError(f"{name}: must be positive")
    return value


def validate_config(config):
    if not isinstance(config,dict): raise ValueError('config object required')
    c = copy.deepcopy(config)
    if isinstance(c.get('schema_version'),bool) or c.get("schema_version") != 1:
        raise ValueError("schema_version: only version 1 supported")
    required = {"schema_version", "site", "source", "observation", "stations", "image", "noise", "seed"}
    if set(c) != required:
        raise ValueError(f"config keys: missing={required-set(c)}, unknown={set(c)-required}")
    site = c["site"]
    keys(site,('latitude_deg','longitude_deg','height_m'),'site',('description',))
    for k in ("latitude_deg", "longitude_deg", "height_m"):
        number(site[k], k)
    if not -90 <= site["latitude_deg"] <= 90 or not -180 <= site["longitude_deg"] <= 180:
        raise ValueError("site: invalid geographic coordinates")
    source = c["source"]
    keys(source,('frame','ra_deg','dec_deg','model'),'source',('total_flux_jy',))
    if source["frame"] != "icrs":
        raise ValueError("source.frame: only icrs supported")
    number(source["ra_deg"], "ra_deg")
    number(source["dec_deg"], "dec_deg")
    if not 0 <= source["ra_deg"] < 360 or not -90 <= source["dec_deg"] <= 90:
        raise ValueError("source: invalid coordinates")
    if source["model"] not in ("point", "double", "shell", "casa", "unknown"):
        raise ValueError("source.model: unsupported")
    if source['model']!='unknown' or 'total_flux_jy' in source:
        number(source.get("total_flux_jy"), "total_flux_jy", positive=True)
    obs = c["observation"]
    keys(obs,('start_utc','duration_s','integration_s','frequency_hz','bandwidth_hz','elevation_min_deg'),'observation')
    if not isinstance(obs['start_utc'],str): raise ValueError('start_utc string required')
    start = datetime.fromisoformat(obs["start_utc"].replace("Z", "+00:00"))
    if start.utcoffset() is None or start.utcoffset().total_seconds() != 0:
        raise ValueError("start_utc: explicit UTC required")
    for k in ("duration_s", "integration_s", "frequency_hz", "bandwidth_hz"):
        number(obs[k], k, positive=True)
    if obs["integration_s"] > obs["duration_s"]:
        raise ValueError("integration_s exceeds duration_s")
    ntime = obs["duration_s"] / obs["integration_s"]
    if not math.isclose(ntime, round(ntime), rel_tol=0, abs_tol=1e-8):
        raise ValueError("duration_s must be a multiple of integration_s")
    number(obs["elevation_min_deg"], "elevation_min_deg")
    if not 0 <= obs["elevation_min_deg"] < 90:
        raise ValueError("invalid elevation_min_deg")
    ids = set()
    if not isinstance(c['stations'],list) or not 2<=len(c["stations"])<=255:
        raise ValueError("at least two stations required")
    positions = set()
    for s in c["stations"]:
        keys(s,('id','enu_m','sefd_jy'),'station',('diameter_m',))
        if not isinstance(s["id"], str) or not s["id"] or s["id"] in ids:
            raise ValueError("station IDs must be nonempty and unique")
        ids.add(s["id"])
        xyz = s["enu_m"]
        if not isinstance(xyz,list) or len(xyz) != 3:
            raise ValueError("enu_m must have three entries")
        for v in xyz:
            number(v, "enu_m")
        if tuple(xyz) in positions:
            raise ValueError("duplicate station position")
        positions.add(tuple(xyz))
        number(s["sefd_jy"], "sefd_jy", positive=True)
        if 'diameter_m' in s: number(s['diameter_m'],'diameter_m',positive=True)
    image = c["image"]
    keys(image,('pixels','pixel_arcsec'),'image')
    n = image["pixels"]
    if isinstance(n, bool) or not isinstance(n, int) or n < 16 or n > 512 or n % 2:
        raise ValueError("image.pixels: even integer in [16,512] required")
    number(image["pixel_arcsec"], "pixel_arcsec", positive=True)
    keys(c['noise'],('enabled','efficiency'),'noise')
    if c["noise"]["enabled"] not in (True, False) or not isinstance(c["noise"]["enabled"], bool):
        raise ValueError("noise.enabled must be boolean")
    eta = number(c["noise"]["efficiency"], "efficiency", positive=True)
    if eta > 1:
        raise ValueError("efficiency must be <=1")
    if isinstance(c["seed"], bool) or not isinstance(c["seed"], int) or c["seed"] < 0:
        raise ValueError("seed: nonnegative integer required")
    return c


def load_config(path):
    return validate_config(json.loads(Path(path).read_text()))
