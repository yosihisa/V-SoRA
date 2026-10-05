"""Run the installed scientific CLI and fixed reference outside any checkout."""
import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path


def run(output,reference):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    script='''
import hashlib,json,subprocess,sys
from pathlib import Path
from vsora_simulator import array_scale,array_shape,sky,sky_covariance,bispectrum_scale
from vsora_observation import reference
prefix=Path(sys.prefix)
modules=(array_scale,array_shape,sky,sky_covariance,bispectrum_scale,reference)
assert all(Path(m.__file__).is_relative_to(prefix) for m in modules)
config=reference.reference_path('known-array-scale-config.json');asset=reference.reference_path()
assert config.is_relative_to(prefix) and asset.is_relative_to(prefix)
expected=json.loads(Path(sys.argv[1]).read_text())
assert hashlib.sha256(config.read_bytes()).hexdigest()==expected['config_fixture_sha256']
assert hashlib.sha256(asset.read_bytes()).hexdigest()==expected['reference']['derived_sha256']
assert not Path('tools/run.py').exists()
subprocess.run([sys.executable,'-m','vsora_simulator.array_scale','--output','native-result'],capture_output=True,text=True,check=True)
actual=json.loads(Path('native-result/summary.json').read_text());assert actual==expected
print(json.dumps({'state':'complete','outside_checkout':True,'pythonpath_removed':True,'installed_scientific_modules_verified':True,'packaged_configuration_and_sky_verified':True,'native_cli_without_checkout_runner':True,'all_scientific_results_identical_to_stage081':True,'snapshots':18,'scale_cases':108,'actual_hardware_data':False,'image_inference_performed':False}))
'''
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-native-array-cli-') as folder:
        result=subprocess.run([sys.executable,'-c',script,str(Path(reference).resolve())],cwd=folder,env=env,capture_output=True,text=True,check=True)
    q=json.loads(result.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--reference',required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
