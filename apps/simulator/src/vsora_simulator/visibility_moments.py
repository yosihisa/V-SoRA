"""Exact second moments of averaged iid proper Gaussian station voltages.

Forward simulator model, not an estimator of unknown sky/receiver covariance.
No quantization, filtering, nonuniform masks or time-dependent station phase.
"""
import numpy as np


def visibility_noise_moments(station_covariance, samples, pairs=None):
    """S[i,j]=E[x_i conj(x_j)], V[i,j]=mean(x_i conj(x_j)).

    Returns E[delta V delta V*], E[delta V delta V] (pseudocovariance),
    and full real covariance in [all Re V, all Im V] order. The moments are
    exact under iid Gaussian voltages; a Gaussian visibility distribution is
    an additional approximation when used by a downstream simulation.
    """
    s = np.asarray(station_covariance, complex)
    if (s.ndim != 2 or s.shape[0] != s.shape[1] or not 2 <= len(s) <= 32
            or not np.isfinite(s).all()
            or not np.allclose(s, s.conj().T, rtol=1e-10, atol=1e-14)):
        raise ValueError('station covariance must be finite Hermitian, 2..32 stations')
    s = (s+s.conj().T)/2
    scale = max(float(np.max(abs(s))), np.finfo(float).tiny)
    if np.linalg.eigvalsh(s).min() < -1e-12*scale:
        raise ValueError('station covariance must be positive semidefinite')
    if isinstance(samples, bool) or not isinstance(samples, (int, np.integer)) or samples < 1:
        raise ValueError('positive integer independent sample count required')
    if pairs is None:
        pairs = [[i, j] for i in range(len(s)) for j in range(i+1, len(s))]
    p = np.asarray(pairs)
    if (p.ndim != 2 or p.shape[1:] != (2,) or not len(p)
            or not np.issubdtype(p.dtype, np.integer) or np.any(p < 0)
            or np.any(p >= len(s)) or np.any(p[:, 0] >= p[:, 1])
            or len(set(map(tuple, p.tolist()))) != len(p)):
        raise ValueError('unique ordered visibility baseline pairs required')
    i, j = p.T
    with np.errstate(over='ignore', invalid='ignore'):
        covariance = s[i[:, None], i[None, :]]*s[j[None, :], j[:, None]]/samples
        pseudo = s[i[:, None], j[None, :]]*s[i[None, :], j[:, None]]/samples
        real = .5*np.block([[np.real(covariance+pseudo), np.imag(pseudo-covariance)],
                          [np.imag(pseudo+covariance), np.real(covariance-pseudo)]])
    if not np.isfinite(real).all() or not np.isfinite(covariance).all() or not np.isfinite(pseudo).all():
        raise ValueError('visibility moments exceed finite numerical range')
    return {'pairs': p.copy(), 'mean': s[i, j].copy(),
        'complex_covariance': covariance, 'complex_pseudocovariance': pseudo,
        'real_covariance': (real+real.T)/2, 'real_parameter_order': 'all real baselines, then all imaginary baselines',
        'samples': int(samples), 'distribution_gaussian_assumed': False,
        'model': 'Sample mean of iid zero-mean proper complex Gaussian station voltages',
        'limits': 'Forward known station covariance, uniform independent samples. Not measured covariance, quantized/filtered IQ, correlated time/channel, gain variation or real hardware.'}
