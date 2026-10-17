import copy,json
import pytest
from vsora_simulator.common_power_validation import case_plan,experiment,run


def test_fixed_synthetic_plan():
 p=case_plan();assert len(p)==9 and len({c['case_id'] for c in p})==9
 assert {c['stations'] for c in p}=={3,4,8} and all(c['center_frequency_hz']==1.42e9 for c in p)
 assert p[7]['mode']=='data_dependent_mask' and p[6]['mode']=='two_retained_blocks'
 p[0]['blocks']=999;assert case_plan()[0]['blocks']==31


def test_all_finite_iq_fft_results_and_saved_summary(tmp_path):
 q=run(tmp_path/'study')
 assert q==json.loads((tmp_path/'study/summary.json').read_text()) and len(q['cases'])==9
 assert all(c['ordinary_visibility_arrays_bit_identical'] for c in q['cases'])
 assert all(c['maximum_chunk_blocks_seen']==min(c['blocks'],c['chunk_blocks']) for c in q['cases'])
 assert q['cases'][-1]['additional_common_power_storage_bytes']==32*4*3*8
 assert q['cases'][6]['available_u3_cells']==0 and q['cases'][6]['direct_voltage_reference_cells_checked']==0
 assert q['cases'][2]['maximum_relative_power_difference_from_station_only_samples']>0
 assert q['cases'][7]['mask_generated_from_data']
 assert q['cases'][-1]['nominal_iq_duration_s']==.3 and not q['baseline_delay_and_lo_offsets_simulated']
 assert not q['raw_profile_v1_format_changed'] and not q['real_hardware_validation_performed']
 assert (tmp_path/'study/common-power.png').is_file()


@pytest.mark.parametrize('kind',['none','empty','unknown','seed','extra'])
def test_modified_fixed_case_rejected(kind):
 c=copy.deepcopy(case_plan()[0])
 if kind=='none':c=None
 elif kind=='empty':c={}
 elif kind=='unknown':c['case_id']='unknown'
 elif kind=='seed':c['seed']+=1
 elif kind=='extra':c['unknown']=True
 with pytest.raises(ValueError):experiment(c)


def test_existing_output_preserved(tmp_path):
 out=tmp_path/'old';out.mkdir();(out/'keep').write_text('old')
 with pytest.raises(FileExistsError):run(out)
 assert (out/'keep').read_text()=='old'
