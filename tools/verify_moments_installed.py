"""Installed forward noise-moment API outside the project checkout."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SCRIPT = '''
import json, sys
from pathlib import Path
import numpy as np
from vsora_simulator import visibility_moments
assert Path(visibility_moments.__file__).is_relative_to(Path(sys.prefix))
s=np.array([[2.,.6+.2j],[.6-.2j,3.]])
q=visibility_moments.visibility_noise_moments(s,32)
assert abs(q['complex_covariance'][0,0]-6/32)<1e-15
assert abs(q['complex_pseudocovariance'][0,0]-s[0,1]**2/32)<1e-15
assert np.linalg.eigvalsh(q['real_covariance']).min()>0
common=visibility_moments.visibility_noise_moments(np.ones((4,4)),10)
np.testing.assert_allclose(common['real_covariance'][6:,:],0,atol=1e-15)
print(json.dumps({'installed_imports':True,'outside_checkout':True,
 'two_station_real_covariance':q['real_covariance'].tolist(),
 'common_signal_imaginary_variance_zero':True,
 'gaussian_visibility_distribution_assumed':q['distribution_gaussian_assumed'],
 'scope':'Known iid proper Gaussian station voltage forward moments. No measured covariance or real hardware.'}))
'''


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-moments-installed-') as directory:
        script=Path(directory)/'check.py';script.write_text(SCRIPT)
        result=subprocess.run([sys.executable,str(script)],cwd=directory,env=env,capture_output=True,text=True)
    (out/'execution.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0,result.stderr
    q=json.loads(result.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
