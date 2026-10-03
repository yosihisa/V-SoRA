"""Installed experimental API, run outside checkout with independent enumeration."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SCRIPT='''
from itertools import permutations
import json
from pathlib import Path
import sys
import numpy as np
import vsora_simulator.bispectrum_distinct as module
assert Path(module.__file__).is_relative_to(Path(sys.prefix))
rng=np.random.default_rng(53);x=rng.normal(size=(7,4))+1j*rng.normal(size=(7,4))
q=module.distinct_sample_bispectrum(x);errors=[]
for a,(i,j,k) in enumerate(q['triangles']):
 z1=x[:,i]*x[:,j].conj();z2=x[:,j]*x[:,k].conj();z3=x[:,k]*x[:,i].conj()
 expected=sum(z1[r]*z2[s]*z3[t] for r,s,t in permutations(range(7),3))/(7*6*5)
 errors.append(abs(q['distinct_sample_bispectrum'][a]-expected))
assert max(errors)<1e-12
assert module.gaussian_ordinary_bispectrum_mean(np.eye(3),32)['ordinary_product_mean'][0]==1/1024
rank=module.gaussian_ordinary_bispectrum_mean(np.ones((3,3)),32)['ordinary_product_mean'][0]
assert abs(rank-33*34/1024)<1e-14
assert not q['closure_phase_unbiased_guarantee'] and not q['production_rml_noise_model_changed']
print(json.dumps({'state':'complete','installed_imports':True,'outside_checkout':True,'pythonpath_removed':True,
 'all_four_triangles_match_ordered_enumeration':True,'maximum_absolute_difference':float(max(errors)),
 'zero_source_ordinary_mean':1/1024,'rank_one_ordinary_mean':float(rank.real),
 'production_rml_noise_model_changed':False,'closure_phase_unbiased_guarantee':False}))
'''


def run(output):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='vsora-bispectrum-installed-') as folder:
        work=Path(folder);script=work/'check.py';script.write_text(SCRIPT)
        env=os.environ.copy();env.pop('PYTHONPATH',None)
        p=subprocess.run([sys.executable,str(script)],cwd=work,env=env,capture_output=True,text=True)
        if p.returncode:raise RuntimeError('installed bispectrum API check failed')
        q=json.loads(p.stdout)
    (out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);print(json.dumps(run(**vars(p.parse_args())),indent=2))
