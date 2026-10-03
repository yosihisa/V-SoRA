"""Coherence calculations for explicitly assumed deterministic rate drift."""
import warnings
import numpy as np
from scipy.integrate import quad,IntegrationWarning
from scipy.optimize import brentq


def quadratic_coherence(rate_slope_hz_per_s,integration_s,residual_rate_hz=0.):
    """Mean exp(i phase), with residual rate specified at integration midpoint.

    Station constant gains/phase are not part of this baseline attenuation.
    No stochastic phase noise, missing samples or measured hardware model.
    """
    values=(rate_slope_hz_per_s,integration_s,residual_rate_hz)
    if any(isinstance(x,(bool,np.bool_)) or not np.isfinite(x) for x in values) or not 0<integration_s<=3:
        raise ValueError('finite drift/rate and integration in (0,3] seconds required')
    r=residual_rate_hz*integration_s;a=rate_slope_hz_per_s*integration_s**2
    if abs(r)+abs(a)>1000:raise ValueError('quadratic reference integral limited to 1000 dimensionless cycles')
    if a==0:return complex(np.sinc(r))
    phase=lambda z:2*np.pi*(r*z+.5*a*z*z)
    with warnings.catch_warnings():
        warnings.simplefilter('error',IntegrationWarning)
        real=quad(lambda z:np.cos(phase(z)),-.5,.5,epsabs=1e-11,limit=2000)[0]
        imag=quad(lambda z:np.sin(phase(z)),-.5,.5,epsabs=1e-11,limit=2000)[0]
    return complex(real,imag)


def centered_drift_limit(integration_s,minimum_coherence=.9):
    """First 90% crossing for a smooth linear rate slope, optimal centering."""
    if (isinstance(minimum_coherence,bool) or not np.isfinite(minimum_coherence)
            or not .5<=minimum_coherence<1):raise ValueError('minimum coherence in [0.5,1) required')
    quadratic_coherence(0.,integration_s)
    dimensionless=brentq(lambda x:abs(quadratic_coherence(x,1.))-minimum_coherence,0.,8.,xtol=1e-12)
    return float(dimensionless/integration_s**2)
