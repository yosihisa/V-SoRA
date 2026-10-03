import numpy as np
import pytest
from scipy.special import j0
from vsora_correlator.rate_variation import diagnose_rate_variation
from workflows.rate_variation_validation import pilot


def test_constant_unknown_sky_gain_rates_and_finite_noise_seeds():
    confirmed=0
    for seed in range(16):
        q=diagnose_rate_variation(pilot(seed))
        assert q['state'] in ('consistent','unverified')
        if q['state']=='consistent':
            confirmed+=1;assert q['maximum_normalized_rate_difference']<6
        assert not q['coherence_stability_measured'] and not q['absolute_common_rate_measured']
    assert confirmed>=12 # Some four-part rate graphs may fail their existing consistency gate.


def test_linear_rate_variation_is_detected_without_truth_input():
    for seed in range(3):
        q=diagnose_rate_variation(pilot(seed,slopes=[0.,2.,-1.,3.]))
        assert q['state']=='variation_detected' and q['maximum_normalized_rate_difference']>6
        assert q['worst_difference']['first_part']!=q['worst_difference']['second_part']


def test_short_or_weak_or_disconnected_subpilots_are_unverified():
    assert diagnose_rate_variation(pilot(count=16))['state']=='unverified'
    weak=pilot();weak['weights'].fill(1e-8)
    q=diagnose_rate_variation(weak);assert q['state']=='unverified'
    masked=pilot();masked['weights'][:32,:,masked['pairs'][:,1]==3]=0
    assert diagnose_rate_variation(masked)['state']=='unverified'


def test_common_rate_drift_is_not_measured():
    ordinary=diagnose_rate_variation(pilot(slopes=[0.,0.,0.,0.]))
    common=diagnose_rate_variation(pilot(slopes=[10.,10.,10.,10.]))
    assert ordinary['state']==common['state']=='consistent'
    assert common['maximum_normalized_rate_difference']==pytest.approx(ordinary['maximum_normalized_rate_difference'],abs=1e-9)


def test_explicit_limitation_periodic_phase_loss_with_consistent_average_rates():
    amplitudes=np.array([0.,.2,-.3,.5]);data=pilot(count=256,noise=0.,oscillation=amplitudes)
    q=diagnose_rate_variation(data)
    assert q['state']=='consistent' and q['maximum_normalized_rate_difference']<1e-4
    # Four identical cos cycles have the same mean rate per part, but lose signal.
    assert j0(max(amplitudes)-min(amplitudes))<.9
    assert not q['coherence_stability_measured']


@pytest.mark.parametrize('options',[{'max_rate_hz':125.},{'threshold_sigma':0.},{'threshold_sigma':float('nan')}, {'reference_station':4}])
def test_invalid_diagnostic_inputs(options):
    with pytest.raises(ValueError):diagnose_rate_variation(pilot(),**options)


def test_required_policy_rejects_unverified_before_final_correlation(tmp_path):
    import json
    from vsora_correlator.closure_pipeline import process_closure_session
    from workflows.vdif_closure_validation import make_fixture
    make_fixture(tmp_path/'input',pilot_blocks=1024,rates_hz=[0.,1.,-1.,2.])
    with pytest.raises(ValueError,match='required subpilot rate consistency'):
        process_closure_session(tmp_path/'input/manifest.json',tmp_path/'input/clock.json',tmp_path/'required',
            pilot_integrations=16,integration_s=.1,max_rate_hz=25.,require_rate_consistency=True)
    q=json.loads((tmp_path/'required.partial/failure.json').read_text())
    assert q['rate_consistency']['state']=='unverified' and q['completed_steps']==['aligned_pilot']
    assert not (tmp_path/'required.partial/correlation').exists()
