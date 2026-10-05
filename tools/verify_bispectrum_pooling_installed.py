"""Check installed conditional pooling API outside the checkout."""
import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path


def run(output):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    script='''
import json,sys
from pathlib import Path
import numpy as np
from vsora_simulator import bispectrum_pooling,bispectrum_moments,bispectrum_average
assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (bispectrum_pooling,bispectrum_moments,bispectrum_average))
s=np.eye(4)+.1*np.ones((4,4));g=np.exp(2j*np.pi*np.arange(4)[:,None]*np.arange(4)[None,:]/4)
q=bispectrum_pooling.pooled_covariance_bispectrum_mean(g[:,:,None]*s*g[:,None,:].conj(),32)
np.testing.assert_allclose(q['equal_group_u3_mean'],.001,atol=1e-15)
np.testing.assert_allclose(q['pooled_u3_mean'],.002/(127*126),atol=1e-15)
ratios=[]
for groups in (1,4,16):
 a=bispectrum_average.gaussian_averaged_bispectrum_moments(np.eye(4),32,groups)
 p=bispectrum_moments.gaussian_distinct_bispectrum_moments(np.eye(4),32*groups)
 ratio=a['complex_covariance'].diagonal().real/p['complex_covariance'].diagonal().real
 np.testing.assert_allclose(ratio,(32*groups-1)*(32*groups-2)/(31*30),rtol=1e-13)
 ratios.append(ratio.tolist())
rng=np.random.default_rng(74);z=rng.normal(size=(4,8,8))+1j*rng.normal(size=(4,8,8));s=z @ z.conj().transpose(0,2,1)
n8=bispectrum_pooling.pooled_covariance_bispectrum_mean(s,32)
assert len(n8['triangles'])==56 and np.isfinite(n8['pooled_u3_mean']).all()
print(json.dumps({'state':'complete','installed_modules_verified':True,'outside_checkout':True,'phase_mean_example_checked':True,'null_variance_ratios':ratios,'eight_station_triangles':56,'heterogeneous_covariance_or_observed_alignment_calculated':False}))
'''
    env=os.environ.copy();env.pop('PYTHONPATH',None)
    with tempfile.TemporaryDirectory(prefix='vsora-pooling-api-') as folder:
        result=subprocess.run([sys.executable,'-c',script],cwd=folder,env=env,capture_output=True,text=True,check=True)
    q=json.loads(result.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);print(json.dumps(run(**vars(p.parse_args())),indent=2))
