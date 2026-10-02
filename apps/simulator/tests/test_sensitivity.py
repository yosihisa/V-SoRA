import numpy as np
import pytest
from vsora_simulator.sensitivity import sefd_from_area,dish_area,baseline_sigma,connected,information_plan
from pathlib import Path
from vsora_observation import load_config
from workflows.compare_arrays import layout


def test_area_and_temperature_units():
    assert sefd_from_area(100.,1.)==pytest.approx(276129.8)
    assert dish_area(2.,.6)==pytest.approx(.6*np.pi)
    assert sefd_from_area(100.,dish_area(2.,.6))==pytest.approx(146491.40868,rel=1e-6)
    for temperature,area in [(0.,1.),(100.,0.),(np.nan,1.)]:
        with pytest.raises(ValueError):sefd_from_area(temperature,area)
    with pytest.raises(ValueError):dish_area(1.,1.1)


def test_baseline_noise_scaling_and_common_source_variance():
    p=np.array([[0,1]])
    assert baseline_sigma([10000.,40000.],p,1e6,1.)[0]==pytest.approx(20000/np.sqrt(2e6))
    assert baseline_sigma([10000.,40000.],p,1e6,4.,.5)[0]==pytest.approx(20000/np.sqrt(2e6))
    rng=np.random.default_rng(52);size=(4000,64)
    def gaussian():return (rng.normal(size=size)+1j*rng.normal(size=size))/np.sqrt(2)
    common=np.sqrt(1000.)*gaussian()
    x=common+np.sqrt(10000.)*gaussian();y=common+np.sqrt(10000.)*gaussian()
    estimates=(x*y.conj()).mean(axis=1)
    measured=(estimates.real.var(ddof=1)+estimates.imag.var(ddof=1))/2
    predicted=baseline_sigma([10000.,10000.],p,64.,1.,source_flux_jy=1000.)[0]**2
    assert measured/predicted==pytest.approx(1.,abs=.06)


def test_sensitivity_information_and_residual_rate():
    config=load_config(Path(__file__).resolve().parents[3]/'configs/experiments/ideal-point.json')
    config['source']['model']='casa';config['observation'].update(duration_s=14400,integration_s=120)
    config['stations']=[{'id':f'ST{i+1:02d}','enu_m':p,'sefd_jy':1e6} for i,p in enumerate(layout(8,'spread'))]
    result=information_plan(config,integration_s=.3)
    assert result['independent_closure_counts']=={'phase':0,'logamp':0}
    assert result['expected_baseline_snr']['maximum']<10
    allowed=result['maximum_residual_baseline_rate_hz_for_90pct_coherence']
    assert np.sinc(allowed*.3)==pytest.approx(.9)
    for s in config['stations']:s['sefd_jy']=1000
    bright=information_plan(config,integration_s=1.)
    assert bright['independent_closure_counts']['logamp']>0
    assert bright['recorded_exposure_per_station_s']==16.
    assert connected(np.array([[0,1],[1,2]]),3)
    assert not connected(np.array([[0,1]]),3)
