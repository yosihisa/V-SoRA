"""Check installed conditional averaging API against frozen known-model moments."""
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
from vsora_simulator import bispectrum_average,bispectrum_moments
assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (bispectrum_average,bispectrum_moments))
reference=json.loads(Path(sys.argv[1]).read_text());phase=np.exp(1j*np.array([0,.7,1.9,-.5]));identity=np.eye(4)
models={'zero':identity,'weak':identity+.001*np.ones((4,4)),'low':identity+.1*np.ones((4,4)),
 'two_components':identity+.2*np.ones((4,4))+.15*phase[:,None]*phase.conj()[None,:],'rank_one':np.ones((4,4))}
for c in reference['cases']:
 q=bispectrum_average.gaussian_averaged_bispectrum_moments(models[c['model']],c['samples_per_window'],c['independent_windows'])
 np.testing.assert_array_equal(q['real_covariance'],np.asarray(c['model_covariance']))
 np.testing.assert_array_equal(np.c_[q['mean'].real,q['mean'].imag],np.asarray(c['known_mean_real_imag']))
 assert not q['distribution_gaussian_assumed'] and not q['production_rml_noise_model_changed']
rng=np.random.default_rng(68);a=rng.normal(size=(8,8))+1j*rng.normal(size=(8,8));s=np.eye(8)+a @ a.conj().T
q=bispectrum_average.gaussian_averaged_bispectrum_moments(s,3,64)
assert q['real_covariance'].shape==(112,112) and np.isfinite(q['real_covariance']).all()
assert np.linalg.eigvalsh(q['real_covariance']).min()>=-1e-10*np.max(abs(q['real_covariance']))
print(json.dumps({'state':'complete','installed_imports':True,'outside_checkout':True,'pythonpath_removed':True,
 'frozen_known_model_cases_identical':len(reference['cases']),'eight_station_covariance_dimension':112,
 'eight_station_finite_psd_checked':True,'distribution_gaussian_assumed':False,'production_rml_noise_model_changed':False,
 'scope':'Installed known-S conditional averaging API; no hardware or image likelihood.'}))
'''


def run(output,reference):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    source=Path(reference).resolve();env=os.environ.copy();env.pop('PYTHONPATH',None)
    env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-u3-average-api-') as directory:
        folder=Path(directory);script=folder/'check.py';script.write_text(SCRIPT)
        result=subprocess.run([sys.executable,str(script),str(source)],cwd=folder,env=env,capture_output=True,text=True)
    (out/'execution.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('installed averaging API validation failed')
    q=json.loads(result.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--reference',required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
