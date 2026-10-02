"""Gain invariant closures with an explicit high SNR noise approximation.

Convention: V_ij = E[x_i conj(x_j)], i < j. No station calibration is
required. Baseline thermal errors are assumed independent and circular;
shared source noise, low SNR bias and inter-cell correlation are excluded.
"""
from itertools import combinations
import json
from pathlib import Path
import numpy as np
from scipy.linalg import qr


def closure_design(pairs):
    pairs = np.asarray(pairs)
    if (pairs.ndim != 2 or pairs.shape[1] != 2 or not len(pairs)
            or not np.issubdtype(pairs.dtype, np.integer)
            or np.any(pairs < 0) or np.any(pairs[:, 0] >= pairs[:, 1])
            or len(np.unique(pairs, axis=0)) != len(pairs)):
        raise ValueError('unique ordered integer baseline pairs required')
    stations = sorted(set(pairs.ravel().tolist()))
    if len(stations) > 16:
        raise ValueError('reference closure implementation supports up to 16 stations')
    edges = {tuple(p): i for i, p in enumerate(pairs)}
    phase, triangles, amplitude, quadrangles = [], [], [], []
    for i, j, k in combinations(stations, 3):
        keys = [(i, j), (j, k), (i, k)]
        if all(p in edges for p in keys):
            row = np.zeros(len(pairs))
            for key, sign in zip(keys, [1, 1, -1]): row[edges[key]] = sign
            phase.append(row); triangles.append([i, j, k])
    for i, j, k, l in combinations(stations, 4):
        for choice, denominator in enumerate([[(i, k), (j, l)], [(i, l), (j, k)]]):
            keys = [(i, j), (k, l), *denominator]
            if all(p in edges for p in keys):
                row = np.zeros(len(pairs))
                for key, sign in zip(keys, [1, 1, -1, -1]): row[edges[key]] = sign
                amplitude.append(row); quadrangles.append([i, j, k, l, choice])
    return {'phase_matrix': np.asarray(phase).reshape(-1, len(pairs)),
            'logamp_matrix': np.asarray(amplitude).reshape(-1, len(pairs)),
            'triangles': np.asarray(triangles, dtype=int).reshape(-1, 3),
            'quadrangles': np.asarray(quadrangles, dtype=int).reshape(-1, 5)}


def wrap_phase(value):
    return np.angle(np.exp(1j * value))


def form_closures(visibilities, weights, pairs, min_snr=5.):
    v, w = np.asarray(visibilities), np.asarray(weights)
    if (not np.iscomplexobj(v) or v.ndim < 1 or v.shape != w.shape
            or v.shape[-1] != len(pairs) or not np.isfinite(v).all()
            or not np.isfinite(w).all() or np.any(w < 0)
            or not np.isfinite(min_snr) or min_snr < 5):
        raise ValueError('finite complex visibilities, nonnegative quadrature weights and min_snr >= 5 required')
    design = closure_design(pairs)
    snr = np.abs(v) * np.sqrt(w)
    baseline_valid = (snr >= min_snr) & (np.abs(v) > 0)
    variance = np.zeros(v.shape)
    np.divide(1., snr**2, out=variance, where=baseline_valid)
    phase = np.angle(v)
    logamp = np.log(np.where(np.abs(v) > 0, np.abs(v), 1.))
    result = {**design, 'baseline_snr': snr, 'baseline_variance': variance,
              'baseline_valid': baseline_valid}
    for name, values in [('phase', phase), ('logamp', logamp)]:
        matrix = design[name + '_matrix']
        valid = np.all(baseline_valid[..., None, :] | (matrix == 0), axis=-1)
        output = values @ matrix.T
        if name == 'phase': output = wrap_phase(output)
        result[name] = np.where(valid, output, 0.)
        result[name + '_valid'] = valid
    return result


def independent_closures(matrix, valid, baseline_variance):
    """Choose a full-rank subset and return its *full* covariance matrix.

    Pivoted QR uses noise-scaled rows. Shared baselines produce off-diagonal
    covariance even in the independent subset. Invalid data never enter it.
    """
    matrix, valid, variance = np.asarray(matrix), np.asarray(valid), np.asarray(baseline_variance)
    if (matrix.ndim != 2 or valid.shape != (len(matrix),) or valid.dtype != np.bool_
            or variance.shape != (matrix.shape[1],) or not np.isfinite(matrix).all()
            or not np.isfinite(variance).all() or np.any(variance < 0)):
        raise ValueError('invalid closure covariance inputs')
    candidates = np.flatnonzero(valid)
    if not len(candidates): return candidates, np.empty((0, 0))
    rows = matrix[candidates]
    diagonal = rows**2 @ variance
    if np.any(diagonal <= 0): raise ValueError('valid closures need positive variance')
    _, r, order = qr((rows / np.sqrt(diagonal[:, None])).T, pivoting=True, mode='economic')
    rank = np.count_nonzero(np.abs(np.diag(r)) > abs(r[0, 0]) * 1e-11)
    selected = candidates[order[:rank]]
    covariance = (matrix[selected] * variance) @ matrix[selected].T
    np.linalg.cholesky(covariance)
    return selected, covariance


def load_visibility_input(path):
    from vsora_formats.visibility import load_visibility
    from vsora_formats.spectral import load_spectral
    from vsora_formats.fitsidi import read_fitsidi
    if Path(path).suffix.lower() == '.fits':
        data = read_fitsidi(path)
        data.setdefault('visibilities', data['vis_jy'])
    else:
        with np.load(path, allow_pickle=False) as probe: spectral = 'times_s' in probe.files
        data = load_spectral(path) if spectral else load_visibility(path)
        data.setdefault('visibilities', data.get('vis_jy'))
    if data['visibilities'].ndim == 2:
        data['visibilities'] = data['visibilities'][:, None, :]
        data['weights'] = data['weights'][:, None, :]
        data['uvw_lambda'] = data['uvw_lambda'][:, None, :, :]
    return data


def extract_closures(path, output, min_snr=5.):
    """Preserve geometry and input unit; closure values themselves have no Jy unit."""
    import hashlib
    data = load_visibility_input(path)
    result = form_closures(data['visibilities'], data['weights'], data['pairs'], min_snr)
    metadata = {'schema_version': 1, 'input_unit': data['metadata'].get('visibility_unit', 'Jy'),
                'phase_unit': 'rad', 'logamp_unit': '1', 'min_baseline_snr': min_snr,
                'noise_model': 'high SNR independent circular Gaussian baseline errors; no source self-noise',
                'config': data['metadata']['config']}
    with open(path, 'rb') as stream:
        metadata['input_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
    out = Path(output)
    if out.suffix != '.npz': raise ValueError('closure output must have .npz extension')
    if out.exists(): raise FileExistsError('closure output already exists')
    out.parent.mkdir(parents=True, exist_ok=True)
    axes = {k: data[k] for k in ('time_mjd', 'times_s', 'frequencies_hz') if k in data}
    if 'time_origin_utc' in data['metadata']: metadata['time_origin_utc'] = data['metadata']['time_origin_utc']
    np.savez_compressed(out, **result, **axes, pairs=data['pairs'], uvw_lambda=data['uvw_lambda'],
                        metadata_json=np.array(json.dumps(metadata)))
    return {'phase_valid': int(result['phase_valid'].sum()),
            'logamp_valid': int(result['logamp_valid'].sum()), 'input_unit': metadata['input_unit'],
            'absolute_flux_available': False, 'absolute_centroid_available': False}


def main():
    import argparse
    p = argparse.ArgumentParser(description='Extract closure phases and log closure amplitudes')
    p.add_argument('--input', required=True); p.add_argument('--output', required=True)
    p.add_argument('--min-snr', type=float, default=5.)
    a = p.parse_args()
    print(json.dumps(extract_closures(a.input, a.output, a.min_snr), indent=2))


if __name__ == '__main__': main()
