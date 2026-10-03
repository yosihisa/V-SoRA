import numpy as np
import pytest
from workflows.rate_covariance_validation import run, shared_model, shared_pilot


def test_shared_visibility_model_preserves_mean_and_full_covariance():
    model=shared_model(.5);data=shared_pilot(42,model)
    assert data['visibilities'].shape==(128,8,6) and model['samples']==800
    assert not np.allclose(model['moments']['complex_pseudocovariance'],0)
    c=model['moments']['real_covariance']
    assert np.any(c-np.diag(np.diag(c))) and np.linalg.eigvalsh(c).min()>0


def test_finite_study_keeps_rejected_trials_and_limits(tmp_path):
    q=run(tmp_path/'study',trials=16)
    assert len(q['groups'])==8 and not q['actual_hardware_data'] and not q['physical_iq_vdif_processed']
    assert all(sum(r['states'].values())==16 for r in q['groups'])
    assert all(r['statistics_conditioned_on_accepted'] for r in q['groups'])
    assert q['groups'][3]['accepted_count']<16
    assert q['groups'][-1]['mean_mahalanobis_per_parameter']<.7
    assert (tmp_path/'study/rate-covariance.png').exists()
    for bad in (True,7,4097,16.):
        with pytest.raises(ValueError,match='integer trials'):run(tmp_path/'bad',trials=bad)
    assert not (tmp_path/'bad').exists()
