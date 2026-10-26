"""checkout外の既存96診断CLIと比較配列の一致を確認する。"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import numpy as np


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--reference',required=True)
    p.add_argument('--record133',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    checkout=Path(__file__).resolve().parents[1];assert not Path.cwd().resolve().is_relative_to(checkout) and 'PYTHONPATH' not in os.environ and not (Path.cwd()/'tools/run.py').exists()
    spec=importlib.util.spec_from_file_location('noise_contract_helper',checkout/'workflows/saved_noise_contract_validation.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    source=Path(a.source).resolve();expected=json.loads((source/'summary.json').read_text());out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False);native=out/'study'
    helper.run(a.reference,a.record133,native,installed=True,expected=expected)
    arrays=0
    for row in expected['cells']:
        relative=Path(row['case'])/f"channel-{row['channel_index']}";left=source/relative;right=native/relative
        assert helper.sha(left/'diagnostic.json')==helper.sha(right/'diagnostic.json')==row['diagnostic_json_sha256']
        assert json.loads((left/'diagnostic.json').read_text())==json.loads((right/'diagnostic.json').read_text())
        with np.load(left/'arrays.npz',allow_pickle=False) as x,np.load(right/'arrays.npz',allow_pickle=False) as y:
            assert set(x.files)==set(y.files)
            for k in x.files:
                assert x[k].dtype==y[k].dtype and x[k].shape==y[k].shape;np.testing.assert_array_equal(x[k],y[k]);arrays+=1
    before={str(p.relative_to(native)):helper.sha(p) for p in native.rglob('*') if p.is_file()}
    try:helper.run(a.reference,a.record133,native,installed=True,expected=expected)
    except FileExistsError:pass
    else:raise AssertionError('existing diagnostic study overwritten')
    assert before=={str(p.relative_to(native)):helper.sha(p) for p in native.rglob('*') if p.is_file()}
    origins={n:m.__file__ for n,m in sys.modules.items() if n.startswith('vsora_') and getattr(m,'__file__',None)}
    assert origins and all(Path(v).is_relative_to(Path(sys.prefix)) for v in origins.values())
    q={'stage':135,'state':'complete','actual_native_diagnostic_cli_calls':96,'native_output_refusal_calls':96,
       'all_96_diagnostic_json_bytes_exact':True,'all_science_json_exact':True,'numeric_and_boolean_arrays_compared':arrays,
       'whole_study_nonoverwrite':True,'input_correlation_sha_preserved':12,'truth_read':False,'images_executed':False,
       'outside_checkout':True,'runner_absent':True,'pythonpath_absent':True,'helper_requires_checkout':True,
       'project_modules':sorted(origins),'all_project_modules_in_prefix':True,'iid_independence_or_coverage_verified':False}
    helper.write_json(out/'verification.json',q);print(json.dumps(q))


if __name__=='__main__':main()
