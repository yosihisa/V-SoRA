"""Verify the installed multi-window entrypoint outside the checkout."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np


def run(manifest,clock,reference,output):
    from vsora_correlator import sequence
    from vsora_formats.spectral import load_spectral
    if not Path(sequence.__file__).is_relative_to(Path(sys.prefix)):
        raise AssertionError('installed sequence import required')
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    binary=str(Path(sys.prefix)/'bin/vsora-sequence')
    with tempfile.TemporaryDirectory(prefix='vsora-installed-sequence-') as directory:
        help_result=subprocess.run([binary,'--help'],cwd=directory,env=env,capture_output=True,text=True)
        assert help_result.returncode==0 and '--window-count' in help_result.stdout
        result=subprocess.run([binary,'--manifest',str(Path(manifest).resolve()),'--clock-model',str(Path(clock).resolve()),
            '--window-count','3','--starts','1','--max-iterations','100','--output',str(out/'sequence')],
            cwd=directory,env=env,capture_output=True,text=True)
        (out/'cli.log').write_text(result.stdout+result.stderr)
        if result.returncode:raise AssertionError('installed sequence failed; inspect local cli.log')
    summary=json.loads((out/'sequence/summary.json').read_text())
    expected=load_spectral(reference);observed=load_spectral(out/'sequence/synthesis/visibility.npz')
    differences={}
    for key,value in expected.items():
        if not isinstance(value,np.ndarray):continue
        np.testing.assert_array_equal(value,observed[key])
        if np.issubdtype(value.dtype,np.inexact):differences[key]=float(abs(value-observed[key]).max())
    result={'installed_import':True,'outside_checkout_entrypoint_help':True,'state':summary['state'],
        'window_count':len(summary['windows']),'window_rates_hz':[w['rate_estimate']['station_rates_hz'] for w in summary['windows']],
        'nominal_image_exposure_per_station_s':summary['nominal_image_exposure_per_station_s'],
        'closures':summary['closures'],'image_sum':summary['rml']['image_sum'],
        'selected_optimizer_success':summary['rml']['runs'][summary['rml']['selected_start']]['optimizer_success'],
        'maximum_absolute_reference_array_differences':differences,
        'scope':'Installed CLI on identical three-window point-noise VDIF. Scientific arrays compared; RML uses one start and 100 iterations, not convergence/fidelity validation.'}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--clock-model',required=True)
    p.add_argument('--reference',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(run(a.manifest,a.clock_model,a.reference,a.output),indent=2))
