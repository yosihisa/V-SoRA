"""Check the installed paired phase experiment outside the checkout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from vsora_simulator import gaussian_phase_template as api
from vsora_observation.reference import reference_path


def tree(path):
    return {str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--reference',required=True);a=p.parse_args()
    r=Path(__file__).resolve().parents[1];out=Path(a.output);assert not out.exists()
    assert not Path.cwd().resolve().is_relative_to(r) and not (Path.cwd()/'tools/run.py').exists()
    assert 'PYTHONPATH' not in os.environ
    source=json.loads(Path(a.reference).read_text());assert source['state']=='complete' and len(source['cases'])==7
    plans=[api.case_plan(profile) for profile in ('full','smoke')]
    for i in (0,6):assert api.experiment(plans[0][i])==source['cases'][i]
    out.mkdir(parents=True,exist_ok=False);native=out/'native'
    cmd=[sys.executable,'-m','vsora_simulator.gaussian_phase_template','--output',str(native),'--profile','full']
    result=subprocess.run(cmd,capture_output=True,text=True);assert result.returncode==0,result.stderr
    installed=json.loads((native/'summary.json').read_text());assert installed==source
    for c in source['cases']:assert json.loads((native/'cases'/f"{c['case_id']}.json").read_text())==c
    before=tree(native);repeat=subprocess.run(cmd,capture_output=True,text=True);assert repeat.returncode!=0 and 'FileExistsError' in repeat.stderr;assert tree(native)==before
    modules=sorted(n for n,m in sys.modules.items() if n.startswith('vsora_') and getattr(m,'__file__',None))
    assert all(Path(sys.modules[n].__file__).is_relative_to(Path(sys.prefix)) for n in modules)
    assets=[reference_path(),reference_path('known-casa-window-symmetry.json')]
    assert all(p.is_relative_to(Path(sys.prefix)) for p in assets)
    q={'state':'complete','native_cli_all7_condition_and_summary_json_identical':True,
        'direct_api_conditions_identical':[0,6],'fixed_plans_checked':2,
        'outside_checkout':True,'pythonpath_absent':True,'runner_absent':True,
        'project_modules':modules,'project_module_count':len(modules),'all_project_modules_in_prefix':True,
        'reference_asset_count':len(assets),'all_reference_assets_in_prefix':True,
        'output_non_overwrite_verified':True,'all_native_output_bytes_unchanged_on_refusal':True}
    (out/'verification.json').write_text(json.dumps(q,indent=2)+'\n');print(json.dumps(q))


if __name__=='__main__':main()
