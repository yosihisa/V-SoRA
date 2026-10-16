"""Check installed normalized-power APIs against a saved source fixture."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def run(reference, output):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    script='''
import json,sys
from pathlib import Path
import numpy as np
from vsora_simulator import bispectrum_observed_power as module,bispectrum_distinct,visibility_moments
prefix=Path(sys.prefix)
assert all(Path(m.__file__).is_relative_to(prefix) for m in (module,bispectrum_distinct,visibility_moments))
assert not Path('tools/run.py').exists()
fixture=json.loads(Path(sys.argv[1]).read_text())
for c in fixture['voltage_cases']:
    values=np.asarray(c['voltages_real_imag']);x=values[...,0]+1j*values[...,1]
    q=module.observed_power_normalized_bispectrum(x,c['selected_triangles'])
    for key,target in c['expected'].items():
        if isinstance(q[key],np.ndarray):
            if np.iscomplexobj(q[key]):
                target=np.asarray(target);target=target[...,0]+1j*target[...,1]
            np.testing.assert_array_equal(q[key],target)
        else:assert q[key]==target,key
for target in fixture['rank_one_moments']:
    assert module.gaussian_rank_one_observed_power_moments(target['samples'])==target
print(json.dumps({'state':'complete','outside_checkout':True,'pythonpath_removed':True,'installed_core_modules_under_prefix':True,'checkout_runner_used':False,'all_source_fixture_values_exact':True,'voltage_cases':len(fixture['voltage_cases']),'rank_one_moment_cases':len(fixture['rank_one_moments']),'production_rml_noise_model_changed':False,'actual_hardware_data':False}))
'''
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-observed-power-') as folder:
        result=subprocess.run([sys.executable,'-c',script,str(Path(reference).resolve())],cwd=folder,env=env,capture_output=True,text=True,check=True)
    q=json.loads(result.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reference',required=True);p.add_argument('--output',required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
