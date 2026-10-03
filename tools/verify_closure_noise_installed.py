"""Installed joint closure-noise API outside the checkout."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SCRIPT='''
import json,sys
from pathlib import Path
import numpy as np
from vsora_imaging import closure_noise
from vsora_simulator import visibility_moments
assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (closure_noise,visibility_moments))
s=np.ones((4,4),complex);np.fill_diagonal(s,2)
m=visibility_moments.visibility_noise_moments(s,512)
q=closure_noise.joint_closure_noise(m['mean'],m['real_covariance'],m['pairs'])
naive=closure_noise.joint_closure_noise(m['mean'],np.eye(12)*4/1024,m['pairs'])
np.testing.assert_allclose(q['joint_covariance'],naive['joint_covariance']*.25,rtol=1e-12,atol=1e-17)
assert q['joint_valid'].all() and not q['covariance_inverted']
assert not q['closure_distribution_gaussian_guaranteed']
print(json.dumps({'installed_imports':True,'outside_checkout':True,'shared_point_rho':.5,
 'first_order_variance_ratio':(np.diag(q['joint_covariance'])/np.diag(naive['joint_covariance'])).tolist(),
 'phase_count':q['phase_count'],'logamp_count':q['logamp_count'],
 'covariance_inverted':False,'closure_distribution_gaussian_guaranteed':False,
 'scope':'Known one-cell forward covariance, high-SNR first-order closure propagation. No receiver covariance estimate, physical VDIF, hardware or image fidelity.'}))
'''


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-closure-noise-installed-') as directory:
        script=Path(directory)/'check.py';script.write_text(SCRIPT)
        result=subprocess.run([sys.executable,str(script)],cwd=directory,env=env,capture_output=True,text=True)
    (out/'execution.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0,result.stderr
    q=json.loads(result.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
