"""Independent references for the conditional, known-covariance API."""
from decimal import Decimal, localcontext

import numpy as np
import pytest
from scipy.stats import multivariate_normal

from vsora_correlator.gaussian_likelihood import (
    gaussian_log_likelihood_ratio as llr,
    gaussian_nll,
    sample_second_moment,
)


def fixture(n=3, m=37, seed=100):
    rng = np.random.default_rng(seed)
    a = rng.normal(size=(n, n)) + 1j * rng.normal(size=(n, n))
    c = a @ a.conj().T + np.eye(n)
    x = (rng.normal(size=(m, n)) + 1j*rng.normal(size=(m, n))) @ np.linalg.cholesky(c).T / np.sqrt(2)
    return c, x


def real_logpdf(c, x):
    r = .5 * np.block([[c.real, -c.imag], [c.imag, c.real]])
    return float(np.sum(multivariate_normal.logpdf(np.concatenate([x.real, x.imag], axis=1), mean=np.zeros(2*len(c)), cov=r)))


@pytest.mark.parametrize('n', [1, 2, 8])
@pytest.mark.parametrize('m', [1, 37])
def test_direct_voltage_and_independent_real_gaussian(n, m):
    c, x = fixture(n, m)
    s = sample_second_moment(x)
    direct = sum(np.outer(row, row.conj()) for row in x) / m
    np.testing.assert_allclose(s, direct, rtol=2e-14, atol=2e-14)
    raw = m*np.linalg.slogdet(c)[1] + sum(np.vdot(row, np.linalg.solve(c, row)).real for row in x)
    assert gaussian_nll(c, s, m) == pytest.approx(raw, rel=3e-14, abs=2e-13)
    full = gaussian_nll(c, s, m) + m*n*np.log(np.pi)
    assert full == pytest.approx(-real_logpdf(c, x), rel=2e-13, abs=2e-12)
    c1 = c + np.diag(np.linspace(.2, .7, n))
    expected = real_logpdf(c1, x) - real_logpdf(c, x)
    assert llr(c, c1, s, m) == pytest.approx(expected, rel=2e-11, abs=3e-12)
    assert llr(c1, c, s, m) == pytest.approx(-expected, rel=2e-11, abs=3e-12)


@pytest.mark.parametrize('scale', [1e-240, 1e-120, 1., 1e120, 1e240])
def test_common_scale(scale):
    c, x = fixture()
    s = sample_second_moment(x);m = len(x);c1 = c + np.eye(len(c))
    assert llr(c*scale, c1*scale, s*scale, m) == pytest.approx(llr(c, c1, s, m), abs=2e-12)
    assert gaussian_nll(c*scale, s*scale, m) == pytest.approx(gaussian_nll(c, s, m)+m*len(c)*np.log(scale), abs=1e-10)
    np.testing.assert_allclose(sample_second_moment(x*np.sqrt(scale))/scale, s, rtol=2e-14, atol=1e-14)


def test_complex_conjugation_orientation_and_known_congruence():
    c, x = fixture();s = sample_second_moment(x);c1 = c+np.eye(len(c));m = len(x)
    assert np.max(np.abs(s.imag)) > .1
    assert abs(gaussian_nll(c, s, m)-gaussian_nll(c, s.T, m)) > 1
    h = np.array([[1j, .1, .3j], [.2, 2, -.1j], [0, .1j, .6]])
    transform = lambda a: h @ a @ h.conj().T
    np.testing.assert_allclose(sample_second_moment(x @ h.T), transform(s), atol=2e-14)
    assert llr(transform(c), transform(c1), transform(s), m) == pytest.approx(llr(c, c1, s, m), abs=1e-12)


@pytest.mark.parametrize('delta', [-.2, -.00001, -1e-12, 1e-12, .00001, .2])
def test_tiny_difference_against_decimal(delta):
    c1 = 1.+delta
    with localcontext() as ctx:
        ctx.prec = 90
        d = Decimal.from_float(c1)-1
        reference = -(1+d).ln() + d/(1+d)
    result = llr([[1]], [[c1]], [[1]], 1)
    assert result == pytest.approx(float(reference), rel=3e-13, abs=1e-36)
    assert result < 0


@pytest.mark.parametrize('m', [1, 37, 2**53, np.int64(4)])
def test_identical_covariances_are_exact_zero_after_validation(m):
    c, x = fixture()
    assert llr(c, c.copy(), sample_second_moment(x), m) == 0.
    with pytest.raises(ValueError):
        llr(c, c, -np.eye(len(c)), m)


def test_known_mean_is_not_fitted_and_zero_rank_deficient_samples_are_valid():
    x = np.tile([1+2j, 3-1j], (3, 1));s = sample_second_moment(x)
    np.testing.assert_allclose(s, np.outer(x[0], x[0].conj()))
    assert gaussian_nll(np.eye(2), s, 3) == pytest.approx(45)
    np.testing.assert_array_equal(sample_second_moment(np.zeros((3, 2))), np.zeros((2, 2)))
    assert gaussian_nll(np.eye(2), np.zeros((2, 2)), 3) == 0
    assert llr(np.eye(2), np.eye(2)*2, np.zeros((2, 2)), 3) == pytest.approx(-6*np.log(2))


@pytest.mark.parametrize('m', [0, -1, True, np.bool_(True), 1., 2**53+1, np.inf, None])
def test_reject_invalid_mode_count(m):
    for fn in (lambda: gaussian_nll([[1]], [[1]], m), lambda: llr([[1]], [[2]], [[1]], m)):
        with pytest.raises(ValueError):fn()


@pytest.mark.parametrize('c', [[], [1], [[1,0]], [[0]], [[-1]], [[np.nan]], [[np.inf]],
    [[1,1j],[1j,1]], [[1,2],[2,1]], [[1,0],[0,1e-16]], [['1']], [[True]], np.ma.array([[1]],mask=False)])
def test_reject_invalid_covariance(c):
    with pytest.raises(ValueError):gaussian_nll(c, [[1]], 1)
    with pytest.raises(ValueError):llr([[1]], c, [[1]], 1)


@pytest.mark.parametrize('s', [[], [1], [[1,0]], [[-1]], [[np.nan]], [[np.inf]],
    [[1,2],[0,1]], [['1']], [[True]], np.ma.array([[1]],mask=False)])
def test_reject_invalid_moment(s):
    with pytest.raises(ValueError):gaussian_nll([[1]], s, 1)
    with pytest.raises(ValueError):llr([[1]], [[2]], s, 1)


@pytest.mark.parametrize('x', [[], [1], np.empty((0,2)), np.empty((2,0)), [[np.nan]], [[np.inf]],
    [['1']], [[True]], np.ma.array([[1]],mask=False), [[1e200]], [[1e-200]], [[1e200,1e-200]]])
def test_reject_invalid_or_unrepresentable_voltage(x):
    with pytest.raises(ValueError):sample_second_moment(x)


@pytest.mark.parametrize('args', [([[1]], [[1e-20]], [[1]], 1), ([[1e-240]], [[1e240]], [[1]], 1)])
def test_reject_unresolved_relative_pair(args):
    with pytest.raises(ValueError):llr(*args)


def test_no_inputs_mutated_and_dimension_checks():
    c, x = fixture();s = sample_second_moment(x);old = [a.copy() for a in (c,x,s)]
    gaussian_nll(c,s,3);llr(c,c+np.eye(3),s,3)
    for a,b in zip((c,x,s),old,strict=True):np.testing.assert_array_equal(a,b)
    with pytest.raises(ValueError):llr(c,np.eye(2),s,3)
    with pytest.raises(ValueError):gaussian_nll(c,np.eye(2),3)


def test_overflow_is_rejected():
    with pytest.raises(ValueError):gaussian_nll([[1e-240]],[[1e240]],1)
    with pytest.raises(ValueError):gaussian_nll([[1e-120]],[[1e180]],2**53)


def test_roundoff_hermitian_and_psd_tolerance():
    s = np.array([[1.,1e-16j],[0.,0.]],dtype=complex)
    assert np.isfinite(gaussian_nll(np.eye(2),s,1))
    with pytest.raises(ValueError):gaussian_nll(np.eye(2),np.diag([1.,-1e-5]),1)


def test_subnormal_covariance_scale_does_not_form_infinite_reciprocal():
    tiny = 1e-320
    assert gaussian_nll([[tiny]], [[tiny]], 1) == pytest.approx(np.log(tiny)+1)
    assert llr([[tiny]], [[tiny*2]], [[tiny]], 1) == pytest.approx(-np.log(2)+.5)


def decimal_identity_reference(c):
    """Independent 90-digit Gauss-Jordan inverse and determinant, real SPD."""
    with localcontext() as ctx:
        ctx.prec = 90
        n = len(c)
        a = [[Decimal.from_float(float(z)) for z in row] for row in c]
        inverse = [[Decimal(int(i == j)) for j in range(n)] for i in range(n)]
        determinant = Decimal(1)
        for j in range(n):
            pivot = a[j][j];determinant *= pivot
            a[j] = [z/pivot for z in a[j]]
            inverse[j] = [z/pivot for z in inverse[j]]
            for i in range(n):
                if i == j:continue
                factor = a[i][j]
                a[i] = [x-factor*y for x,y in zip(a[i],a[j],strict=True)]
                inverse[i] = [x-factor*y for x,y in zip(inverse[i],inverse[j],strict=True)]
        return float(Decimal(n)-determinant.ln()-sum(inverse[i][i] for i in range(n)))


@pytest.mark.parametrize('n',[2,8])
@pytest.mark.parametrize('delta',[1e-5,1e-12])
def test_matrix_tiny_difference_against_independent_decimal(n,delta):
    rng = np.random.default_rng(100)
    a = rng.normal(size=(n,n));c1 = np.eye(n)+delta*(a+a.T)
    expected = decimal_identity_reference(c1)
    assert llr(np.eye(n),c1,np.eye(n),1) == pytest.approx(expected,rel=2e-13,abs=1e-36)


def test_complex_matrix_reference_avoids_rotated_identity_roundoff():
    rng = np.random.default_rng(100);n=8
    a=rng.normal(size=(n,n))+1j*rng.normal(size=(n,n))
    c1=np.eye(n)+1e-12*(a+a.conj().T)
    # Real representation: logdet and trace double; convert back by 1/2.
    real=np.block([[c1.real,-c1.imag],[c1.imag,c1.real]])
    expected=decimal_identity_reference(real)/2
    assert llr(np.eye(n),c1,np.eye(n),1) == pytest.approx(expected,rel=2e-13,abs=1e-36)


@pytest.mark.parametrize('delta',[1e-200,1e-320,np.nextafter(0.,1.)])
def test_reject_underflow_of_nonzero_second_order_term(delta):
    with pytest.raises(ValueError):llr(np.eye(2),[[1,delta],[delta,1]],np.eye(2),1)
