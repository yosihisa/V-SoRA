"""Reference likelihood for zero-mean, iid proper complex Gaussian voltages.

All stations must share every sample. This does not infer unknown receiver
gains, SEFD, LO, effective sample count, or a closure image likelihood.
"""
import math
from numbers import Integral

import numpy as np
from scipy.linalg import solve_triangular


def _array(value, name, ndim):
    if np.ma.isMaskedArray(value):
        raise ValueError(f'{name}: masked data are not supported')
    raw = np.asarray(value)
    if raw.ndim != ndim or not np.issubdtype(raw.dtype, np.number):
        raise ValueError(f'{name}: numeric {ndim}-dimensional array required')
    if not np.isfinite(raw).all():
        raise ValueError(f'{name}: finite values required')
    with np.errstate(over='ignore', under='ignore', invalid='ignore'):
        result = raw.astype(np.complex128)
    if (not np.isfinite(result).all()
            or np.any((raw.real != 0) & (result.real == 0))
            or np.any((raw.imag != 0) & (result.imag == 0))):
        raise ValueError(f'{name}: values must be representable in complex128')
    return result


def _scale(a):
    return float(max(np.max(np.abs(a.real)), np.max(np.abs(a.imag))))


def _divide_real(a, scale):
    # Divide components separately: complex division may form 1/scale first,
    # which overflows for a representable, subnormal positive scale.
    result = np.empty_like(a)
    with np.errstate(over='ignore', under='ignore', invalid='ignore'):
        result.real = a.real / scale
        result.imag = a.imag / scale
    if (not np.isfinite(result).all()
            or np.any((a.real != 0) & (result.real == 0))
            or np.any((a.imag != 0) & (result.imag == 0))):
        raise ValueError('matrix scaling is outside complex128')
    return result


def _hermitian(value, name):
    a = _array(value, name, 2)
    if a.shape[0] == 0 or a.shape[0] != a.shape[1]:
        raise ValueError(f'{name}: nonempty square matrix required')
    scale = _scale(a)
    z = _divide_real(a, scale) if scale else a.copy()
    if (np.any((a.real != 0) & (z.real == 0))
            or np.any((a.imag != 0) & (z.imag == 0))):
        raise ValueError(f'{name}: normalization erases a nonzero component')
    tol = 64 * np.finfo(float).eps * len(a)
    if np.max(np.abs(z - z.conj().T)) > tol:
        raise ValueError(f'{name}: Hermitian matrix required')
    # Normalize before averaging so large finite entries do not overflow.
    z = z + .5 * (z.conj().T - z)
    return z, scale, tol


def _covariance(value, name):
    a, scale, tol = _hermitian(value, name)
    eigenvalues = np.linalg.eigvalsh(a)
    if scale == 0 or eigenvalues[0] <= tol * eigenvalues[-1]:
        raise ValueError(f'{name}: numerically resolved positive definite matrix required')
    return a, scale, np.linalg.cholesky(a)


def _moment(value, n):
    s, scale, tol = _hermitian(value, 'second_moment')
    if len(s) != n:
        raise ValueError('covariance and second moment dimensions differ')
    if np.linalg.eigvalsh(s)[0] < -tol * max(1., float(np.linalg.norm(s, 2))):
        raise ValueError('second_moment: positive semidefinite matrix required')
    return s, scale


def _modes(modes):
    if isinstance(modes, (bool, np.bool_)) or not isinstance(modes, Integral) or not 1 <= modes <= 2**53:
        raise ValueError('modes: integer in 1..2**53 required')
    return int(modes)


def _whiten(l, a):
    left = solve_triangular(l, a, lower=True, check_finite=False)
    return solve_triangular(l, left.conj().T, lower=True, check_finite=False).conj().T


def _finite(value):
    if not math.isfinite(value):
        raise ValueError('likelihood calculation is outside the float64 range')
    return float(value)


def sample_second_moment(voltage):
    """Return sum_m x_m x_m^H / M for complete rows [M, stations].

    No fitted mean is subtracted. Missing, masked, or nonfinite data are
    rejected; provenance, iid and properness remain caller assumptions.
    """
    x = _array(voltage, 'voltage', 2)
    if min(x.shape) == 0:
        raise ValueError('voltage: nonempty [M, stations] required')
    scale = _scale(x)
    if scale == 0:
        return np.zeros((x.shape[1], x.shape[1]), dtype=complex)
    y = _divide_real(x, scale)
    if (np.any((x.real != 0) & (y.real == 0))
            or np.any((x.imag != 0) & (y.imag == 0))):
        raise ValueError('voltage normalization erases a nonzero component')
    normalized = y.T @ y.conj() / len(x)
    if np.any(np.any(x != 0, axis=0) & (normalized.diagonal().real == 0)):
        raise ValueError('positive sample power underflows complex128')
    with np.errstate(over='ignore', under='ignore', invalid='ignore'):
        result = (normalized * scale) * scale
    if (not np.isfinite(result).all()
            or np.any((normalized.real != 0) & (result.real == 0))
            or np.any((normalized.imag != 0) & (result.imag == 0))):
        raise ValueError('second moment is outside the complex128 range')
    return result


def gaussian_nll(covariance, second_moment, modes):
    """M[logdet(C) + tr(C^-1 S)], omitting M*n*log(pi).

    This is the raw-voltage negative log likelihood up to a constant, not
    the normalized probability density of a sample covariance matrix.
    """
    m = _modes(modes)
    c, cscale, l = _covariance(covariance, 'covariance')
    s, sscale = _moment(second_moment, len(c))
    with np.errstate(over='ignore', under='ignore', invalid='ignore'):
        ratio = sscale / cscale
        if not math.isfinite(ratio) or (sscale > 0 and ratio == 0):
            raise ValueError('second moment / covariance scale is unresolved')
        trace = float(np.trace(_whiten(l, s)).real) * ratio
        logdet = len(c) * math.log(cscale) + 2 * math.fsum(np.log(l.diagonal().real))
        return _finite(m * math.fsum((logdet, trace)))


def _relative_remainder(d):
    # d/(1+d) - log1p(d), with its first-order cancellation removed.
    if abs(d) < .001:
        value = math.fsum(((-1)**(k+1) * (k-1)/k * d**k) for k in range(2, 9))
        if d != 0 and value == 0:
            raise ValueError('nonzero leading likelihood term underflows float64')
        return value
    return d / (1 + d) - math.log1p(d)


def gaussian_log_likelihood_ratio(covariance0, covariance1, second_moment, modes):
    """log L(C1) - log L(C0); positive favors known candidate C1.

    Work with the whitened difference C1-C0 to retain small changes. Very
    ill-conditioned individual or relative covariance pairs are rejected.
    Equal valid covariance arrays return exactly zero after validation.
    """
    m = _modes(modes)
    c0, scale0, l0 = _covariance(covariance0, 'covariance0')
    c1, _, _ = _covariance(covariance1, 'covariance1')
    if c0.shape != c1.shape:
        raise ValueError('candidate covariance dimensions differ')
    s, sscale = _moment(second_moment, len(c0))
    a0 = _array(covariance0, 'covariance0', 2)
    a1 = _array(covariance1, 'covariance1', 2)
    if np.array_equal(a0, a1):
        return 0.
    with np.errstate(over='ignore', under='ignore', invalid='ignore'):
        delta = _divide_real(a1 - a0, scale0)
        ratio = sscale / scale0
    if not np.isfinite(delta).all() or not math.isfinite(ratio) or (sscale and ratio == 0):
        raise ValueError('relative covariance / second moment scale is unresolved')
    dmatrix = _whiten(l0, delta + .5 * (delta.conj().T - delta))
    if not np.isfinite(dmatrix).all():
        raise ValueError('whitened covariance difference is outside complex128')
    d, u = np.linalg.eigh(dmatrix + .5 * (dmatrix.conj().T - dmatrix))
    relative = 1 + d
    tol = 64 * np.finfo(float).eps * len(c0)
    if np.min(relative) <= tol * max(1., float(np.max(relative))):
        raise ValueError('relative covariance pair is numerically unresolved')
    # Whiten S-C0 directly. Rotating T and then subtracting 1 would turn
    # orthonormal-eigenvector roundoff into a spurious first-order signal.
    raw_s = _array(second_moment, 'second_moment', 2)
    with np.errstate(over='ignore', under='ignore', invalid='ignore'):
        residual = _divide_real(raw_s - a0, scale0)
    residual = _whiten(l0, residual + .5 * (residual.conj().T - residual))
    if not np.isfinite(residual).all():
        raise ValueError('whitened second moment residual is outside complex128')
    diagonal = np.einsum('ij,ij->j', u.conj(), residual @ u).real
    with np.errstate(over='ignore', invalid='ignore'):
        terms = [float(di) * float(e)/(1+float(e)) + _relative_remainder(float(e))
                 for e, di in zip(d, diagonal, strict=True)]
    return _finite(m * math.fsum(terms))
