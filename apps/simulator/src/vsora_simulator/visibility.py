"""Direct Fourier reference using a discrete, phase-tracked sky."""
import numpy as np
from .sky import components


def direct_visibility(uvw_lambda, image, pixel_arcsec, block_size=128):
    uvw = np.asarray(uvw_lambda, dtype=float)
    if uvw.shape[-1] != 3 or not np.isfinite(uvw).all():
        raise ValueError("finite uvw (...,3) required")
    lm, flux = components(image, pixel_arcsec)
    directions = np.column_stack([lm, np.sqrt(1-(lm**2).sum(axis=1))-1])
    flat = uvw.reshape(-1,3)
    result = np.empty(len(flat), dtype=complex)
    for start in range(0,len(flat),block_size):
        phase = flat[start:start+block_size] @ directions.T
        result[start:start+block_size] = np.exp(-2j*np.pi*phase) @ flux
    return result.reshape(uvw.shape[:-1])


def thermal_noise(config, pairs, shape):
    sefd = np.array([s["sefd_jy"] for s in config["stations"]])
    obs = config["observation"]
    eta = config["noise"]["efficiency"]
    sigma_b = np.sqrt(sefd[pairs[:,0]]*sefd[pairs[:,1]]/(2*obs["bandwidth_hz"]*obs["integration_s"])) / eta
    sigma = np.broadcast_to(sigma_b,shape).copy()
    rng = np.random.default_rng(config["seed"])
    noise = sigma * (rng.normal(size=shape)+1j*rng.normal(size=shape))
    return noise, sigma
