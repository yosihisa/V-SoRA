import json
import pytest
from workflows.bispectrum_observed_power_validation import experiment, run


def test_fixed_small_voltage_suite_and_result_file(tmp_path):
    result = run(tmp_path/'result', trials=1024)
    assert result == json.loads((tmp_path/'result/summary.json').read_text())
    assert result['state'] == 'complete' and len(result['cases']) == 9
    assert result['classification_performed'] is False
    assert result['production_rml_noise_model_changed'] is False
    rank3 = result['cases'][0]
    assert rank3['known_rank_one_theory']['mean_real'] == .45
    assert (tmp_path/'result/observed-power-bispectrum.png').is_file()


def test_existing_output_is_not_overwritten(tmp_path):
    target = tmp_path/'existing'; target.mkdir(); marker = target/'original.txt'; marker.write_text('keep')
    with pytest.raises(FileExistsError): run(target)
    assert marker.read_text() == 'keep'


@pytest.mark.parametrize('bad', [True, 1023, 32769, 1024., None, '1024'])
def test_invalid_trials(bad):
    with pytest.raises(ValueError): experiment('rank_one', 3, trials=bad)


@pytest.mark.parametrize('bad', [True, -1, 2**32, 1.5, None])
def test_invalid_seed(bad):
    with pytest.raises(ValueError): experiment('rank_one', 3, seed=bad)


@pytest.mark.parametrize('bad', [True, 2, 129, 3.])
def test_invalid_samples(bad):
    with pytest.raises(ValueError): experiment('rank_one', bad)


def test_unknown_model_rejected():
    with pytest.raises(ValueError): experiment('unknown', 3)
