import numpy as np
import pytest
from vsora_correlator.coherence import quadratic_coherence,centered_drift_limit


def test_zero_and_constant_residual_rate():
    assert quadratic_coherence(0.,.3)==1
    assert quadratic_coherence(0.,.3,2.)==pytest.approx(np.sinc(.6))


def test_quadratic_integral_matches_independent_midpoint_sum():
    for a,t,r in [(1.,3.,0.),(-.7,.3,2.),(12.,1.,-.3)]:
        z=(np.arange(200000)+.5)/200000-.5
        expected=np.exp(2j*np.pi*(r*t*z+.5*a*t*t*z*z)).mean()
        assert quadratic_coherence(a,t,r)==pytest.approx(expected,abs=1e-9)
    assert quadratic_coherence(-1.,3.)==pytest.approx(quadratic_coherence(1.,3.).conjugate())


def test_first_ninety_percent_crossing_scales_as_inverse_time_squared():
    a=centered_drift_limit(1.)
    assert 1<a<3 and abs(quadratic_coherence(a,1.))==pytest.approx(.9,abs=1e-10)
    assert centered_drift_limit(3.)==pytest.approx(a/9.)
    assert abs(quadratic_coherence(.9*a,1.))>.9 and abs(quadratic_coherence(1.1*a,1.))<.9


@pytest.mark.parametrize('args',[(float('nan'),1.),(0.,0.),(0.,3.1),(True,1.),(1001.,1.)])
def test_invalid_quadratic_inputs(args):
    with pytest.raises(ValueError):quadratic_coherence(*args)


def test_closure_of_integrated_station_chirps_does_not_cancel():
    from itertools import combinations
    from vsora_imaging.closure import form_closures
    pairs=np.array(list(combinations(range(4),2)));slopes=np.array([0.,.1,-.05,.15])
    v=np.array([quadratic_coherence(slopes[i]-slopes[j],3.) for i,j in pairs])[None,None,:]
    c=form_closures(v,np.full(v.shape,1e8),pairs,min_snr=10)
    assert c['logamp_valid'].all() and np.max(abs(c['logamp']))>.03
    assert c['phase_valid'].all() and np.max(abs(c['phase']))>1e-3


@pytest.mark.parametrize('slopes',[[0.,1.],[0.,float('nan'),0.,0.]])
def test_vdif_fixture_rejects_invalid_generating_slopes(tmp_path,slopes):
    from workflows.vdif_closure_validation import make_fixture
    with pytest.raises(ValueError,match='station rate slopes'):
        make_fixture(tmp_path/'invalid',frame_count=16,rate_slopes_hz_per_s=slopes)
