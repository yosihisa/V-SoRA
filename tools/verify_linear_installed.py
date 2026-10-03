"""Installed linear-rate entrypoints outside checkout, full VDIF comparison."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np


def run(reference_run,source_run,output):
    from vsora_correlator import aligned,rate_linear
    from vsora_formats.spectral import load_spectral
    assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (aligned,rate_linear))
    base=Path(reference_run).resolve();source=Path(source_run).resolve();out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-linear-installed-') as cwd:
        result=subprocess.run([str(Path(sys.prefix)/'bin/vsora-rate-linear'),
            '--input',str(base/'moderate-3s/pilot/shard-00000.npz'),'--output',str(out/'linear.json')],
            cwd=cwd,env=env,capture_output=True,text=True)
        assert result.returncode==0,'installed linear CLI failed'
        assert json.loads((out/'linear.json').read_text())==rate_linear.estimate_linear_shard(base/'moderate-3s/pilot/shard-00000.npz')
        result=subprocess.run([str(Path(sys.prefix)/'bin/vsora-closure-session'),
            '--manifest',str(base/'strong/manifest.json'),'--clock-model',str(base/'strong/clock.json'),
            '--pilot-integrations','1500','--integration-s','3','--correlation-only','--rate-model','linear',
            '--output',str(out/'strong')],cwd=cwd,env=env,capture_output=True,text=True)
        (out/'pipeline.log').write_text(result.stdout+result.stderr)
        assert result.returncode==0,'installed measured linear VDIF pipeline failed'
    expected=load_spectral(source/'strong/correlation/shard-00000.npz');observed=load_spectral(out/'strong/correlation/shard-00000.npz')
    differences={}
    for key,value in expected.items():
        if not isinstance(value,np.ndarray):continue
        np.testing.assert_array_equal(value,observed[key])
        if np.issubdtype(value.dtype,np.inexact):differences[key]=float(abs(value-observed[key]).max())
    q=json.loads((out/'strong/summary.json').read_text())
    summary={'installed_imports':True,'entrypoints_outside_checkout':True,'state':q['state'],
        'rate_model':q['rate_model'],'measured_rate_model':q['rate_estimate'],
        'maximum_absolute_source_array_differences':differences,
        'scope':'Strong deterministic smooth LO drift, four-station matched point/noise fixture. No arbitrary phase noise, hardware or Cas A fidelity claim.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference-run',required=True);p.add_argument('--source-run',required=True);p.add_argument('--output',required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
