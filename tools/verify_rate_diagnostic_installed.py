"""Installed diagnostic CLI and required-policy stop outside checkout."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def run(reference_run,output):
    from vsora_correlator import rate_variation
    assert Path(rate_variation.__file__).is_relative_to(Path(sys.prefix))
    base=Path(reference_run).resolve();out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    rows=[]
    with tempfile.TemporaryDirectory(prefix='vsora-diagnostic-installed-') as cwd:
        for case in ('control-3s','control-short','moderate-3s','strong-3s','strong-short'):
            directory=base/(case+'.partial' if case=='strong-3s' else case)
            destination=out/(case+'.json')
            result=subprocess.run([str(Path(sys.prefix)/'bin/vsora-rate-diagnose'),
                '--input',str(directory/'pilot/shard-00000.npz'),'--output',str(destination)],
                cwd=cwd,env=env,capture_output=True,text=True)
            assert result.returncode==0,'installed diagnostic CLI failed'
            q=json.loads(destination.read_text());expected=rate_variation.diagnose_rate_shard(directory/'pilot/shard-00000.npz')
            assert q==expected
            rows.append({'case':case,'state':q['state'],'input_sha256':q['input_sha256'],
                         'maximum_normalized_rate_difference':q['maximum_normalized_rate_difference']})
        result=subprocess.run([str(Path(sys.prefix)/'bin/vsora-closure-session'),
            '--manifest',str(base/'moderate/manifest.json'),'--clock-model',str(base/'moderate/clock.json'),
            '--pilot-integrations','1500','--integration-s','3','--correlation-only',
            '--require-rate-consistency','--output',str(out/'required')],cwd=cwd,env=env,capture_output=True,text=True)
        (out/'required.log').write_text(result.stdout+result.stderr)
        assert result.returncode!=0
        failure=json.loads((out/'required.partial/failure.json').read_text())
        assert failure['completed_steps']==['aligned_pilot'] and failure['rate_consistency']['state']=='variation_detected'
        assert not (out/'required').exists() and not (out/'required.partial/correlation').exists()
    summary={'installed_imports':True,'entrypoints_outside_checkout':True,'pilot_diagnostics':rows,
             'required_policy':{'exit_code':result.returncode,'state':failure['state'],
                'completed_steps':failure['completed_steps'],'diagnosis':failure['rate_consistency']['state'],
                'final_correlation_created':False}}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference-run',required=True);p.add_argument('--output',required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
