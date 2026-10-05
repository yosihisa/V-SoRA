import json
import numpy as np
import pytest
from workflows import bispectrum_known_sky_validation as workflow


@pytest.mark.parametrize('stations,kind',[(n,k) for n in (4,8) for k in ('spread','line','ring')])
def test_layout_maximum_baseline_and_station_count(stations,kind):
    p=workflow.station_layout(stations,kind)
    assert p.shape==(stations,3)
    assert np.isclose(np.linalg.norm(p[:,None]-p[None,:],axis=-1).max(),600.,rtol=1e-13)


@pytest.mark.parametrize('stations,kind',[(3,'line'),(9,'line'),(True,'line'),(4.,'line'),(4,'unknown'),(0,'spread')])
def test_invalid_layout(stations,kind):
    with pytest.raises(ValueError):workflow.station_layout(stations,kind)


def test_chunked_second_moment_and_standard_error_match_full_tensor():
    rng=np.random.default_rng(76);values=rng.normal(size=(160,3))+1j*rng.normal(size=(160,3))
    parts=np.c_[values.real,values.imag];products=parts[:,:,None]*parts[:,None,:]
    expected=products.mean(axis=0);se=products.std(axis=0,ddof=1)/np.sqrt(len(parts))
    q=workflow.moment_comparison(values,np.zeros(3,complex),expected)
    np.testing.assert_allclose(q['observed_residual_second_moment'],expected,rtol=1e-13,atol=1e-15)
    np.testing.assert_allclose(q['covariance_mc_standard_error'],se,rtol=1e-13,atol=1e-15)
    assert not q['full_trial_product_tensor_allocated'] and q['covariance_product_chunk_trials']==64


@pytest.mark.parametrize('values',[np.ones((2,1)),np.ones((1,1),complex),np.full((2,1),np.nan,dtype=complex),np.ma.array(np.ones((2,1),complex),mask=False)])
def test_invalid_trial_values(values):
    with pytest.raises(ValueError):workflow.moment_comparison(values,np.zeros(1,complex),np.eye(2))


@pytest.mark.parametrize('trials',[True,1023,32769,1024.])
def test_invalid_mc_trials(trials):
    with pytest.raises(ValueError):workflow.experiment(np.eye(4),76,trials)


@pytest.mark.parametrize('seed',[True,-1,2**32,.5])
def test_invalid_mc_seed(seed):
    with pytest.raises(ValueError):workflow.experiment(np.eye(4),seed)


@pytest.mark.parametrize('passed',[True,False])
def test_fixed_forecasts_and_failed_mc_output_preserved(tmp_path,monkeypatch,passed):
    called=[]
    def experiment(s,seed,trials):
        called.append((len(s),seed,trials))
        return {'all_means_and_covariances_within_6se':passed,'seed':seed,'samples':128}
    monkeypatch.setattr(workflow,'experiment',experiment);monkeypatch.setattr(workflow,'plot',lambda *args:None)
    out=tmp_path/'run'
    if passed:workflow.run(out)
    else:
        with pytest.raises(RuntimeError):workflow.run(out)
    q=json.loads((out/'summary.json').read_text())
    assert q['state']==('complete' if passed else 'failed_validation') and len(q['conditional_forecasts'])==144
    assert len(q['snapshots'])==12 and len(q['representative_joint_covariances'])==2
    assert called==[(4,76,8192),(4,77,8192),(8,78,8192)]
    assert q['assumed_frequency_hz']==1.42e9 and q['assumed_flux_jy']==1000.
    assert {r['independent_samples_conditional_input'] for r in q['conditional_forecasts']}=={6400,19200,64000,192000}
    assert not q['gaussian_detection_probability_calculated'] and not q['triangles_statistically_independent_assumed']
    assert q['reference']['derived_sha256']=='cb9ef1efbcd4011bcfd8ea9b6b9553f36005d08f8c9d26a65439b45e18130663'
    with pytest.raises(FileExistsError):workflow.run(out)
