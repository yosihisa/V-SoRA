"""独立envの外部DFT/Closureと、導入済みnativeの同一参照を照合する。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reference',required=True);parser.add_argument('--output',required=True);parser.add_argument('--external-python',required=True)
    a=parser.parse_args();root=Path(__file__).resolve().parents[1];reference=Path(a.reference).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
    workflow=root/'workflows/ehtim_conventions_validation.py';env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg');env.pop('PYTHONPATH',None)
    def run(args,log,cwd,success=True):
        result=subprocess.run(args,cwd=cwd,env=env,text=True,capture_output=True);(out/log).write_text(result.stdout+result.stderr)
        assert (result.returncode==0)==success,(log,result.returncode)
        return result
    with tempfile.TemporaryDirectory(prefix='vsora-external-conventions-') as folder:
        cwd=Path(folder);assert not cwd.is_relative_to(root) and not (cwd/'tools/run.py').exists()
        probe='''import importlib,json,pathlib,sysconfig
prefix=pathlib.Path(sysconfig.get_path('purelib')); names=['vsora_observation','vsora_formats','vsora_simulator','vsora_imaging']
paths={n:str(pathlib.Path(importlib.import_module(n).__file__).resolve()) for n in names};assert all(pathlib.Path(p).is_relative_to(prefix) for p in paths.values());print(json.dumps(paths))
'''
        run([sys.executable,'-c',probe],'native-prefix.log',cwd)
        run([sys.executable,str(workflow),'--mode','prepare','--repository',str(root),'--output',str(out/'native')],'native.log',cwd)
        source=json.loads((reference/'summary.json').read_text());installed=json.loads((out/'native/summary.json').read_text())
        source_science={k:v for k,v in source.items() if k!='reference_bundle_sha256'};installed_science={k:v for k,v in installed.items() if k!='reference_bundle_sha256'}
        assert source_science==installed_science
        with np.load(reference/'reference.npz',allow_pickle=False) as left,np.load(out/'native/reference.npz',allow_pickle=False) as right:
            assert set(left.files)==set(right.files)
            for name in left.files:np.testing.assert_array_equal(left[name],right[name])
            arrays=len(left.files)
        external_python=str(Path(a.external_python).absolute())
        run([external_python,str(workflow),'--mode','external','--reference',str(reference),'--output',str(out/'external')],'external.log',cwd)
        external=json.loads((out/'external/verification.json').read_text());assert external['state']=='complete'
        # 既存directoryへの再実行は原本を変えず失敗する。
        files=[*reference.iterdir(),*(out/'native').iterdir(),*(out/'external').iterdir()]
        before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}
        failure=run([sys.executable,str(workflow),'--mode','prepare','--repository',str(root),'--output',str(out/'native')],'native-nonoverwrite.log',cwd,False);assert 'FileExistsError' in failure.stderr
        failure=run([external_python,str(workflow),'--mode','external','--reference',str(reference),'--output',str(out/'external')],'external-nonoverwrite.log',cwd,False);assert 'FileExistsError' in failure.stderr
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in before.items())
        result={'stage':122,'state':'complete','native_source_installed_all_science_json_equal':True,'native_arrays_exact':arrays,'source_and_installed_bundle_bytes_equal':source['reference_bundle_sha256']==installed['reference_bundle_sha256'],'native_core_module_prefixes':4,'external_module_prefixes':external['external_module_prefixes_checked'],'outside_checkout_without_runner':True,'all_nonoverwrite_checks_passed':True,'all_input_bytes_unchanged':True,'external_version':external['external_version'],'dft_cases':len(external['dft_cases']),'dft_frequency_comparisons':source['dft_frequency_comparisons'],'closure_cases':len(external['closure_cases']),'maximum_dft_absolute_difference':max(x['maximum_abs_difference'] for x in external['dft_cases']),'maximum_closure_value_difference':max(x['maximum_value_difference'] for x in external['closure_cases']),'maximum_closure_sigma_difference':max(x['maximum_sigma_difference'] for x in external['closure_cases']),'w_comparisons':len(source['w_comparisons']),'maximum_w_phase_bound_rad':max(x['maximum_phase_rad'] for x in source['w_comparisons']),'maximum_w_normalized_visibility_bound':max(x['normalized_visibility_absolute_bound'] for x in source['w_comparisons']),'maximum_w_measured_model_difference':max(x['maximum_normalized_model_visibility_difference'] for x in source['w_comparisons']),'explicit_equal_time_dtype_adapter_used':True,'external_source_files_patched':False,'actual_observation_validated':False}
        (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
