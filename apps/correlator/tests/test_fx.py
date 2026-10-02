import numpy as np
from vsora_correlator.fx import fx_correlate
from vsora_simulator.iq import generate_iq
from vsora_simulator.visibility import direct_visibility


def test_common_signal_against_time_domain_power():
    rng=np.random.default_rng(5)
    x=rng.normal(size=65536)+1j*rng.normal(size=65536)
    gains=np.array([1,2j,.5-1j])
    result=fx_correlate(gains[:,None]*x[None,:],2048000,64)
    for b,(i,j) in enumerate(result['pairs']):
        expected=gains[i]*gains[j].conj()*np.mean(abs(x)**2)
        assert abs(result['vis_jy'][:,b].mean()-expected)<1e-12


def test_station_delay_correction_and_covariance():
    uvw=np.array([[200.,300.,-100.],[400,-200,50],[200,-500,150]])
    pairs=np.array([[0,1],[0,2],[1,2]])
    image=np.zeros((32,32));image[18,14]=1000
    delays=np.array([0,2.3/2048000,-1.7/2048000])
    x,expected=generate_iq(uvw,pairs,image,16,[0,0,0],2048000,1.42e9,64,2048,2,delays)
    wrong=fx_correlate(x,2048000,64)
    right=fx_correlate(x,2048000,64,delay_s=delays)
    assert np.linalg.norm(right['vis_jy']-expected)/np.linalg.norm(expected)<.04
    assert np.linalg.norm(wrong['vis_jy']-expected)/np.linalg.norm(expected)>.5


def test_invalid_samples_are_excluded_per_baseline():
    x=np.ones((3,128),complex)
    valid=np.ones_like(x,bool);valid[0,:64]=False
    result=fx_correlate(x,2048000,64,valid=valid)
    np.testing.assert_array_equal(result['valid_fft_count'],[1,1,2])
    valid[:]=False
    assert (fx_correlate(x,2048000,64,valid=valid)['valid_fft_count']==0).all()
