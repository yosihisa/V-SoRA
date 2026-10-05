"""Verify known joint-covariance means from installed APIs outside checkout."""
import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path


def run(output,reference):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False);record=Path(reference).resolve()
    script='''
import json,sys
from pathlib import Path
import numpy as np
from vsora_simulator import bispectrum_joint_temporal as module
assert Path(module.__file__).is_relative_to(Path(sys.prefix))
q=json.loads(Path(sys.argv[1]).read_text());models={m['id']:m for m in q['models']};count=0
for c in q['cases']:
 a=np.asarray(models[c['model_id']]['known_covariance_real_imag']);base=a[...,0]+1j*a[...,1]
 times=np.asarray(c['model_times_s']);rates=np.asarray(c['generating_known_station_rates_hz']);phase=np.exp(2j*np.pi*times[:,None]*rates[None,:])
 changed=base*phase[:,:,None,None]*phase.conj()[None,None,:,:]
 for state,cov in [('uncorrected',changed),('known_inverse_phase',base)]:
  theory=module.joint_temporal_bispectrum_mean(cov)
  assert not theory['variance_or_likelihood_calculated'] and not theory['observed_gain_or_clock_estimated']
  for name in ('ordinary','distinct'):
   mean=theory[name+'_bispectrum_mean'];np.testing.assert_array_equal(np.c_[mean.real,mean.imag],c['methods'][state][name]['known_mean_real_imag']);count+=1
print(json.dumps({'state':'complete','installed_module_verified':True,'outside_checkout':True,'covariance_axis_order_verified':'time,station,time,station','conditions_checked':len(q['cases']),'mean_arrays_checked':count,'known_inverse_phase_supplied':True,'observed_gain_or_clock_estimated':False,'variance_or_likelihood_calculated':False,'real_hardware_validation_performed':False}))
'''
    env=os.environ.copy();env.pop('PYTHONPATH',None)
    with tempfile.TemporaryDirectory(prefix='vsora-joint-time-api-') as folder:
        result=subprocess.run([sys.executable,'-c',script,str(record)],cwd=folder,env=env,capture_output=True,text=True,check=True)
    q=json.loads(result.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--reference',required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
