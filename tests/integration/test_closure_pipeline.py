import json
from pathlib import Path
import numpy as np
import pytest
from vsora_correlator.closure_pipeline import process_closure_session
from vsora_correlator.rate import validate_rate_profile
from vsora_formats.spectral import load_spectral
from workflows.vdif_closure_validation import make_fixture


def test_vdif_unknown_gain_to_relative_rml_and_failure(tmp_path):
    truth=make_fixture(tmp_path/'input',23)
    result=process_closure_session(tmp_path/'input/manifest.json',tmp_path/'input/clock.json',tmp_path/'complete',
                                   starts=2,max_iterations=300)
    assert result['state']=='complete' and len(result['completed_steps'])==5
    assert np.max(abs(np.array(result['rate_estimate']['station_rates_hz'])-truth['true_rates_hz']))<.05
    assert result['rml']['input_unit']=='ADC^2' and not result['rml']['absolute_flux_measured']
    image=np.load(tmp_path/'complete/rml/relative-model.npy')
    assert abs(image.sum()-1)<1e-12 and np.isfinite(image).all()
    assert not (tmp_path/'complete.partial').exists()
    data=load_spectral(tmp_path/'complete/correlation/shard-00000.npz')
    assert data['metadata']['clock_mapping_applied'] and data['metadata']['rate_only_profile_sha256']
    assert data['metadata']['config']['source']['model']=='unknown'
    assert 'total_flux_jy' not in data['metadata']['config']['source']
    with pytest.raises(FileExistsError):process_closure_session(tmp_path/'input/manifest.json',tmp_path/'input/clock.json',tmp_path/'complete')
    # One-second final integration is beyond the pilot's valid range; no implicit extrapolation.
    with pytest.raises(ValueError,match='extrapolation'):
        process_closure_session(tmp_path/'input/manifest.json',tmp_path/'input/clock.json',tmp_path/'bad-coverage',integration_s=1)
    assert not (tmp_path/'bad-coverage').exists()
    failure=json.loads((tmp_path/'bad-coverage.partial/failure.json').read_text())
    assert failure['state']=='incomplete' and failure['completed_steps']==['aligned_pilot','model_free_rate']


def test_rate_profile_identity_and_epoch_checks():
    profile={'schema_version':1,'type':'station_rate_only','station_ids':['ST01','ST02'],
             'station_indices':[0,1],'time_origin_utc':'2026-10-02T08:00:00Z','station_rates_hz':[0,12],
             'valid_time_range_s':[.003,.513],'sample_cadence_s':.002,'time_reference_s':.258}
    rate,epoch=validate_rate_profile(profile,['ST01','ST02'],'2026-10-02T08:00:00.000Z',.002,.302)
    assert rate.tolist()==[0,12] and epoch==.258
    with pytest.raises(ValueError,match='station order'):validate_rate_profile(profile,['ST02','ST01'],profile['time_origin_utc'],.002,.3)
    with pytest.raises(ValueError,match='origin'):validate_rate_profile(profile,['ST01','ST02'],'2026-10-02T08:00:01Z',.002,.3)
    with pytest.raises(ValueError,match='values'):validate_rate_profile({**profile,'station_rates_hz':[0,float('nan')]},profile['station_ids'],profile['time_origin_utc'],.002,.3)


def test_linear_diagnostic_saved_without_altering_correlation(tmp_path):
    from vsora_correlator.aligned import correlate_aligned
    make_fixture(tmp_path/'input',38,frame_count=300,rate_slopes_hz_per_s=[0.,1.,-.5,1.5])
    result=process_closure_session(tmp_path/'input/manifest.json',tmp_path/'input/clock.json',tmp_path/'complete',
        integration_s=.3,correlation_only=True,rate_model='linear')
    diagnostic=result['rate_estimate']['integration_uncertainty']
    assert diagnostic['type']=='linear_rate_uncertainty' and diagnostic['integration_s']==pytest.approx(.3)
    assert not diagnostic['coherence_stability_measured']
    original=json.loads((tmp_path/'complete/rate-linear.json').read_text())
    assert original['integration_uncertainty']==diagnostic
    original.pop('integration_uncertainty')
    profile=tmp_path/'without-diagnostic.json';profile.write_text(json.dumps(original))
    correlate_aligned(tmp_path/'complete/final-manifest.json',tmp_path/'input/clock.json',tmp_path/'comparison',
        1,.002,profile)
    a=load_spectral(tmp_path/'complete/correlation/shard-00000.npz')
    b=load_spectral(tmp_path/'comparison/shard-00000.npz')
    for key in a:
        if isinstance(a[key],np.ndarray):np.testing.assert_array_equal(a[key],b[key])
