"""Conditional centered complex coherence from Gaussian linear-rate errors.

This is E[mean exp(i centered phase error)], not E[abs(mean)], a confidence
bound or a measurement of receiver coherence. Fast unmodelled phase is absent.
"""
import warnings
import numpy as np
from scipy.integrate import quad, IntegrationWarning
from .rate_linear import validate_linear_profile

PARAMETER_ORDER = 'relative rates Hz, then relative rate slopes Hz/s'


def linear_rate_uncertainty(profile, station_ids, origin, start_s, end_s, pairs=None):
    """Uniform integration, constant station phase removed at window center.

    The full covariance is used, including station and rate/slope correlations.
    Errors are assumed zero-mean Gaussian with the supplied covariance. This
    assumption is conditional and has not been calibrated on real hardware.
    """
    if (not all(isinstance(t, (int, float)) and not isinstance(t, bool)
                and np.isfinite(t) for t in (start_s, end_s))
            or not 0 < end_s-start_s <= 3.+1e-9):
        raise ValueError('uncertainty window must have finite duration in (0, 3] seconds')
    _, _, epoch = validate_linear_profile(profile, station_ids, origin, start_s, end_s)
    count = len(station_ids)
    reference = profile.get('reference_station')
    if (isinstance(reference, bool) or not isinstance(reference, int)
            or reference not in range(count) or count < 2):
        raise ValueError('invalid uncertainty reference station')
    unknown = [s for s in range(count) if s != reference]
    if (profile.get('covariance_station_order') != unknown
            or profile.get('parameter_order') != PARAMETER_ORDER):
        raise ValueError('uncertainty covariance/parameter order differs')
    n = len(unknown)
    c = np.asarray(profile.get('parameter_covariance'), float)
    if (c.shape != (2*n, 2*n) or not np.isfinite(c).all()
            or not np.allclose(c, c.T, rtol=1e-10, atol=1e-14)):
        raise ValueError('uncertainty covariance must be finite and symmetric')
    c = (c+c.T)/2
    eigenvalues = np.linalg.eigvalsh(c)
    scale = max(float(np.max(abs(c))), np.finfo(float).tiny)
    if eigenvalues.min() < -1e-12*scale:
        raise ValueError('uncertainty covariance must be positive semidefinite')
    if pairs is None:
        pairs = [[i, j] for i in range(count) for j in range(i+1, count)]
    p = np.asarray(pairs)
    if (p.ndim != 2 or p.shape[1:] != (2,) or not len(p)
            or not np.issubdtype(p.dtype, np.integer) or np.any(p < 0)
            or np.any(p >= count) or np.any(p[:, 0] >= p[:, 1])
            or len(set(map(tuple, p.tolist()))) != len(p)):
        raise ValueError('unique ordered uncertainty baseline pairs required')
    center = (start_s+end_s)/2
    duration = end_s-start_s
    rows = []
    for i, j in p:
        d = np.array([(1. if s == i else 0.)-(1. if s == j else 0.) for s in unknown])
        # Two-vector baseline covariance; preserve all cross terms.
        transform = np.zeros((2, 2*n))
        transform[0, :n] = d
        transform[1, n:] = d
        baseline_covariance = transform @ c @ transform.T

        def variance(z):
            x = duration*z
            b = 2*np.pi*np.array([x, x*(center-epoch)+.5*x*x])
            v = float(b @ baseline_covariance @ b)
            if not np.isfinite(v):
                raise ValueError('uncertainty phase variance is not finite')
            return max(0., v)

        # Bound the whole interval using coefficient magnitudes, to keep the
        # adaptive integration's narrowest supported features resolved.
        max_b = 2*np.pi*np.array([duration/2,
            duration/2*abs(center-epoch)+duration**2/8])
        variance_bound = float(max_b @ abs(baseline_covariance) @ max_b)
        if not np.isfinite(variance_bound) or variance_bound > 1e4:
            raise ValueError('uncertainty phase variance exceeds supported numerical range')
        with warnings.catch_warnings():
            warnings.simplefilter('error', IntegrationWarning)
            expected, error = quad(lambda z: np.exp(-.5*variance(z)), -.5, .5,
                points=[0.], epsabs=1e-10, epsrel=1e-10, limit=400)
        if error > 1e-8 or not 0. <= expected <= 1.+1e-12:
            raise ValueError('uncertainty quadrature did not converge')
        rows.append({'pair': [int(i), int(j)],
            'expected_centered_complex_coherence': float(min(1., expected)),
            'quadrature_absolute_error_estimate': float(error),
            'baseline_rate_slope_covariance': baseline_covariance.tolist(),
            'endpoint_phase_sigma_rad': [float(np.sqrt(variance(z))) for z in (-.5, .5)]})
    return {'schema_version': 1, 'type': 'linear_rate_uncertainty',
        'start_s': float(start_s), 'end_s': float(end_s),
        'center_s': float(center), 'integration_s': float(duration),
        'station_ids': list(station_ids), 'reference_station': reference,
        'profile_input_sha256': profile.get('input_sha256'),
        'baselines': rows,
        'minimum_expected_centered_complex_coherence': min(
            r['expected_centered_complex_coherence'] for r in rows),
        'coherence_stability_measured': False,
        'hardware_confidence_calibrated': False,
        'assumption': 'Zero-mean Gaussian parameter errors with supplied full Fisher covariance; uniform exposure; constant station phase removed at integration center.',
        'quantity': 'E[mean exp(i centered phase error)], not E[abs(mean)] or a single-realization bound.',
        'limits': 'Conditional model-error diagnostic only. Does not include unmodelled fast phase, aliases, shared sky/filter noise, incorrect covariance or gain changes. No actual OCXO, low-SNR or image-fidelity guarantee. No correction, gating or weights are changed. Windows <=3s within pilot; phase-variance numerical bound <=10000 rad^2.'}


def main():
    import argparse
    import hashlib
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description='Conditional Gaussian linear-rate error diagnostic; not hardware coherence')
    parser.add_argument('--profile', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--start-offset-s', type=float, required=True)
    parser.add_argument('--integration-s', type=float, required=True)
    args = parser.parse_args()
    target = Path(args.output)
    if target.exists():
        raise FileExistsError('choose a new uncertainty diagnostic output')
    source = Path(args.profile).read_bytes()
    profile = json.loads(source)
    result = linear_rate_uncertainty(profile, profile['station_ids'], profile['time_origin_utc'],
        args.start_offset_s, args.start_offset_s+args.integration_s)
    result['profile_sha256'] = hashlib.sha256(source).hexdigest()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
