"""Verify installed common-power accumulators and native FFT study outside checkout."""
import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path


def run(reference,science_reference,output):
 out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
 script='''
import json,subprocess,sys
from pathlib import Path
import numpy as np
from vsora_correlator.bispectrum_accumulator import BispectrumAccumulator
from vsora_correlator.bispectrum_power import normalize_common_power_bispectrum
from vsora_simulator import common_power_validation
assert not Path('tools/run.py').exists()
def encode(v):
 if isinstance(v,np.ndarray):return {'complex_real_imag':np.stack((v.real,v.imag),axis=-1).tolist()} if np.iscomplexobj(v) else {'array':v.tolist(),'dtype':str(v.dtype)}
 if isinstance(v,dict):return {k:encode(x) for k,x in v.items()}
 return v
fixture=json.loads(Path(sys.argv[1]).read_text())
for c in fixture['cases']:
 values=np.asarray(c['voltages_real_imag']);x=values[...,0]+1j*values[...,1];mask=np.asarray(c['valid'],bool)
 a=BispectrumAccumulator(x.shape[-1],x.shape[1])
 for start in range(0,len(x),c['chunk_blocks']):a.consume(x[start:start+c['chunk_blocks']],mask[start:start+c['chunk_blocks']])
 raw=a.finish();assert encode(raw)==c['expected_raw'],c['name']
 assert encode(normalize_common_power_bispectrum(raw))==c['expected_normalized'],c['name']
modules={name:m for name,m in sys.modules.items() if name.startswith('vsora_') and getattr(m,'__file__',None)}
assert modules and all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in modules.values())
subprocess.run([sys.executable,'-m','vsora_simulator.common_power_validation','--output','native-result'],capture_output=True,text=True,check=True)
actual=json.loads(Path('native-result/summary.json').read_text());expected=json.loads(Path(sys.argv[2]).read_text());assert actual==expected
print(json.dumps({'state':'complete','outside_checkout':True,'pythonpath_removed':True,'checkout_runner_used':False,'api_cases_all_raw_and_normalized_fields_identical':len(fixture['cases']),'all_imported_project_modules_under_runtime_prefix':True,'project_module_count':len(modules),'project_module_names':sorted(modules),'native_cli_executed':True,'all_scientific_fields_identical_to_source':True,'synthetic_fft_conditions':len(actual['cases']),'short_window_iq_duration_s':actual['cases'][-1]['nominal_iq_duration_s'],'raw_profile_v1_format_changed':False,'production_rml_noise_model_changed':False,'real_hardware_validation_performed':False}))
'''
 env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
 with tempfile.TemporaryDirectory(prefix='vsora-common-power-installed-') as folder:
  r=subprocess.run([sys.executable,'-c',script,str(Path(reference).resolve()),str(Path(science_reference).resolve())],cwd=folder,env=env,capture_output=True,text=True)
 (out/'process.log').write_text(r.stdout+r.stderr);r.check_returncode()
 q=json.loads(r.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--reference',required=True);p.add_argument('--science-reference',required=True);p.add_argument('--output',required=True);print(json.dumps(run(**vars(p.parse_args())),indent=2))
