from itertools import permutations
import numpy as np
import pytest
from vsora_simulator.bispectrum_sensitivity import null_bispectrum_variance,conditional_bispectrum_plan


def contraction(positive,negative):
    return sum(all(a==b for a,b in zip(positive,p)) for p in permutations(negative))


@pytest.mark.parametrize('m',[3,4,6])
def test_null_variance_matches_independent_wick_index_enumeration(m):
    triples=list(permutations(range(m),3));variance=pseudo=0
    for a,b,c in triples:
        for aa,bb,cc in triples:
            variance+=(contraction([a,cc],[c,aa])*contraction([b,aa],[a,bb])*contraction([c,bb],[b,cc]))
            pseudo+=(contraction([a,aa],[c,cc])*contraction([b,bb],[a,aa])*contraction([c,cc],[b,bb]))
    q=null_bispectrum_variance(m)
    assert variance/len(triples)**2==pytest.approx(q['complex_variance'])
    assert pseudo==0 and q['pseudo_covariance']==[0,0]
    assert q['real_variance']==q['imaginary_variance']==q['complex_variance']/2


def test_conditional_scaling_and_zero_model():
    q=conditional_bispectrum_plan(128,[.01,.02,.03],windows=16,window_seconds=.3)
    single=conditional_bispectrum_plan(128,[.01,.02,.03])
    doubled=conditional_bispectrum_plan(128,[.02,.04,.06])
    assert q['stacked_null_variance_snr']==pytest.approx(4*single['single_window_null_variance_snr'])
    assert doubled['single_window_null_variance_snr']==pytest.approx(8*single['single_window_null_variance_snr'])
    assert q['conditional_recorded_seconds']==pytest.approx(.3*q['required_identical_independent_windows'])
    assert not q['nonzero_source_variance_calculated'] and not q['actual_temporal_independence_verified']
    zero=conditional_bispectrum_plan(128,[0,.02,.03])
    assert zero['required_identical_independent_windows'] is None and zero['conditional_recorded_seconds'] is None


@pytest.mark.parametrize('m',[True,2,1000001,3.0,None])
def test_null_variance_invalid_m(m):
    with pytest.raises(ValueError):null_bispectrum_variance(m)


@pytest.mark.parametrize('kind',['shape','negative','one','nan','complex','masked','windows_bool','windows_zero','windows_large','target_bool','target_zero','target_nan','time_bool','time_small','time_large'])
def test_conditional_plan_rejections(kind):
    rho=[.01]*3;windows=1;target=5.;exposure=.3
    if kind=='shape':rho=[.01]*2
    elif kind=='negative':rho=[-.01,.01,.01]
    elif kind=='one':rho=[1,.01,.01]
    elif kind=='nan':rho=[np.nan,.01,.01]
    elif kind=='complex':rho=np.array([.01+1j]*3)
    elif kind=='masked':rho=np.ma.array(rho,mask=False)
    elif kind=='windows_bool':windows=True
    elif kind=='windows_zero':windows=0
    elif kind=='windows_large':windows=1000000001
    elif kind=='target_bool':target=True
    elif kind=='target_zero':target=0
    elif kind=='target_nan':target=np.nan
    elif kind=='time_bool':exposure=True
    elif kind=='time_small':exposure=.05
    elif kind=='time_large':exposure=4
    with pytest.raises(ValueError):conditional_bispectrum_plan(128,rho,windows,target,exposure)


def test_numeric_range_and_psd_feasibility():
    with pytest.raises(ValueError):conditional_bispectrum_plan(128,[.9,.9,0])
    with pytest.raises(ValueError):conditional_bispectrum_plan(128,[1e-100]*3)
    with pytest.raises(ValueError):conditional_bispectrum_plan(128,['0.01']*3)
    with pytest.raises(ValueError):conditional_bispectrum_plan(128,[.01]*3,target_snr=np.bool_(True))
    assert conditional_bispectrum_plan(128,[.01]*3,target_snr=1e-200)['required_identical_independent_windows']==1


def test_fixed_null_gaussian_cases():
    from workflows.bispectrum_sensitivity_validation import experiment
    for i,m in enumerate((3,8,32,128)):
        q=experiment(m,trials=512,seed=57+i)
        assert q['means_and_second_moments_within_6se']
        assert not q['observed_sample_selection_used']


def test_workflow_summary_figure_and_existing_output(tmp_path):
    from workflows.bispectrum_sensitivity_validation import run
    q=run(tmp_path/'null')
    assert len(q['null_variance_cases'])==5 and len(q['conditional_point_source_plans'])==32
    assert all(c['means_and_second_moments_within_6se'] for c in q['null_variance_cases'])
    assert not q['nonzero_source_variance_calculated'] and not q['actual_temporal_independence_verified']
    assert (tmp_path/'null/bispectrum-sensitivity.png').is_file()
    with pytest.raises(FileExistsError):run(tmp_path/'null')
