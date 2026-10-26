"""同一w=0参照のnative/外部RMLを、checkout外の別processで再現する。"""
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
    p=argparse.ArgumentParser();p.add_argument('--reference',required=True);p.add_argument('--native',required=True);p.add_argument('--output',required=True);p.add_argument('--external-python',required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[1];ref=Path(a.reference).resolve();native=Path(a.native).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
    workflow=root/'workflows/ehtim_image_reference.py';env=dict(os.environ,PYTHONHASHSEED='0',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg');env.pop('PYTHONPATH',None)
    def run(args,log,cwd,success=True):
        result=subprocess.run(args,cwd=cwd,env=env,text=True,capture_output=True);(out/log).write_text(result.stdout+result.stderr)
        assert (result.returncode==0)==success,(log,result.returncode)
        return result
    with tempfile.TemporaryDirectory(prefix='vsora-rml-comparison-') as folder:
        cwd=Path(folder);assert not cwd.is_relative_to(root) and not (cwd/'tools/run.py').exists()
        probe='''import importlib,json,pathlib,sysconfig,sys
names=['vsora_imaging','vsora_formats','vsora_simulator','vsora_observation'];prefix=pathlib.Path(sysconfig.get_path('purelib'))
if sys.argv[1]=='external':names+=['ehtim','ehtim.imager']
paths={n:str(pathlib.Path(importlib.import_module(n).__file__).resolve()) for n in names};assert all(pathlib.Path(p).is_relative_to(prefix) for p in paths.values());print(json.dumps(paths))
'''
        run([sys.executable,'-c',probe,'native'],'native-prefix.log',cwd)
        foreign=str(Path(a.external_python).absolute());run([foreign,'-c',probe,'external'],'external-prefix.log',cwd)
        run([sys.executable,str(workflow),'--mode','prepare','--repository',str(root),'--output',str(out/'reference')],'prepare.log',cwd)
        left=json.loads((ref/'metadata.json').read_text());right=json.loads((out/'reference/metadata.json').read_text());assert left==right
        count=0
        with np.load(ref/'input.npz',allow_pickle=False) as x,np.load(out/'reference/input.npz',allow_pickle=False) as y:
            assert set(x.files)==set(y.files)
            for name in x.files:np.testing.assert_array_equal(x[name],y[name]);count+=1
        for name in ['truth.npy','generation-gains.npy']:np.testing.assert_array_equal(np.load(ref/name,allow_pickle=False),np.load(out/'reference'/name,allow_pickle=False));count+=1
        run([sys.executable,str(workflow),'--mode','native','--reference',str(out/'reference'),'--output',str(out/'native')],'native.log',cwd)
        assert json.loads((native/'science.json').read_text())==json.loads((out/'native/science.json').read_text())
        np.testing.assert_array_equal(np.load(native/'relative-model.npy',allow_pickle=False),np.load(out/'native/relative-model.npy',allow_pickle=False));count+=1
        for label,source in [('source',ref),('installed',out/'reference')]:
            run([foreign,str(workflow),'--mode','external','--reference',str(source),'--output',str(out/f'external-{label}')],f'external-{label}.log',cwd)
        external=[json.loads((out/f'external-{m}/science.json').read_text()) for m in ['source','installed']];assert external[0]==external[1]
        for name in ['relative-model.npy',*[f'start-{i}.npy' for i in range(3)]]:
            np.testing.assert_array_equal(np.load(out/'external-source'/name,allow_pickle=False),np.load(out/'external-installed'/name,allow_pickle=False));count+=1
        for label,r,n,e in [('source',ref,native,out/'external-source'),('installed',out/'reference',out/'native',out/'external-installed')]:
            run([sys.executable,str(workflow),'--mode','assess','--reference',str(r),'--native-output',str(n),'--external-output',str(e),'--output',str(out/f'assessment-{label}')],f'assessment-{label}.log',cwd)
        assessment=[json.loads((out/f'assessment-{m}/summary.json').read_text()) for m in ['source','installed']];assert assessment[0]==assessment[1]
        tracked=[*ref.iterdir(),*(out/'reference').iterdir(),*native.iterdir(),*(out/'native').iterdir(),*(out/'external-source').iterdir(),*(out/'external-installed').iterdir()]
        before={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked if path.is_file()}
        for mode,args in [('prepare',['--repository',str(root),'--output',str(out/'reference')]),('native',['--reference',str(ref),'--output',str(out/'native')]),('external',['--reference',str(ref),'--output',str(out/'external-source')]),('assess',['--reference',str(ref),'--native-output',str(native),'--external-output',str(out/'external-source'),'--output',str(out/'assessment-source')])]:
            result=run([foreign if mode=='external' else sys.executable,str(workflow),'--mode',mode,*args],f'nonoverwrite-{mode}.log',cwd,False);assert 'FileExistsError' in result.stderr
        assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in before.items())
        n=json.loads((native/'science.json').read_text());e=external[0]
        report={'stage':123,'state':'complete','arrays_exact':count,'all_native_science_json_equal':True,'all_external_science_json_equal':True,'all_assessment_json_equal':True,
            'native_core_prefixes':4,'external_prefixes':6,'working_directory_outside_checkout':True,'repository_runner_invoked':False,'all_four_nonoverwrite_checks':True,'all_input_and_output_bytes_unchanged':True,
            'native_initializations_each':3,'external_initializations_each':3,'native_minimize_calls_each':6,'external_minimize_calls_each':3,
            'native_selected_start':n['summary']['selected_start'],'native_selected_converged':n['summary']['runs'][n['summary']['selected_start']]['optimizer_success'],
            'external_selected_start':e['selected_start'],'external_selected_converged':e['runs'][e['selected_start']]['optimizer_success'],
            'native_converged_runs':sum(row['optimizer_success'] for row in n['summary']['runs']),'external_converged_runs':sum(row['optimizer_success'] for row in e['runs']),
            'maximum_actual_initial_image_difference':max(n['initial_image_maximum_difference'],*[r['initial_image_maximum_difference'] for r in e['runs']]),
            'w_zero_control_only':True,'physical_receiver_noise_generated':False,'actual_observation_validated':False}
        (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
