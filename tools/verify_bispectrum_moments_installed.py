"""Installed exact known-Gaussian U3 moments outside the source checkout."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,tempfile

SCRIPT='''
import json
from pathlib import Path
import sys
import numpy as np
import vsora_simulator.bispectrum_moments as module
assert Path(module.__file__).is_relative_to(Path(sys.prefix))
null=module.gaussian_distinct_bispectrum_moments(np.eye(4),128)
np.testing.assert_allclose(null['complex_covariance'],np.eye(4)/(128*127*126),rtol=1e-13,atol=0)
np.testing.assert_array_equal(null['complex_pseudocovariance'],0)
s=np.eye(4)+.1*np.ones((4,4))
q=module.gaussian_distinct_bispectrum_moments(s,32)
gain=np.array([.4,3,1.5,.75])*np.exp(1j*np.array([.2,-.7,1.1,2.1]))
r=module.gaussian_distinct_bispectrum_moments(s*gain[:,None]*gain.conj()[None,:],32)
factor=np.prod(abs(gain[q['triangles']])**2,axis=1)
for key in ('complex_covariance','complex_pseudocovariance'):
 np.testing.assert_allclose(r[key],q[key]*factor[:,None]*factor[None,:],rtol=1e-12,atol=1e-12)
assert np.linalg.eigvalsh(q['real_covariance']).min()>-1e-12
assert not q['distribution_gaussian_assumed'] and not q['actual_temporal_independence_verified']
print(json.dumps({'state':'complete','installed_imports':True,'outside_checkout':True,'pythonpath_removed':True,
 'null_limit_verified':True,'fixed_gain_covariance_verified':True,'real_covariance_psd_verified':True,
 'distribution_gaussian_assumed':False,'actual_temporal_independence_verified':False,'production_rml_noise_model_changed':False}))
'''


def run(output):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='vsora-u3-moments-installed-') as folder:
        work=Path(folder);script=work/'check.py';script.write_text(SCRIPT)
        env=os.environ.copy();env.pop('PYTHONPATH',None)
        p=subprocess.run([sys.executable,str(script)],cwd=work,env=env,capture_output=True,text=True)
        if p.returncode:raise RuntimeError('installed U3 moments API verification failed')
        q=json.loads(p.stdout)
    (out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);print(json.dumps(run(**vars(p.parse_args())),indent=2))
