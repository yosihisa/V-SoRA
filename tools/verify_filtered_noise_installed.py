"""Outside-checkout installed API verification for fixed Gaussian operators."""
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
from scipy.signal import firwin,lfilter
from vsora_simulator import filtered_noise
from vsora_correlator import clock
assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (filtered_noise,clock))
s=np.ones((3,3))+np.eye(3);shift=filtered_noise.filtered_visibility_moments(s,np.eye(3),1,8)
assert abs(shift['complex_covariance'][0,2]-7/64)<1e-14
assert shift['iid_counterfactual_real_covariance'][0,2]==0 and shift['common_kernel_effective_count'] is None
m=128;common=filtered_noise.filtered_visibility_moments(s,np.full((3,65),1/np.sqrt(65)),8,m)
expected=1+2*sum((1-d/m)*(1-d*8/65)**2 for d in range(1,9))
assert abs(common['common_kernel_variance_factor']-expected)<1e-12
assert not common['actual_hardware_data'] and not common['production_rml_noise_model_changed']
rng=np.random.default_rng(49);length=32;count=5;offset=.25;channel=24
raw=(rng.normal(size=count*length+192)+1j*rng.normal(size=count*length+192))/np.sqrt(2)
y,_=clock.interpolate_samples(lfilter(firwin(65,.35,fs=1.,window=('kaiser',8.6)),[1],raw),96+offset+np.arange(count*length))
truth=np.fft.fftshift(np.fft.fft(y.reshape(count,length),axis=1,norm='ortho'),axes=1)[:,channel]
h=filtered_noise.aligned_fft_kernel(length,channel,offset);actual=np.array([h @ raw[a*length:a*length+len(h)] for a in range(count)])
np.testing.assert_allclose(actual,truth,rtol=1e-12,atol=1e-12)
print(json.dumps({'installed_api_outside_checkout':True,'integer_shift_cross_covariance':float(shift['complex_covariance'][0,2].real),
 'common_kernel_variance_factor':common['common_kernel_variance_factor'],'common_kernel_effective_count':common['common_kernel_effective_count'],
 'maximum_fir_sinc_fft_operator_error':float(max(abs(actual-truth))),
 'raw_covariance_supplied':True,'actual_hardware_data':False,'production_rml_noise_model_changed':False,
 'scope':'Known raw Gaussian covariance and fixed FIR/sinc/FFT coefficients; no measured effective count, ADC or image fidelity.'}))
'''


def run(output):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-filtered-api-') as directory:
        script=Path(directory)/'check.py';script.write_text(SCRIPT)
        r=subprocess.run([sys.executable,str(script)],cwd=directory,env=env,capture_output=True,text=True)
    (out/'execution.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
    q=json.loads(r.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    print(json.dumps(run(**vars(parser.parse_args())),indent=2))
