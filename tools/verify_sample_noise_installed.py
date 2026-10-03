"""Installed finite-sample noise estimator outside the checkout."""
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
from vsora_simulator import visibility_noise_estimate
assert Path(visibility_noise_estimate.__file__).is_relative_to(Path(sys.prefix))
s=np.array([[2.,.6+.2j],[.6-.2j,3.]])
q=visibility_noise_estimate.estimate_visibility_noise(s,8)
np.testing.assert_allclose(q['complex_covariance'][0,0],(8*6-abs(s[0,1])**2)/63,rtol=1e-12)
np.testing.assert_allclose(q['complex_pseudocovariance'][0,0],s[0,1]**2/9,rtol=1e-12)
assert np.linalg.eigvalsh(q['real_covariance']).min()>0
assert q['conditional_ensemble_unbiased'] and not q['generating_truth_used']
assert not q['distribution_gaussian_assumed'] and not q['covariance_inverted']
print(json.dumps({'installed_imports':True,'outside_checkout':True,'samples':8,
 'estimated_real_covariance':q['real_covariance'].tolist(),'conditional_ensemble_unbiased':True,
 'generating_truth_used':False,'distribution_gaussian_assumed':False,'covariance_inverted':False,
 'scope':'Algebraic installed API check. Conditional iid proper Gaussian model, not physical IQ, hardware covariance or confidence calibration.'}))
'''


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-sample-noise-installed-') as directory:
        script=Path(directory)/'check.py';script.write_text(SCRIPT)
        result=subprocess.run([sys.executable,str(script)],cwd=directory,env=env,capture_output=True,text=True)
    (out/'execution.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0,result.stderr
    q=json.loads(result.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    print(json.dumps(run(**vars(parser.parse_args())),indent=2))
