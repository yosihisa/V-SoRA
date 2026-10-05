import json
import numpy as np
import pytest
from workflows.bispectrum_gain_validation import four_station_example,run


def test_positive_definite_example_has_only_mean_degeneracy():
    q=four_station_example()
    assert q['all_covariances_positive_definite'] and q['population_means_identical']
    np.testing.assert_allclose(q['conventional_logamp_difference'],np.log(2),rtol=1e-12,atol=1e-12)
    assert not q['station_powers_identical'] and not q['conditional_u3_covariances_identical']
    assert 'not full distributional nonidentifiability' in q['scope']


def test_known_gain_workflow_new_json_and_plot(tmp_path):
    out=tmp_path/'validation';q=run(out)
    assert q['state']=='complete' and len(q['cases'])==6
    assert (out/'bispectrum-gain.png').read_bytes().startswith(b'\x89PNG')
    assert json.loads((out/'summary.json').read_text())==q
    assert not q['noise_likelihood_implemented'] and not q['observed_statistic_logarithms_taken']
    assert not q['extra_station_powers_or_higher_moments_used_as_constraints']
    assert all(c['same_gain_invariant_baseline_row_span'] for c in q['cases'] if c['stations']>=5)
    assert not q['cases'][1]['same_gain_invariant_baseline_row_span']
    with pytest.raises(FileExistsError):run(out)
