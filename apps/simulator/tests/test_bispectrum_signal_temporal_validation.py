import json
import numpy as np
import pytest
from workflows.bispectrum_signal_temporal_validation import time_model,experiment


@pytest.mark.parametrize('label,outputs,guard',[('white',128,1),('long_average',128,1),('reference_fft',128,1),('guarded_average',15,9),('guarded_reference',26,5)])
def test_known_model_dimensions(label,outputs,guard):
    k,q=time_model(label)
    assert k.shape==(outputs,outputs) and q['retained_outputs']==outputs and q['guard_step_outputs']==guard
    assert np.linalg.eigvalsh(k).min()>0
    np.testing.assert_allclose(k.diagonal(),1,rtol=1e-12,atol=1e-14)
    if label in ('white','guarded_average','guarded_reference'):assert q['known_temporal_covariance_is_identity']


@pytest.mark.parametrize('trials',[True,0,1023,32769,8192.5])
def test_invalid_trial_count(trials):
    with pytest.raises(ValueError,match='trials'):experiment('zero','white',trials)


@pytest.mark.parametrize('seed',[True,-1,2**32,1.5])
def test_invalid_seed(seed):
    with pytest.raises(ValueError,match='seed'):experiment('zero','white',1024,seed)


def test_unknown_time_model():
    with pytest.raises(ValueError):time_model('unknown')


@pytest.mark.parametrize('passed',[True,False])
def test_run_preserves_fixed_protocol_and_failure_record(tmp_path,monkeypatch,passed):
    from workflows import bispectrum_signal_temporal_validation as module
    calls=[]
    def case(source,time,trials,seed):
        calls.append((source,time,trials,seed));return {'all_mean_components_within_6se':passed}
    monkeypatch.setattr(module,'experiment',case);monkeypatch.setattr(module,'plot',lambda *args:None)
    out=tmp_path/'run'
    if passed:q=module.run(out)
    else:
        with pytest.raises(RuntimeError,match='criterion'):module.run(out)
    q=json.loads((out/'summary.json').read_text())
    assert q['state']==('complete' if passed else 'failed_validation') and len(q['cases'])==25
    assert [c[3] for c in calls]==list(range(72,97)) and all(c[2]==8192 for c in calls)
    assert not q['observed_bias_correction_performed'] and not q['variance_or_likelihood_calculated']
    assert not q['physical_raw_filter_convolution_performed'] and not q['production_rml_noise_model_changed']
    with pytest.raises(FileExistsError):module.run(out)
