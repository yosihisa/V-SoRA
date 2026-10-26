"""固定入力の外部反復・勾配診断と、source/installed後評価を照合する。"""
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
    p=argparse.ArgumentParser();p.add_argument('--reference',required=True);p.add_argument('--native',required=True);p.add_argument('--regression123',required=True);p.add_argument('--output',required=True);p.add_argument('--external-python',required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[1];ref=Path(a.reference).resolve();native=Path(a.native).resolve();old=Path(a.regression123).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ,PYTHONHASHSEED='0',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg');env.pop('PYTHONPATH',None)
    def run(args,log,cwd,environment=env,success=True):
        q=subprocess.run(args,cwd=cwd,env=environment,text=True,capture_output=True);(out/log).write_text(q.stdout+q.stderr);assert (q.returncode==0)==success,(log,q.returncode);return q
    with tempfile.TemporaryDirectory(prefix='vsora-iteration-controls-') as directory:
        cwd=Path(directory);assert not cwd.is_relative_to(root) and not (cwd/'tools/run.py').exists()
        for label,reference in [('source',ref),('installed',old/'reference')]:
            run([str(Path(a.external_python).absolute()),str(root/'workflows/ehtim_iteration_controls.py'),'--reference',str(reference),'--output',str(out/label)],label+'.log',cwd)
            e=dict(env)
            if label=='source':e['PYTHONPATH']=os.pathsep.join(map(str,[root,*sorted(root.glob('apps/*/src')),*sorted(root.glob('packages/*/src'))]))
            probe='''import importlib,pathlib,sysconfig,sys
names=['vsora_imaging','vsora_observation','vsora_simulator','vsora_formats'];base=pathlib.Path(sys.argv[2]) if sys.argv[1]=='source' else pathlib.Path(sysconfig.get_path('purelib'))
assert all(pathlib.Path(importlib.import_module(n).__file__).resolve().is_relative_to(base) for n in names)
'''
            run([sys.executable,'-c',probe,label,str(root)],label+'-prefix.log',cwd,e)
            for limit in [2000,5000]:
                run([sys.executable,str(root/'workflows/ehtim_image_reference.py'),'--mode','assess','--reference',str(reference),'--native-output',str(native if label=='source' else old/'native'),'--external-output',str(out/label/f'iterations-{limit}'),'--output',str(out/f'assessment-{label}-{limit}')],f'assessment-{label}-{limit}.log',cwd,e)
        left=json.loads((out/'source/summary.json').read_text());right=json.loads((out/'installed/summary.json').read_text());assert left==right
        arrays=0
        for limit in [2000,5000]:
            assert json.loads((out/f'assessment-source-{limit}/summary.json').read_text())==json.loads((out/f'assessment-installed-{limit}/summary.json').read_text())
            for name in ['relative-model.npy',*[f'start-{i}.npy' for i in range(3)]]:
                np.testing.assert_array_equal(np.load(out/'source'/f'iterations-{limit}'/name,allow_pickle=False),np.load(out/'installed'/f'iterations-{limit}'/name,allow_pickle=False));arrays+=1
        files=[*ref.iterdir(),*native.iterdir(),*(out/'source').rglob('*')];before={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files if f.is_file()}
        q=run([str(Path(a.external_python).absolute()),str(root/'workflows/ehtim_iteration_controls.py'),'--reference',str(ref),'--output',str(out/'source')],'nonoverwrite.log',cwd,success=False);assert 'FileExistsError' in q.stderr
        assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in before.items())
        states=[state for limit in left['limits'] for run in limit['runs'] for state in [run['initial_gradient'],run['final_gradient']]]
        report={'stage':124,'state':'complete','all_external_science_json_equal':True,'all_source_installed_assessment_json_equal':True,'images_exact':arrays,'new_iteration_limits':[2000,5000],'initializations_each':3,
            'gradient_states':len(states),'primary_gradient_states_passed':sum(x['all_primary_passed'] for x in states),'primary_gradient_states_failed':sum(not x['all_primary_passed'] for x in states),
            'maximum_primary_normalized_error':max(x['maximum_primary_normalized_error'] for x in states),'maximum_secondary_normalized_error':max(x['maximum_secondary_normalized_error'] for x in states),
            'secondary_diagnostic_changes_primary_verdict':False,'source_core_prefixes':4,'installed_core_prefixes':4,'cwd_outside_checkout':True,'repository_runner_invoked':False,'nonoverwrite_and_all_bytes_unchanged':True,
            'converged_runs_by_limit':{str(x['max_iterations']):sum(r['optimizer_success'] for r in x['runs']) for x in left['limits']},'actual_observation_validated':False}
        (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
