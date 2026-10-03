import copy
import hashlib
import json
from itertools import combinations
import numpy as np
import pytest
from vsora_correlator.time_scatter import diagnose_time_scatter,diagnose_time_file,time_power_moments
from vsora_formats.spectral import save_spectral


def fixture(nt=64,rho=.3):
    pairs=np.array(list(combinations(range(4),2)));t=.003+np.arange(nt)*.002
    v=np.full((nt,1,6),complex(rho));power=np.full((nt,1,4),1.)
    return dict(visibilities=v,weights=np.ones(v.shape),pairs=pairs,times_s=t,
        frequencies_hz=np.array([1.42e9]),uvw_lambda=np.zeros((*v.shape,3)),integration_s=np.full(nt,.002),
        valid_fft_count=np.full((nt,6),128),diagnostic_station_valid_fft_count=np.full((nt,4),128),
        diagnostic_station_power=power,diagnostic_station_flags=np.zeros((nt,1,4),int),
        metadata={'visibility_unit':'ADC^2','diagnostic_power_unit':'ADC^2','time_origin_utc':'2026-10-04T00:00:00Z',
            'config':{'stations':[{'id':f'ST{i+1:02d}'} for i in range(4)]},'rate_profile_type':None,
            'rate_applied_hz':[0]*4,'rate_applied_slopes_hz_per_s':[0]*4})


def profile(data,linear=False):
    return dict(schema_version=1,type='station_rate_linear' if linear else 'station_rate_only',
        station_ids=['ST01','ST02','ST03','ST04'],station_indices=list(range(4)),
        time_origin_utc=data['metadata']['time_origin_utc'],station_rates_hz=[0,7,-3,2],
        station_rate_slopes_hz_per_s=[0,.2,-.4,.3],time_reference_s=float(np.mean(data['times_s'])),
        valid_time_range_s=[float(data['times_s'][0]),float(data['times_s'][-1])],
        sample_cadence_s=.002,max_baseline_rate_hz=100,temporal_nyquist_hz=250)


def test_constant_moments_unbounded_ratio_and_units():
    data=fixture();q=diagnose_time_scatter(data,0)
    assert q['state']=='conditional_estimate' and q['power_unit']=='ADC^4'
    # A particular noiseless-looking sample still has a conditional noise estimate.
    assert all(x['mean_to_time_power_ratio_unbounded']>1 for x in q['baselines'])
    assert not q['ratio_clipped_to_physical_interval'] and not q['hardware_coherence_measured']
    assert not q['production_rml_noise_model_changed'] and not q['generating_truth_used']
    m=128;nu=(m-.3**2)/(m*m-1)
    x=q['baselines'][0]
    assert x['noise_subtracted_time_power']==pytest.approx(.09-nu)
    assert x['noise_subtracted_mean_power']==pytest.approx(.09-nu/64)
    assert x['excess_time_scatter']==pytest.approx(-nu*(1-1/64))


@pytest.mark.parametrize('linear',[False,True])
def test_center_profile_rotation_sign_and_no_input_mutation(linear):
    data=fixture();p=profile(data,linear);tau=data['times_s']-p['time_reference_s']
    phase=2*np.pi*(tau[:,None]*p['station_rates_hz']+(.5*tau[:,None]**2*np.array(p['station_rate_slopes_hz_per_s']) if linear else 0))
    pairs=data['pairs'];data['visibilities'][:,0]*=np.exp(1j*(phase[:,pairs[:,0]]-phase[:,pairs[:,1]]))
    before=data['visibilities'].copy();q=diagnose_time_scatter(data,0,p)
    np.testing.assert_array_equal(before,data['visibilities'])
    for row in q['baselines']:
        assert row['mean_visibility_real']==pytest.approx(.3,abs=1e-14)
        assert row['mean_visibility_imag']==pytest.approx(0,abs=1e-14)
    assert q['additional_center_rotation_applied']
    assert not q['rate_profile_fit_dependence_calibrated']


def test_fixed_station_gain_preserves_power_ratio():
    data=fixture();before=diagnose_time_scatter(data,0)
    gain=np.array([.4,3,1.5,.75])*np.exp(1j*np.array([.3,-1,2,1.1]));pairs=data['pairs']
    factor=gain[pairs[:,0]]*gain[pairs[:,1]].conj()
    data['visibilities']*=factor;data['diagnostic_station_power']*=abs(gain)**2
    after=diagnose_time_scatter(data,0)
    for i,(a,b) in enumerate(zip(before['baselines'],after['baselines'])):
        assert a['mean_to_time_power_ratio_unbounded']==pytest.approx(b['mean_to_time_power_ratio_unbounded'])
        assert b['excess_time_scatter']==pytest.approx(a['excess_time_scatter']*abs(factor[i])**2)


def test_negative_signal_power_is_unresolved_and_not_clipped():
    data=fixture(rho=0);q=diagnose_time_scatter(data,0)
    assert q['state']=='conditional_estimate'
    assert all(x['state']=='unverified' and x['noise_subtracted_time_power']<0 and x['mean_to_time_power_ratio_unbounded'] is None for x in q['baselines'])


@pytest.mark.parametrize('kind,reason',[
    ('few','time_cell_count_outside_32_to_8192'),('overlap','overlapping_time_cells'),
    ('missing','ineligible_time_cell'),('flag','ineligible_time_cell'),('mask','ineligible_time_cell'),
    ('counts','ineligible_time_cell'),('unknown','stored_rate_correction_unknown')])
def test_ineligible_series_not_selected_or_repaired(kind,reason):
    data=fixture(nt=31 if kind=='few' else 64);p=None
    if kind=='overlap':data['integration_s'][10]=.004
    elif kind=='missing':data.pop('valid_fft_count')
    elif kind=='flag':data['diagnostic_station_flags'][10,0,1]=1
    elif kind=='mask':data['weights'][10,0,1]=0
    elif kind=='counts':data['valid_fft_count'][10,0]-=1
    elif kind=='unknown':p=profile(data);data['metadata'].pop('rate_profile_type')
    q=diagnose_time_scatter(data,0,p);assert q['state']=='unverified' and q['reason']==reason
    assert 'baselines' not in q
    if kind in ('flag','mask','counts'):assert q['time_index']==10


@pytest.mark.parametrize('kind',['channel','bool','fraction','exposure','origin','identity','outside','double','nonzero'])
def test_invalid_selection_or_profile_fails(kind):
    data=fixture();p=profile(data);channel=0
    if kind=='channel':channel=1
    elif kind=='bool':channel=True
    elif kind=='fraction':channel=.5
    elif kind=='exposure':data['integration_s'][0]=0
    elif kind=='origin':p['time_origin_utc']='2026-10-03T00:00:00Z'
    elif kind=='identity':p['station_ids'][0]='OTHER'
    elif kind=='outside':p['valid_time_range_s'][1]-=.01
    elif kind=='double':data['metadata']['rate_profile_type']='station_rate_only'
    elif kind=='nonzero':data['metadata']['rate_applied_hz'][1]=1
    with pytest.raises(ValueError):diagnose_time_scatter(data,channel,p)


@pytest.mark.parametrize('kind',['real_visibility','negative_noise','complex_noise','shape','few','nonfinite'])
def test_moment_parameters(kind):
    z=np.ones((32,2),complex);nu=np.ones(z.shape)
    if kind=='real_visibility':z=z.real
    elif kind=='negative_noise':nu[0,0]=-1
    elif kind=='complex_noise':nu=nu.astype(complex)
    elif kind=='shape':nu=nu[:,:1]
    elif kind=='few':z=z[:31];nu=nu[:31]
    elif kind=='nonfinite':z[0,0]=np.nan
    with pytest.raises(ValueError):time_power_moments(z,nu)


def test_file_closed_identity_profile_and_no_overwrite(tmp_path):
    data=fixture();p=profile(data);meta=data.pop('metadata');source=tmp_path/'input.npz'
    save_spectral(source,data,meta);profile_path=tmp_path/'rate.json';profile_path.write_text(json.dumps(p))
    output=tmp_path/'result.json';q=diagnose_time_file(source,output,0,profile_path)
    assert q==json.loads(output.read_text())
    assert q['input_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    assert q['rate_profile_sha256']==hashlib.sha256(profile_path.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):diagnose_time_file(source,output,0,profile_path)
    with pytest.raises(ValueError):diagnose_time_file(source,tmp_path/'wrong.npz',0)


def test_gaussian_voltage_ensembles_and_weak_unbounded_statistics():
    from workflows.time_scatter_validation import experiment
    for kind in ('constant','periodic_phase','amplitude','weak'):
        q=experiment(kind,trials=256,seed=51)
        assert q['all_power_means_within_6se']
        assert not q['generating_truth_used_by_power_estimator']
        if kind=='weak':assert max(q['nonpositive_time_power_fraction'])>.1
        if kind=='periodic_phase':assert q['powers']['excess']['target'][-1]>.02


def test_missing_old_archive_and_changed_input(tmp_path,monkeypatch):
    import vsora_correlator.time_scatter as module
    data=fixture();data.pop('valid_fft_count');meta=data.pop('metadata');source=tmp_path/'old.npz'
    save_spectral(source,data,meta)
    q=diagnose_time_file(source,tmp_path/'old.json',0)
    assert q['state']=='unverified' and q['cell_reason']=='missing_station_power_flags_or_fft_counts'
    reader=module.load_spectral
    def mutate(path):
        value=reader(path)
        with path.open('ab') as stream:stream.write(b'changed')
        return value
    monkeypatch.setattr(module,'load_spectral',mutate)
    with pytest.raises(ValueError,match='changed'):diagnose_time_file(source,tmp_path/'changed.json',0)


def test_baseline_exposure_shape_and_differences():
    data=fixture();data['integration_s']=np.tile(data['integration_s'][:,None],(1,6))
    assert diagnose_time_scatter(data,0)['state']=='conditional_estimate'
    data['integration_s'][10,0]*=.5
    assert diagnose_time_scatter(data,0)['reason']=='baseline_exposures_differ'


def test_actual_aligned_vdif_native_exposure_shape(tmp_path):
    from workflows.vdif_closure_validation import make_fixture
    from vsora_correlator.aligned import correlate_aligned
    from vsora_formats.spectral import load_spectral
    make_fixture(tmp_path/'input',51,rates_hz=[0,0,0,0],frame_count=160)
    correlate_aligned(tmp_path/'input/manifest.json',tmp_path/'input/clock.json',tmp_path/'pilot',32)
    data=load_spectral(tmp_path/'pilot/shard-00000.npz')
    assert data['integration_s'].shape==(32,6)
    assert diagnose_time_scatter(data,16)['state']=='conditional_estimate'
