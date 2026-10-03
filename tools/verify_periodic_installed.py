"""Installed production CLI on archived fast/slow periodic phase VDIF."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,tempfile
import numpy as np


def run(source_run,output):
    from vsora_correlator import closure_pipeline
    from vsora_formats.spectral import load_spectral
    assert Path(closure_pipeline.__file__).is_relative_to(Path(sys.prefix))
    base=Path(source_run).resolve();out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    source=json.loads((base/'summary.json').read_text());records=[]
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-periodic-installed-') as cwd:
        for case in ('fast','slow'):
            expected=next(r for r in source['cases'] if r['case']==case and r['rate_model']=='linear')
            result=subprocess.run([str(Path(sys.prefix)/'bin/vsora-closure-session'),
                '--manifest',str(base/(case+'-input')/'manifest.json'),'--clock-model',str(base/(case+'-input')/'clock.json'),
                '--pilot-integrations','1500','--integration-s','3','--rate-model','linear','--correlation-only',
                '--output',str(out/case)],cwd=cwd,env=env,capture_output=True,text=True)
            (out/(case+'.log')).write_text(result.stdout+result.stderr)
            if expected['state']=='complete':
                assert result.returncode==0
                q=json.loads((out/case/'summary.json').read_text());differences={}
                a=load_spectral(base/(case+'-linear')/'correlation/shard-00000.npz')
                b=load_spectral(out/case/'correlation/shard-00000.npz')
                for key,value in a.items():
                    if not isinstance(value,np.ndarray):continue
                    np.testing.assert_array_equal(value,b[key])
                    if np.issubdtype(value.dtype,np.inexact):differences[key]=float(abs(value-b[key]).max())
                records.append({'case':case,'state':q['state'],'diagnosis':q['rate_consistency']['state'],
                    'rate_estimate':q['rate_estimate'],'maximum_absolute_source_array_differences':differences})
            else:
                assert result.returncode!=0
                failure=json.loads((out/(case+'.partial')/'failure.json').read_text())
                assert failure['rate_consistency']['state']==expected['diagnosis']['state']
                assert not (out/case).exists() and not (out/(case+'.partial')/'correlation').exists()
                records.append({'case':case,'state':failure['state'],'diagnosis':failure['rate_consistency']['state'],
                    'completed_steps':failure['completed_steps'],'final_correlation_created':False})
    summary={'installed_imports':True,'entrypoint_outside_checkout':True,'cases':records,
        'scope':'Same deterministic periodic phase synthetic VDIF. Completeness/source array check, not measured hardware coherence or image fidelity.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-run',required=True);p.add_argument('--output',required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
