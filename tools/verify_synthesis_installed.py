"""Verify the installed synthesis entry point outside the source checkout."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def run(inputs,output):
    from vsora_imaging import synthesis
    assert Path(synthesis.__file__).is_relative_to(Path(sys.prefix)), 'installed package required'
    out=Path(output).resolve();paths=[str(Path(x).resolve()) for x in inputs]
    environment=os.environ.copy();environment.pop('PYTHONPATH',None)
    environment.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-synthesis-') as directory:
        command=[str(Path(sys.executable).parent/'vsora-synthesis'),'--inputs',*paths,
                 '--output',str(out),'--starts','1','--max-iterations','100']
        result=subprocess.run(command,cwd=directory,env=environment,capture_output=True,text=True,check=True)
    summary=json.loads(result.stdout)
    assert summary['rml']['input_unit']=='ADC^2'
    assert abs(summary['rml']['image_sum']-1)<1e-12
    record={'installed_package_confirmed':True,'outside_checkout_cli':'complete',
        'input_count':summary['synthesis']['input_count'],'unit':summary['rml']['input_unit'],
        'image_sum':summary['rml']['image_sum'],
        'independent_closure_counts':summary['rml']['independent_closure_counts'],
        'scope':'Entry point and unit/constraints; not optimizer convergence validation'}
    (out/'installed-check.json').write_text(json.dumps(record,indent=2)+'\n');return record


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',nargs='+',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(run(a.inputs,a.output),indent=2))
