import json
import pytest
from vsora_simulator.window_symmetry_validation import experiment,run


def test_fixed_vector_suite_and_saved_results(tmp_path):
 q=run(tmp_path/'result',trials=1024)
 assert q==json.loads((tmp_path/'result/summary.json').read_text())
 assert q['state']=='complete' and len(q['cases'])==13
 assert not q['physical_voltage_generated'] and not q['source_or_shape_detection_claimed']
 assert q['cases'][-1]['joint_null_invariance_satisfied_by_generation'] is False
 assert all(r['fraction']==1 for r in q['cases'][-1]['levels'])
 assert (tmp_path/'result/window-sign-symmetry.png').is_file()


def test_existing_output_not_overwritten(tmp_path):
 out=tmp_path/'original';out.mkdir();(out/'keep').write_text('original')
 with pytest.raises(FileExistsError):run(out)
 assert (out/'keep').read_text()=='original'


@pytest.mark.parametrize('bad',[True,1023,16385,1024.,None])
def test_invalid_trials(bad):
 with pytest.raises(ValueError):experiment('normal_full_rank',4,trials=bad)


@pytest.mark.parametrize('bad',[True,-1,2**32,1.,None])
def test_invalid_seed(bad):
 with pytest.raises(ValueError):experiment('normal_full_rank',4,seed=bad)


@pytest.mark.parametrize('bad',[True,0,2,13,4.])
def test_invalid_fixed_window_setting(bad):
 with pytest.raises(ValueError):experiment('normal_full_rank',bad)


def test_unknown_model_rejected():
 with pytest.raises(ValueError):experiment('unknown',4)
