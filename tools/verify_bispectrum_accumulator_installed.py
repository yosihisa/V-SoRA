"""Installed raw U3 accumulator compared with batch API outside checkout."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,tempfile

SCRIPT='''
import json
from pathlib import Path
import sys
import numpy as np
import vsora_correlator.bispectrum_accumulator as module
import vsora_simulator.bispectrum_distinct as batch
assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (module,batch))
rng=np.random.default_rng(6105)
x=rng.normal(size=(29,3,4))+1j*rng.normal(size=(29,3,4))
ok=np.ones((29,4),bool);ok[:4,0]=False;ok[7:10,2]=False
a=module.BispectrumAccumulator(4,3)
for start in range(0,29,5):a.consume(x[start:start+5],ok[start:start+5])
q=a.finish()
for n,t in enumerate(q['triangles']):
 good=ok[:,t].all(axis=1)
 ref=batch.distinct_sample_bispectrum(x[good].transpose(1,0,2),[t])
 np.testing.assert_allclose(q['distinct_sample_bispectrum'][:,n],ref['distinct_sample_bispectrum'][:,0],rtol=1e-12,atol=1e-12)
 assert q['common_sample_count'][n]==good.sum()
assert not q['input_sample_independence_verified'] and not q['input_mask_independence_verified']
print(json.dumps({'state':'complete','installed_imports':True,'outside_checkout':True,'pythonpath_removed':True,
 'chunked_common_mask_batch_match':True,'input_sample_independence_verified':False,
 'input_mask_independence_verified':False,'production_visibility_statistics_changed':False,
 'production_rml_noise_model_changed':False}))
'''


def run(output):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='vsora-u3-stream-installed-') as folder:
        work=Path(folder);script=work/'check.py';script.write_text(SCRIPT)
        env=os.environ.copy();env.pop('PYTHONPATH',None)
        p=subprocess.run([sys.executable,str(script)],cwd=work,env=env,capture_output=True,text=True)
        if p.returncode:raise RuntimeError('installed U3 accumulator verification failed')
        q=json.loads(p.stdout)
    (out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);print(json.dumps(run(**vars(p.parse_args())),indent=2))
