"""Verify known-C public API and full native CLI outside the checkout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from PIL import Image
from vsora_simulator import gaussian_template_validation as study
from vsora_observation.reference import reference_path


def run(reference, api_reference, output):
    checkout=Path(__file__).resolve().parents[1]
    assert not Path.cwd().resolve().is_relative_to(checkout)
    assert 'PYTHONPATH' not in os.environ
    expected=json.loads(Path(reference).read_text())
    gold=json.loads(Path(api_reference).read_text())
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    for row in gold['error_cases']:
        assert study.known_model_error_summary(row['errors'],row['trials'])==row['result']
    assert study.case_plan()==gold['full_plan'] and study.case_plan('smoke')==gold['smoke_plan']
    env=os.environ.copy();env.pop('PYTHONPATH',None)
    env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-gaussian-template-cli-') as folder:
        workspace=Path(folder);assert not (workspace/'tools/run.py').exists()
        command=[sys.executable,'-m','vsora_simulator.gaussian_template_validation','--profile','full','--output',str(out/'native')]
        with (out/'native-cli.log').open('w') as log:
            result=subprocess.run(command,cwd=workspace,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
        assert result.returncode==0
        actual=json.loads((out/'native/summary.json').read_text())
        assert actual==expected and actual['state']=='complete' and len(actual['cases'])==9
        assert actual['independent_voltage_windows_generated']==9216
        for case in expected['cases']:
            assert json.loads((out/'native/cases'/f"{case['case_id']}.json").read_text())==case
        def hashes():
            return {str(p.relative_to(out/'native')):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (out/'native').rglob('*') if p.is_file()}
        before=hashes()
        second=subprocess.run(command,cwd=workspace,env=env,capture_output=True,text=True,timeout=30)
        assert second.returncode!=0 and hashes()==before
    modules=sorted(n for n,m in sys.modules.items() if n.startswith('vsora_') and getattr(m,'__file__',None))
    assert all(Path(sys.modules[n].__file__).is_relative_to(Path(sys.prefix)) for n in modules)
    assets=('casa-template-jy-pixel.fits','known-casa-window-symmetry.json','known-array-scale-config.json')
    assert all(reference_path(a).is_relative_to(Path(sys.prefix)) for a in assets)
    source_png=Path(reference).parent/'known-covariance-template.png'
    assert Image.open(source_png).tobytes()==Image.open(out/'native/known-covariance-template.png').tobytes()
    q={'state':'complete','error_summary_api_cases':len(gold['error_cases']),
       'both_fixed_plans_identical':True,'full_native_cli_all_scientific_json_identical':True,
       'all_nine_case_json_files_identical':True,'native_cases':9,'independent_voltage_windows':9216,
       'plot_pixels_identical':True,'all_output_bytes_unchanged_on_second_run':True,
       'all_project_modules_under_runtime_prefix':True,'project_module_count':len(modules),'project_modules':modules,
       'all_configuration_and_sky_assets_under_runtime_prefix':True,'asset_count':len(assets),
       'api_and_cli_cwd_outside_checkout':True,'pythonpath_removed':True,'workspace_has_checkout_runner':False}
    (out/'summary.json').write_text(json.dumps(q,indent=2)+'\n')
    return q


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('reference','api-reference','output'):p.add_argument('--'+name,required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
