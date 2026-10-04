"""Verify installed conditional bispectrum API outside checkout."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,tempfile

SCRIPT='''
import json, math
from pathlib import Path
import sys
import vsora_simulator.bispectrum_sensitivity as module
assert Path(module.__file__).is_relative_to(Path(sys.prefix))
m=19200
q=module.null_bispectrum_variance(m)
assert q['complex_variance']==1/(m*(m-1)*(m-2))
a=module.conditional_bispectrum_plan(m,[.01,.02,.03],windows=16)
b=module.conditional_bispectrum_plan(m,[.02,.04,.06])
assert math.isclose(a['stacked_null_variance_snr'],4*a['single_window_null_variance_snr'])
assert math.isclose(b['single_window_null_variance_snr'],8*a['single_window_null_variance_snr'])
assert not a['nonzero_source_variance_calculated'] and not a['actual_temporal_independence_verified']
print(json.dumps({'state':'complete','installed_imports':True,'outside_checkout':True,'pythonpath_removed':True,
 'null_complex_variance':q['complex_variance'],'sqrt_window_scaling_verified':True,'cubic_coherence_scaling_verified':True,
 'nonzero_source_variance_calculated':False,'actual_temporal_independence_verified':False,'image_reconstructed':False}))
'''


def run(output):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='vsora-null-sensitivity-') as folder:
        work=Path(folder);script=work/'check.py';script.write_text(SCRIPT)
        env=os.environ.copy();env.pop('PYTHONPATH',None)
        p=subprocess.run([sys.executable,str(script)],cwd=work,env=env,capture_output=True,text=True)
        if p.returncode:raise RuntimeError('installed conditional sensitivity API failed')
        q=json.loads(p.stdout)
    (out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);print(json.dumps(run(**vars(p.parse_args())),indent=2))
