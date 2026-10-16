"""Run installed sign-symmetry APIs and native CLI outside any checkout."""
import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path


def run(reference,science_reference,output):
 out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
 script='''
import json,sys,subprocess
from pathlib import Path
import numpy as np
from vsora_imaging import window_symmetry
from vsora_simulator import window_symmetry_validation
assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (window_symmetry,window_symmetry_validation))
assert not Path('tools/run.py').exists()
fixture=json.loads(Path(sys.argv[1]).read_text())
for c in fixture['cases']:
    actual=window_symmetry.exact_window_sign_flip_test(np.asarray(c['vectors']))
    assert actual==c['expected'],c['name']
range_checks=0
if np.finfo(np.longdouble).maxexp>np.finfo(np.float64).maxexp:
    for value in ('1e400','1e-400'):
        try:window_symmetry.exact_window_sign_flip_test(np.full((8,2),np.longdouble(value),dtype=np.longdouble))
        except ValueError:range_checks+=1
        else:raise AssertionError('extended input lost in float64 conversion')
subprocess.run([sys.executable,'-m','vsora_simulator.window_symmetry_validation','--output','native-result'],capture_output=True,text=True,check=True)
actual=json.loads(Path('native-result/summary.json').read_text());expected=json.loads(Path(sys.argv[2]).read_text())
assert actual==expected
print(json.dumps({'state':'complete','outside_checkout':True,'pythonpath_removed':True,'core_and_generator_under_installed_prefix':True,'checkout_runner_used':False,'native_cli_executed':True,'all_api_fields_exact':True,'api_cases':len(fixture['cases']),'extended_precision_range_rejections_checked':range_checks,'all_scientific_results_identical_to_source':True,'vector_conditions':len(actual['cases']),'physical_voltage_processed':False,'production_rml_noise_model_changed':False}))
'''
 env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
 with tempfile.TemporaryDirectory(prefix='vsora-window-symmetry-') as folder:
  r=subprocess.run([sys.executable,'-c',script,str(Path(reference).resolve()),str(Path(science_reference).resolve())],cwd=folder,env=env,capture_output=True,text=True,check=True)
 q=json.loads(r.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--reference',required=True);p.add_argument('--science-reference',required=True);p.add_argument('--output',required=True)
 print(json.dumps(run(**vars(p.parse_args())),indent=2))
