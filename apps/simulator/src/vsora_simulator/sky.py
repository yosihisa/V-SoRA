"""Discrete sky in Jy/pixel on an east/north direction-cosine grid."""
import numpy as np
from vsora_observation.geometry import tangent_grid, ARCSEC_RAD


def synthetic_sky(config):
    size = config["image"]["pixels"]
    pixel = config["image"]["pixel_arcsec"]
    l, m = tangent_grid(size, pixel)
    image = np.zeros((size, size))
    source = config["source"]
    model = source["model"]
    if model == "point":
        image[size//2, size//2] = 1
    elif model == "double":
        # Two on-grid point sources with a reproducible flux ratio.
        offset = max(1, round(80/pixel))
        if offset >= size//2:
            raise ValueError("double source outside field")
        image[size//2, size//2-offset] = .6
        image[size//2, size//2+offset] = .4
    elif model == "shell":
        radius = np.hypot(l, m) / ARCSEC_RAD
        image[(radius >= 95) & (radius <= 150)] = 1
    else:
        raise ValueError("Cas A reference loading is introduced separately")
    if image.sum() == 0:
        raise ValueError("model contains no flux in the field")
    return image / image.sum() * source["total_flux_jy"]


def components(image, pixel_arcsec):
    l, m = tangent_grid(image.shape[0], pixel_arcsec)
    select = image != 0
    return np.column_stack([l[select], m[select]]), image[select]
