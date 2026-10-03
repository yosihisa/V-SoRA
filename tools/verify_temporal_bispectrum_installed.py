"""Verify installed temporal bispectrum API outside the source checkout."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SCRIPT = '''
from itertools import permutations, product
import json
from pathlib import Path
import sys
import numpy as np
import vsora_simulator.bispectrum_temporal as module
assert Path(module.__file__).is_relative_to(Path(sys.prefix))
rng = np.random.default_rng(55)
a = rng.normal(size=(3, 7, 7)) + 1j*rng.normal(size=(3, 7, 7))
k = np.array([r @ r.conj().T/7 for r in a])
q = module.temporal_receiver_bispectrum_mean(k)
def term(a,b,c): return k[0,a,c]*k[1,b,a]*k[2,c,b]
ordinary = sum(term(a,b,c) for a,b,c in product(range(7),repeat=3))/7**3
distinct = sum(term(a,b,c) for a,b,c in permutations(range(7),3))/(7*6*5)
error = max(abs(ordinary-q['ordinary_bispectrum_mean']),abs(distinct-q['distinct_bispectrum_mean']))
assert error < 1e-12
box = module.white_filter_temporal_covariance(np.ones(65)/np.sqrt(65),8,128)
before = module.temporal_receiver_bispectrum_mean(np.repeat(box[None],3,axis=0))
guard = box[::9,::9]
after = module.temporal_receiver_bispectrum_mean(np.repeat(guard[None],3,axis=0))
assert before['distinct_bispectrum_mean'].real > 1e-4
assert abs(after['distinct_bispectrum_mean']) < 1e-14 and len(guard)==15
assert not before['actual_temporal_independence_verified']
print(json.dumps({'state':'complete','installed_imports':True,'outside_checkout':True,
 'pythonpath_removed':True,'all_index_enumeration_maximum_difference':float(error),
 'box_distinct_model_mean':float(before['distinct_bispectrum_mean'].real),
 'guarded_distinct_model_mean':float(after['distinct_bispectrum_mean'].real),
 'retained_outputs':len(guard),'actual_temporal_independence_verified':False,
 'production_rml_noise_model_changed':False}))
'''


def run(output):
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='vsora-temporal-installed-') as folder:
        work = Path(folder)
        script = work/'check.py'
        script.write_text(SCRIPT)
        env = os.environ.copy()
        env.pop('PYTHONPATH', None)
        result = subprocess.run([sys.executable, str(script)], cwd=work, env=env,
                                capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError('installed temporal bispectrum API check failed')
        summary = json.loads(result.stdout)
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    print(json.dumps(run(**vars(parser.parse_args())), indent=2))
