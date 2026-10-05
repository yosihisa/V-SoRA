import json
import numpy as np
import pytest
from workflows import bispectrum_joint_temporal_validation as w


@pytest.mark.parametrize('n,kind,m',[(True,'white',8),(3,'white',8),(4,'unknown',8),(4,'white',True),(4,'white',2),(4,'white',33)])
def test_invalid_coefficient_models(n,kind,m):
    with pytest.raises(ValueError):w.known_covariance(n,kind,m)


@pytest.mark.parametrize('n,cycles,m',[(True,.25,8),(3,.25,8),(4,True,8),(4,-1.,8),(4,np.nan,8),(4,2.,8),(4,.25,True),(4,.25,2)])
def test_invalid_known_phase(n,cycles,m):
    with pytest.raises(ValueError):w.known_phase(n,cycles,m)


@pytest.mark.parametrize('kind',['white','common_correlated','station_coefficients'])
def test_coefficients_have_declared_power_and_psd(kind):
    c=w.known_covariance(8,kind);matrix=c.reshape(64,64)
    np.testing.assert_allclose(matrix.diagonal().real,1.2,rtol=0,atol=1e-12)
    assert np.linalg.eigvalsh(matrix).min()>0
    phase,times,rates=w.known_phase(8,.25);np.testing.assert_allclose(abs(phase),1,atol=1e-15)
    np.testing.assert_allclose(phase,np.exp(2j*np.pi*times[:,None]*rates[None,:]),atol=0)


@pytest.mark.parametrize('seed,trials',[(True,1024),(-1,1024),(2**32,1024),(78,True),(78,1023),(78,32769)])
def test_invalid_repetition_arguments(seed,trials):
    with pytest.raises(ValueError):w.experiment(w.known_covariance(4,'white'),w.known_phase(4,0)[0],seed,trials)


@pytest.mark.parametrize('passed',[True,False])
def test_full_grid_seeds_and_failure_artifacts(tmp_path,monkeypatch,passed):
    seeds=[]
    def fake(base,phase,seed,trials):
        seeds.append(seed);changed=base*phase[:,:,None,None]*phase.conj()[None,None,:,:]
        methods={}
        for state,c in [('uncorrected',changed),('known_inverse_phase',base)]:
            q=w.joint_temporal_bispectrum_mean(c)
            methods[state]={name:{'known_mean_real_imag':np.c_[q[name+'_bispectrum_mean'].real,q[name+'_bispectrum_mean'].imag].tolist()} for name in ('ordinary','distinct')}
        return {'samples':8,'trials':trials,'seed':seed,'triangles':q['triangles'].tolist(),'methods':methods,'all_calculated_means_and_known_phase_invariance_checked':passed}
    monkeypatch.setattr(w,'experiment',fake);out=tmp_path/'result'
    if passed:q=w.run(out,1024)
    else:
        with pytest.raises(RuntimeError):w.run(out,1024)
        q=json.loads((out/'summary.json').read_text())
    assert len(q['models'])==6 and len(q['cases'])==12 and seeds==list(range(78,90))
    assert q['state']==('complete' if passed else 'failed_validation') and (out/'joint-time-bispectrum.png').is_file()
    assert not q['covariance_of_bispectrum_calculated'] and not q['observed_gain_or_clock_estimated']
    with pytest.raises(FileExistsError):w.run(out,1024)


@pytest.mark.parametrize('trials',[True,1023,32769])
def test_invalid_run_leaves_no_output(tmp_path,trials):
    out=tmp_path/'invalid'
    with pytest.raises(ValueError):w.run(out,trials)
    assert not out.exists()
