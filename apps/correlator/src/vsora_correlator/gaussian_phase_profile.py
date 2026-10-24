"""Phase-only nuisance fits for a supplied proper Gaussian covariance.

Amplitudes/SEFD and the sky covariance remain supplied. Station phases are
constant within a window. This is not an image or unknown-LO likelihood.
"""
import math
from numbers import Integral

import numpy as np
from scipy.linalg import cho_solve
from scipy.optimize import minimize

from .gaussian_likelihood import (
    _covariance, _divide_real, _modes, _moment, _scale,
    gaussian_log_likelihood_ratio, gaussian_nll,
)


class PhaseProfileConvergenceError(RuntimeError):
    """A profile score was requested without verified local stationarity."""


def _phase_cost_gradient(theta, a):
    """Only off-diagonal trace; phi[0]=0. A has already been normalized."""
    phase = np.exp(1j*np.r_[0., theta])
    i, j = np.triu_indices(len(a), 1)
    terms = a[i,j] * phase[j] * phase[i].conj()
    gradient = np.zeros(len(a))
    np.add.at(gradient, i, 2*terms.imag)
    np.add.at(gradient, j, -2*terms.imag)
    return float(2*np.sum(terms.real)), gradient[1:]


def _problem(covariance, second_moment, modes):
    m = _modes(modes)
    gaussian_nll(covariance, second_moment, m)  # Reuse the public numeric contract.
    c, scale, lower = _covariance(covariance, 'covariance')
    if len(c) > 16:
        raise ValueError('phase reference supports at most16 stations')
    s, sscale = _moment(second_moment, len(c))
    # Precision coefficients are explicitly retained here for the phase graph.
    # Obtain them by Cholesky solves rather than an inverse routine.
    precision = cho_solve((lower, True), np.eye(len(c), dtype=complex))
    a = precision.T * s
    if np.any((precision.T != 0) & (s != 0) & (a == 0)):
        raise ValueError('nonzero phase coefficient underflows complex128')
    a = a + .5*(a.conj().T-a)
    np.fill_diagonal(a, 0.)
    ascale = _scale(a)
    normalized = _divide_real(a, ascale) if ascale else a.copy()
    return c, scale, normalized, ascale, sscale/scale, m


def fit_station_phases(covariance, second_moment, modes, *, max_iterations=200):
    """Fit constant phases, preserving supplied amplitudes and noise model.

    One/two station or phase-independent cases have analytic minima. Larger
    cases return a local stationary candidate, never a global certificate.
    Failed local fits retain state='not_converged'; compare refuses those.
    """
    if (isinstance(max_iterations, (bool, np.bool_)) or not isinstance(max_iterations, Integral)
            or not 1 <= max_iterations <= 1000):
        raise ValueError('max_iterations must be an integer in1..1000')
    c, scale, a, ascale, sratio, m = _problem(covariance, second_moment, modes)
    n = len(c); runs = []; candidates = []
    if ascale == 0 or n == 1:
        theta = np.zeros(n-1); state = 'phase_independent'; global_minimum = True
        chosen = None
    elif n == 2:
        theta = np.array([np.pi-np.angle(a[0,1])])
        state = 'analytic_two_station'; global_minimum = True; chosen = None
    else:
        _, vectors = np.linalg.eigh(a)
        starts = [np.angle(v)-np.angle(v[0]) for v in vectors.T]
        # Include every station before fixing the reference, so the set of
        # phase perturbations does not single out a station ordering.
        starts += [starts[0] + np.pi*np.eye(n)[k] for k in range(n)]
        for index, initial in enumerate(starts):
            result = minimize(_phase_cost_gradient, initial[1:]-initial[0], args=(a,), jac=True,
                method='L-BFGS-B', options={'maxiter':int(max_iterations), 'gtol':1e-7,
                                          'ftol':1e-14, 'maxls':50})
            x = np.asarray(result.x, dtype=float)
            if x.shape != (n-1,) or not np.isfinite(x).all():
                raise PhaseProfileConvergenceError('optimizer returned invalid phases')
            value, gradient = _phase_cost_gradient(x, a)
            if not math.isfinite(value) or not np.isfinite(gradient).all():
                raise PhaseProfileConvergenceError('optimizer returned nonfinite objective')
            norm = float(np.max(abs(gradient)))
            verified = bool(result.success) and norm <= 1e-6
            candidates.append((value, x.copy(), verified))
            runs.append({'start_index':index, 'optimizer_success':bool(result.success),
                'stationarity_verified':verified, 'iterations':int(result.nit),
                'objective_normalized':value, 'gradient_inf_norm_normalized':norm,
                'optimizer_message':str(result.message)})
        best_seen = min(c[0] for c in candidates)
        tie = 64*np.finfo(float).eps*n*max(1.,abs(best_seen))
        eligible = [k for k, v in enumerate(candidates) if v[2] and v[0] <= best_seen+tie]
        chosen = min(eligible or range(len(candidates)), key=lambda k:candidates[k][0])
        _, theta, verified = candidates[chosen]
        state = 'stationary_candidate' if verified else 'not_converged'
        global_minimum = False
    theta = np.angle(np.exp(1j*theta)); phases = np.r_[0.,theta]
    gain = np.exp(1j*phases)
    fitted = (gain[:,None]*c*gain.conj()[None,:])*scale
    value, gradient = _phase_cost_gradient(theta,a)
    with np.errstate(over='ignore',under='ignore',invalid='ignore'):
        dependent = value*ascale*sratio
    if not math.isfinite(dependent) or (value != 0 and ascale > 0 and sratio > 0 and dependent == 0):
        raise ValueError('phase-dependent objective is outside float64')
    return {'type':'known_covariance_station_phase_profile', 'state':state,
        'station_count':n, 'modes':m, 'reference_station_index':0,
        'candidate_phase_rad':phases.tolist(),
        'fitted_covariance_real_imag':np.stack((fitted.real,fitted.imag),axis=-1).tolist(),
        'nll_without_constant':gaussian_nll(fitted,second_moment,m),
        'phase_dependent_trace_per_mode':dependent,
        'gradient_inf_norm_normalized':float(np.max(abs(gradient))) if len(gradient) else 0.,
        'chosen_start_index':chosen, 'optimizer_runs':runs,
        'global_minimum_for_this_phase_objective_proved':global_minimum,
        'true_phases_supplied_for_initialization':False,
        'physical_phase_identification_verified':False,
        'amplitudes_and_sefd_supplied':True, 'unknown_amplitude_sefd_or_lo_estimated':False,
        'constant_phase_within_window_assumed':True, 'image_likelihood_defined':False}


def compare_phase_profiles(covariance0, covariance1, second_moment, modes, *, max_iterations=200):
    """Difference of fitted conditional log likelihoods, not a calibrated test.

    Local fitting failures raise. No chi-square p-value, image probability,
    global optimum or practical calibration guarantee is attached.
    """
    fit0 = fit_station_phases(covariance0,second_moment,modes,max_iterations=max_iterations)
    fit1 = fit_station_phases(covariance1,second_moment,modes,max_iterations=max_iterations)
    accepted = {'phase_independent','analytic_two_station','stationary_candidate'}
    if fit0['state'] not in accepted or fit1['state'] not in accepted:
        raise PhaseProfileConvergenceError('both phase fits must reach verified stationarity')
    def matrix(fit):
        a = np.asarray(fit['fitted_covariance_real_imag'])
        return a[...,0]+1j*a[...,1]
    score = gaussian_log_likelihood_ratio(matrix(fit0),matrix(fit1),second_moment,modes)
    return {'state':'fitted_reference_score','log_likelihood1_minus0':score,
        'fit0':fit0,'fit1':fit1, 'global_profile_optimum_proved':all(
            f['global_minimum_for_this_phase_objective_proved'] for f in (fit0,fit1)),
        'calibrated_hypothesis_test_defined':False,'image_probability_defined':False,
        'unknown_amplitude_sefd_or_lo_estimated':False}
