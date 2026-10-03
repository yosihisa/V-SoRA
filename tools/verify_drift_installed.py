"""Installed constant-rate entrypoint on frozen moderate-drift VDIF."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np


def run(manifest,clock_model,reference,output):
    from vsora_correlator import coherence,closure_pipeline
    from vsora_formats.spectral import load_spectral
    assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (coherence,closure_pipeline))
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-drift-installed-') as directory:
        result=subprocess.run([str(Path(sys.prefix)/'bin/vsora-closure-session'),
            '--manifest',str(Path(manifest).resolve()),'--clock-model',str(Path(clock_model).resolve()),
            '--pilot-integrations','1500','--integration-s','3','--correlation-only','--output',str(out/'correlation')],
            cwd=directory,env=env,capture_output=True,text=True)
        (out/'cli.log').write_text(result.stdout+result.stderr)
        assert result.returncode==0,'installed drift CLI failed; inspect local cli.log'
    q=json.loads((out/'correlation/summary.json').read_text())
    expected=load_spectral(reference);observed=load_spectral(out/'correlation/correlation/shard-00000.npz');differences={}
    for key,value in expected.items():
        if not isinstance(value,np.ndarray):continue
        np.testing.assert_array_equal(value,observed[key])
        if np.issubdtype(value.dtype,np.inexact):differences[key]=float(abs(value-observed[key]).max())
    summary={'installed_imports':True,'entrypoint_outside_checkout':True,'state':q['state'],'type':q['type'],
        'rate_estimate':q['rate_estimate'],'input_identity':q['input_identity'],
        'centered_90pct_drift_limit_for_3s_hz_per_s':coherence.centered_drift_limit(3.),
        'maximum_absolute_reference_array_differences':differences,
        'scope':'Moderate deterministic drift point-noise VDIF. Production still fits constant rate; this test reproduces completion with residual attenuation, not drift correction or Cas A fidelity.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--clock-model',required=True)
    p.add_argument('--reference',required=True);p.add_argument('--output',required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
