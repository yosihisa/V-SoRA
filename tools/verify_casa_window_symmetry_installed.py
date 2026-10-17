"""Verify packaged finite-voltage models outside a checkout, including full CLI."""
import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path


def run(reference,science_reference,output):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    script='''
import hashlib,json,sys,subprocess
from pathlib import Path
from vsora_simulator import casa_window_symmetry,bispectrum_observed_power,sky_covariance
from vsora_imaging import window_symmetry
from vsora_observation import reference
modules=(casa_window_symmetry,bispectrum_observed_power,sky_covariance,window_symmetry,reference)
assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in modules)
asset=reference.reference_path('known-casa-window-symmetry.json')
assert asset.is_relative_to(Path(sys.prefix)) and reference.reference_path().is_relative_to(Path(sys.prefix))
assert not Path('tools/run.py').exists()
fixture=json.loads(Path(sys.argv[1]).read_text())
for c in fixture['cases']:
    assert casa_window_symmetry.experiment(c['input'])==c['expected'],c['input']['case_id']
assert casa_window_symmetry.case_plan()==fixture['full_plan']
with open('native-cli.log','w') as log:
    subprocess.run([sys.executable,'-m','vsora_simulator.casa_window_symmetry','--profile','full','--output','native-result'],stdout=log,stderr=subprocess.STDOUT,check=True)
actual=json.loads(Path('native-result/summary.json').read_text());expected=json.loads(Path(sys.argv[2]).read_text())
assert actual==expected
for c in actual['cases']:
    assert json.loads((Path('native-result/cases')/(c['case_id']+'.json')).read_text())==c
print(json.dumps({'state':'complete','outside_checkout':True,'pythonpath_removed':True,'all_science_modules_and_assets_under_installed_prefix':True,'checkout_runner_used':False,'native_cli_full_profile_executed':True,'api_cases_all_fields_exact':len(fixture['cases']),'full_plan_identical':True,'scientific_conditions_all_fields_exact':len(actual['cases']),'case_files_all_fields_exact':len(actual['cases']),'configuration_sha256':hashlib.sha256(asset.read_bytes()).hexdigest(),'actual_hardware_data':False,'production_rml_noise_model_changed':False}))
'''
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-casa-symmetry-') as folder:
        r=subprocess.run([sys.executable,'-c',script,str(Path(reference).resolve()),str(Path(science_reference).resolve())],cwd=folder,env=env,capture_output=True,text=True)
        for name in ('native-cli.log',):
            p=Path(folder)/name
            if p.exists():(out/name).write_text(p.read_text())
        (out/'process.log').write_text(r.stdout+r.stderr)
        r.check_returncode()
    q=json.loads(r.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference',required=True);p.add_argument('--science-reference',required=True);p.add_argument('--output',required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
