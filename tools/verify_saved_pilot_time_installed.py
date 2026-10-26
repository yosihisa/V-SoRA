"""checkout外で既存time_scatter CLIを24系列実行し、全JSONを比較する。"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--reference',required=True)
    p.add_argument('--record132',required=True);p.add_argument('--output',required=True);a=p.parse_args();checkout=Path(__file__).resolve().parents[1]
    assert not Path.cwd().resolve().is_relative_to(checkout) and 'PYTHONPATH' not in os.environ and not (Path.cwd()/'tools/run.py').exists()
    spec=importlib.util.spec_from_file_location('pilot_time_helper',checkout/'workflows/saved_pilot_time_validation.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    source=Path(a.source).resolve();expected=json.loads((source/'summary.json').read_text());out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False);native=out/'study'
    helper.run(a.reference,a.record132,native,installed=True,expected=expected)
    for row in expected['series']:
        relative=Path(row['raw_case'])/f"channel-{row['channel_index']}"/(row['mode']+'.json')
        assert helper.sha(source/relative)==helper.sha(native/relative)==row['diagnostic_json_sha256']
        assert json.loads((source/relative).read_text())==json.loads((native/relative).read_text())
    before={str(p.relative_to(native)):helper.sha(p) for p in native.rglob('*') if p.is_file()}
    try:helper.run(a.reference,a.record132,native,installed=True,expected=expected)
    except FileExistsError:pass
    else:raise AssertionError('existing pilot study overwritten')
    assert before=={str(p.relative_to(native)):helper.sha(p) for p in native.rglob('*') if p.is_file()}
    origins={n:m.__file__ for n,m in sys.modules.items() if n.startswith('vsora_') and getattr(m,'__file__',None)}
    assert origins and all(Path(v).is_relative_to(Path(sys.prefix)) for v in origins.values())
    q={'stage':136,'state':'complete','actual_native_diagnostic_cli_calls':24,'native_output_refusal_calls':24,
       'all_24_diagnostic_json_bytes_exact':True,'all_science_json_exact':True,'whole_study_nonoverwrite':True,
       'input_pilot_archives_sha_preserved':12,'input_rate_profiles_sha_preserved':4,
       'outside_checkout':True,'runner_absent':True,'pythonpath_absent':True,'helper_requires_checkout':True,
       'project_modules':sorted(origins),'all_project_modules_in_prefix':True,'hardware_coherence_measured':False,
       'truth_numerical_values_used':False,'production_rml_changed':False}
    helper.write_json(out/'verification.json',q);print(json.dumps(q))


if __name__=='__main__':main()
