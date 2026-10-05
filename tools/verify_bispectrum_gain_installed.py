"""Installed population gain design checked outside the checkout."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,tempfile

SCRIPT='''
import json,sys
from pathlib import Path
import numpy as np
from vsora_imaging import bispectrum_gain
from vsora_simulator import bispectrum_moments
assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (bispectrum_gain,bispectrum_moments))
ref=json.loads(Path(sys.argv[1]).read_text())
for c in ref['cases']:
 q=bispectrum_gain.bispectrum_gain_design(c['stations'])
 for name in ('baselines','triangle_count','triangle_amplitude_rank','triangle_station_gain_rank','gain_invariant_amplitude_rank','left_null_weight_rows','zero_identity_directions_in_left_null','conventional_logamp_rank','closure_phase_rank'):assert q[name]==c[name]
 assert not q['observed_statistic_logarithms_taken'] and not q['noise_or_likelihood_calculated']
e=ref['four_station_example'];s0=np.asarray(e['base_station_covariance']);s1=np.asarray(e['matched_station_covariance'])
q0=bispectrum_moments.gaussian_distinct_bispectrum_moments(s0,128);q1=bispectrum_moments.gaussian_distinct_bispectrum_moments(s1,128)
np.testing.assert_allclose(q0['mean'],q1['mean'],rtol=1e-12,atol=1e-12)
assert not np.allclose(q0['real_covariance'],q1['real_covariance'],rtol=1e-12,atol=1e-12)
print(json.dumps({'state':'complete','installed_imports':True,'outside_checkout':True,'pythonpath_removed':True,
 'complete_array_station_counts_checked':[3,4,5,6,7,8],'rank_results_match_frozen_reference':True,
 'four_station_population_means_identical':True,'finite_sample_covariances_differ':True,
 'noise_likelihood_implemented':False,'actual_hardware_data':False,'production_rml_noise_model_changed':False,
 'scope':'Population mean constraints only; this is not full distributional nonidentifiability or image feasibility.'}))
'''


def run(output,reference):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    source=Path(reference).resolve();env=os.environ.copy();env.pop('PYTHONPATH',None)
    env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-gain-installed-') as folder:
        cwd=Path(folder);script=cwd/'check.py';script.write_text(SCRIPT)
        p=subprocess.run([sys.executable,str(script),str(source)],cwd=cwd,env=env,capture_output=True,text=True)
    (out/'execution.log').write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError('installed population gain validation failed')
    q=json.loads(p.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--reference',required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
