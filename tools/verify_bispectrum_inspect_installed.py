"""Installed raw bispectrum inspector CLI outside checkout."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,tempfile

SCRIPT='''
import json,subprocess,sys
from pathlib import Path
from vsora_correlator import bispectrum_inspect
assert Path(bispectrum_inspect.__file__).is_relative_to(Path(sys.prefix))
spec=json.loads(Path(sys.argv[1]).read_text());out=Path(spec['output'])
command=[str(Path(sys.prefix)/'bin/vsora-bispectrum-inspect'),'--input',spec['input'],'--source-visibility',spec['source_visibility'],
 '--output',str(out/'inspection.json'),'--time-index','0','--channel-index','10']
r=subprocess.run(command,cwd=out,capture_output=True,text=True);assert r.returncode==0,r.stderr
current=json.loads((out/'inspection.json').read_text());expected=json.loads(Path(spec['reference']).read_text())
assert current==expected and current['source_visibility_verified'] and not current['noise_covariance_estimated']
again=subprocess.run(command,cwd=out,capture_output=True,text=True);assert again.returncode!=0
print(json.dumps({'state':'complete','installed_imports':True,'outside_checkout':True,'pythonpath_removed':True,
 'installed_cli_verified':True,'source_visibility_verified':True,'frozen_inspection_json_identical':True,
 'no_overwrite_checked':True,'noise_covariance_estimated':False,'production_rml_noise_model_changed':False}))
'''


def run(output,input,source_visibility,reference):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    spec={'output':str(out),**{k:str(Path(v).resolve()) for k,v in zip(('input','source_visibility','reference'),(input,source_visibility,reference))}}
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-u3-inspect-cli-') as directory:
        folder=Path(directory);script=folder/'check.py';script.write_text(SCRIPT);options=folder/'options.json';options.write_text(json.dumps(spec))
        r=subprocess.run([sys.executable,str(script),str(options)],cwd=folder,env=env,capture_output=True,text=True)
    (out/'execution.log').write_text(r.stdout+r.stderr)
    if r.returncode:raise RuntimeError('installed raw bispectrum inspector CLI verification failed')
    q=json.loads(r.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('output','input','source-visibility','reference'):p.add_argument('--'+name,required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
