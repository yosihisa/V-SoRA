"""Exercise installed seek/sequential aligned CLI outside the checkout."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np


def run(manifest,clock,rate,reference,output):
    from vsora_formats import vdif
    from vsora_formats.spectral import load_spectral
    from vsora_correlator import aligned
    if not all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (vdif,aligned)):
        raise AssertionError('installed wheel imports required')
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    inputs=list(map(lambda p:str(Path(p).resolve()),[manifest,clock,rate]))
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    expected=load_spectral(reference);rows=[]
    with tempfile.TemporaryDirectory(prefix='vsora-installed-seek-') as directory:
        for mode in ['seek','sequential']:
            command=[str(Path(sys.prefix)/'bin/vsora-correlate'),'correlate-aligned','--manifest',inputs[0],
                '--clock-model',inputs[1],'--rate-profile',inputs[2],'--start-offset-s','2.502',
                '--integrations','1','--output',str(out/mode)]
            if mode=='sequential':command.append('--sequential-input')
            result=subprocess.run(command,cwd=directory,env=env,capture_output=True,text=True)
            (out/(mode+'.log')).write_text(result.stdout+result.stderr)
            if result.returncode:raise AssertionError('installed aligned CLI failed; inspect local log')
            observed=load_spectral(out/mode/'shard-00000.npz');differences={}
            for key,value in expected.items():
                if not isinstance(value,np.ndarray):continue
                np.testing.assert_array_equal(observed[key],value)
                if np.issubdtype(value.dtype,np.inexact):differences[key]=float(abs(observed[key]-value).max())
            summary=json.loads((out/mode/'summary.json').read_text())
            assert summary['vdif_read_mode']==('guarded_seek' if mode=='seek' else 'sequential_prefix')
            rows.append({'mode':mode,'correlation':summary,'maximum_absolute_differences':differences})
    summary={'installed_imports':True,'outside_checkout_cli':True,'rows':rows,
        'scope':'Same identified late 0.3s sample/RF/rate aligned reference. Does not validate all unread file headers or real receivers.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--clock-model',required=True)
    p.add_argument('--rate-profile',required=True);p.add_argument('--reference',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(run(a.manifest,a.clock_model,a.rate_profile,a.reference,a.output),indent=2))
