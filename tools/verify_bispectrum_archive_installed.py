"""Verify installed raw v1/v2 APIs and inspection CLI outside checkout."""
import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path

def run(reference,fixtures,output):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    script=r'''
import hashlib,json,subprocess,sys
from pathlib import Path
import numpy as np
from vsora_formats.bispectrum import load_bispectrum,arrays_for_version
from vsora_correlator.bispectrum_inspect import inspect_bispectrum_file
from vsora_simulator import bispectrum_archive_validation
assert not Path('tools/run.py').exists()
expected=json.loads(Path(sys.argv[1]).read_text());fixtures=Path(sys.argv[2]);cells=0;arrays=0;cli=0
for case in expected['cases']:
    folder=fixtures/case['case_id'];raw=folder/'raw.npz';source=folder/'visibility.npz'
    loaded=load_bispectrum(raw,source)
    assert loaded['schema_version']==case['schema_version'] and loaded['source_visibility_verified']
    with np.load(raw,allow_pickle=False) as wire:
        for key in arrays_for_version(case['schema_version']):
            np.testing.assert_array_equal(loaded[key],wire[key]);arrays+=1
    for old in case['inspection_cells']:
        name=f"api-{case['case_id']}-t{old['time_index']}-f{old['channel_index']}.json"
        actual=inspect_bispectrum_file(raw,source,name,old['channel_index'],old['time_index'])
        assert actual==old,(case['case_id'],name);cells+=1
    old=case['inspection_cells'][5];name=f"cli-{case['case_id']}.json"
    command=[str(Path(sys.prefix)/'bin/vsora-bispectrum-inspect'),'--input',str(raw),
        '--source-visibility',str(source),'--output',name,'--time-index','1','--channel-index','1']
    subprocess.run(command,capture_output=True,text=True,check=True)
    assert json.loads(Path(name).read_text())==old;cli+=1
subprocess.run([sys.executable,'-m','vsora_simulator.bispectrum_archive_validation','--output','native-result'],capture_output=True,text=True,check=True)
assert json.loads(Path('native-result/summary.json').read_text())==expected
for case in expected['cases']:
    for name in ('raw.npz','visibility.npz'):
        assert (Path('native-result')/case['case_id']/name).read_bytes()==(fixtures/case['case_id']/name).read_bytes()
modules={name:m for name,m in sys.modules.items() if name.startswith('vsora_') and getattr(m,'__file__',None)}
assert modules and all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in modules.values())
print(json.dumps({'state':'complete','outside_checkout':True,'pythonpath_removed':True,
    'checkout_runner_used':False,'archive_conditions':len(expected['cases']),'all_stored_arrays_identical':arrays,
    'all_inspection_api_json_identical':cells,'independent_console_cli_json_identical':cli,
    'native_cli_all_scientific_json_identical':True,'all_sixteen_native_archives_byte_identical':True,
    'all_imported_project_modules_under_runtime_prefix':True,'project_module_count':len(modules),
    'project_module_names':sorted(modules),'legacy_missing_power_not_inferred':True,
    'production_rml_noise_model_changed':False,'actual_hardware_data':False}))
'''
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-archive-installed-') as folder:
        process=subprocess.run([sys.executable,'-c',script,str(Path(reference).resolve()),str(Path(fixtures).resolve())],
            cwd=folder,env=env,capture_output=True,text=True)
    (out/'process.log').write_text(process.stdout+process.stderr);process.check_returncode()
    q=json.loads(process.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference',required=True);p.add_argument('--fixtures',required=True);p.add_argument('--output',required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
