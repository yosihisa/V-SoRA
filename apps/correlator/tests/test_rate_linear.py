import copy
import numpy as np
import pytest
from vsora_correlator.rate_linear import fit_linear_parts,estimate_linear_rates,validate_linear_profile,estimate_linear_shard
from vsora_correlator.rate import estimate_rate_shard
from workflows.rate_variation_validation import pilot


def parts(slopes=(0.,.1,-.05,.15)):
    rates=np.array([0.,17.,-11.,26.]);slopes=np.array(slopes);epoch=1.5;rows=[]
    for i in range(4):
        t=(i+.5)*.75
        rows.append({'state':'complete','start_s':i*.75,'end_s':(i+1)*.75,
            'time_reference_s':t,'station_rates_hz':(rates+slopes*(t-epoch)).tolist(),
            'covariance_station_order':[1,2,3],
            'station_covariance_hz2':[[.002,.0005,.0003],[.0005,.001,.0002],[.0003,.0002,.003]]})
    return {'station_indices':[0,1,2,3],'reference_station':0,'subpilots':rows}


def profile():
    q=fit_linear_parts(parts());q.update(station_ids=['A','B','C','D'],time_origin_utc='2026-10-03T00:00:00Z',
        valid_time_range_s=[.001,2.999],sample_cadence_s=.002,max_baseline_rate_hz=100.,temporal_nyquist_hz=250.)
    return q


def test_covariance_and_exact_linear_rates():
    q=fit_linear_parts(parts())
    np.testing.assert_allclose(q['station_rates_hz'],[0,17,-11,26],atol=1e-12)
    np.testing.assert_allclose(q['station_rate_slopes_hz_per_s'],[0,.1,-.05,.15],atol=1e-12)
    assert q['linear_model_reduced_chisq']<1e-20 and q['linear_model_degrees_of_freedom']==6
    c=np.array(q['parameter_covariance']);assert c.shape==(6,6) and np.linalg.eigvalsh(c).min()>0
    assert c[0,1]!=0 and not q['coherence_stability_measured']


def test_generated_unknown_complex_visibility():
    q=estimate_linear_rates(pilot(4,slopes=[0,2,-1,3]))
    np.testing.assert_allclose(q['station_rate_slopes_hz_per_s'],[0,2,-1,3],atol=.35)
    assert q['rate_consistency']['state']=='variation_detected'


def test_unverified_and_incompatible_and_curved_parts():
    for change,match in [(lambda q:q['subpilots'][0].update(state='unverified'),'four verified'),
                         (lambda q:q['subpilots'][1]['station_rates_hz'].__setitem__(1,20),'inconsistent'),
                         (lambda q:q['subpilots'][0].update(station_covariance_hz2=np.zeros((3,3)).tolist()),'positive definite')]:
        q=parts();change(q)
        with pytest.raises(ValueError,match=match):fit_linear_parts(q)
    with pytest.raises(ValueError,match='curvature too large'):fit_linear_parts(parts((0.,10.,-5.,15.)))
    with pytest.raises(ValueError,match='baseline rate bound'):fit_linear_parts(parts(),max_rate_hz=20.)


def test_linear_profile_coverage_order_and_values():
    q=profile();ids=q['station_ids'];origin=q['time_origin_utc']
    rates,slopes,epoch=validate_linear_profile(q,ids,origin,0.,3.)
    assert epoch==1.5 and rates.shape==slopes.shape==(4,)
    with pytest.raises(ValueError,match='extrapolation'):validate_linear_profile(q,ids,origin,-.01,3.)
    with pytest.raises(ValueError,match='extrapolation'):validate_linear_profile(q,ids,origin,0.,3.,True)
    with pytest.raises(ValueError,match='station order'):validate_linear_profile(q,ids[::-1],origin,0.,3.)
    for key,value in [('station_rate_slopes_hz_per_s',[0,np.nan,0,0]),('temporal_nyquist_hz',249.),('max_baseline_rate_hz',False)]:
        bad=copy.deepcopy(q);bad[key]=value
        with pytest.raises(ValueError):validate_linear_profile(bad,ids,origin,0.,3.)


def test_periodic_phase_counterexample_remains_invisible():
    q=estimate_linear_rates(pilot(count=256,noise=0.,oscillation=[0,.2,-.3,.5]))
    assert q['rate_consistency']['state']=='consistent'
    np.testing.assert_allclose(q['station_rate_slopes_hz_per_s'],0,atol=1e-8)
    assert not q['coherence_stability_measured']


def test_reject_prior_linear_and_missing_alignment(tmp_path):
    from vsora_formats.spectral import save_spectral
    from workflows.vdif_closure_validation import make_fixture
    from vsora_observation.config import load_config
    import json
    make_fixture(tmp_path/'input',frame_count=270)
    manifest=json.loads((tmp_path/'input/manifest.json').read_text())
    config=load_config(tmp_path/'input'/manifest['observation_config'])
    d=pilot();d.update(frequencies_hz=np.arange(8)+1.42e9,
        uvw_lambda=np.zeros((128,8,6,3)),integration_s=np.full(128,.004))
    meta={'config':config,'time_origin_utc':config['observation']['start_utc'],
        'visibility_unit':'ADC^2','phase_center_corrected':True,'clock_mapping_applied':True,
        'rate_applied_slopes_hz_per_s':[0,.1,0,0]}
    path=tmp_path/'prior.npz';save_spectral(path,d,meta)
    with pytest.raises(ValueError,match='uncorrected LO'):estimate_linear_shard(path)
    with pytest.raises(ValueError,match='prior linear'):estimate_rate_shard(path)


def test_incompatible_pipeline_settings_rejected_before_work(tmp_path):
    from vsora_correlator.closure_pipeline import process_closure_session
    with pytest.raises(ValueError,match='cannot be combined'):
        process_closure_session('missing','missing',tmp_path/'out',rate_model='linear',require_rate_consistency=True)
    assert not (tmp_path/'out.partial').exists()
