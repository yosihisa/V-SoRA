"""Installed known common space/time mean API checked outside the checkout."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,tempfile

SCRIPT='''
import json,sys
from pathlib import Path
import numpy as np
from vsora_simulator import bispectrum_common_temporal,bispectrum_temporal,filtered_noise
assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (bispectrum_common_temporal,bispectrum_temporal,filtered_noise))
ref=json.loads(Path(sys.argv[1]).read_text());phase=np.exp(1j*np.array([0,.7,1.9,-.5]));identity=np.eye(4)
sources={'zero':identity,'weak':identity+.001*np.ones((4,4)),'low':identity+.1*np.ones((4,4)),
 'two_components':identity+.2*np.ones((4,4))+.15*phase[:,None]*phase.conj()[None,:],'rank_one':np.ones((4,4))}
for c in ref['cases']:
 label=c['time_model'];guard={'guarded_average':9,'guarded_reference':5}.get(label,1)
 if label=='white':h=np.ones(1);hop=1
 elif label in ('long_average','guarded_average'):h=np.ones(65)/np.sqrt(65);hop=8
 else:h=filtered_noise.aligned_fft_kernel(32,16,.25);h=h/np.sqrt(np.sum(abs(h)**2));hop=32
 k=bispectrum_temporal.white_filter_temporal_covariance(h,hop,128)[::guard,::guard]
 q=bispectrum_common_temporal.common_temporal_bispectrum_mean(sources[c['source_model']],k)
 for method,key in [('ordinary','ordinary_bispectrum_mean'),('distinct','distinct_bispectrum_mean')]:
  np.testing.assert_array_equal(np.c_[q[key].real,q[key].imag],np.asarray(c['methods'][method]['known_mean_real_imag']))
 assert not q['variance_or_likelihood_calculated'] and not q['actual_temporal_independence_verified']
 assert q['samples']==c['retained_outputs']
rng=np.random.default_rng(72);a=rng.normal(size=(8,8))+1j*rng.normal(size=(8,8));s=np.eye(8)+a @ a.conj().T
q=bispectrum_common_temporal.common_temporal_bispectrum_mean(s,.2*np.ones((3,3))+.8*np.eye(3))
assert q['distinct_bispectrum_mean'].shape==(56,) and np.isfinite(q['distinct_bispectrum_mean']).all()
print(json.dumps({'state':'complete','installed_imports':True,'outside_checkout':True,'pythonpath_removed':True,
 'frozen_known_model_means_identical':len(ref['cases']),'eight_station_triangles':56,'eight_station_finite_means':True,
 'variance_or_likelihood_calculated':False,'observed_bias_correction_performed':False,'actual_hardware_data':False,
 'production_rml_noise_model_changed':False,'scope':'Known constant S times common constant-power K conditional means only; no physical filters or observation correction.'}))
'''


def run(output,reference):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    source=Path(reference).resolve();env=os.environ.copy();env.pop('PYTHONPATH',None)
    env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-common-time-api-') as folder:
        cwd=Path(folder);script=cwd/'check.py';script.write_text(SCRIPT)
        p=subprocess.run([sys.executable,str(script),str(source)],cwd=cwd,env=env,capture_output=True,text=True)
    (out/'execution.log').write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError('installed known common time mean verification failed')
    q=json.loads(p.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--reference',required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
