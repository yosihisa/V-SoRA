"""Check installed synthetic layout API and frozen defaults outside checkout."""
import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path


def run(output,reference):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False);record=Path(reference).resolve()
    script='''
import json,sys
from pathlib import Path
import numpy as np
from vsora_observation import layouts
from vsora_ui import models,worker
assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (layouts,models,worker))
golden=json.loads(Path(sys.argv[1]).read_text())['layouts'];count=0
for n in (4,8):
 for kind in ('spread','line','ring'):
  assert layouts.reference_layout(n,kind).tobytes()==np.asarray(golden[f'{n}-{kind}'],dtype=float).tobytes()
  for maximum in (25.,100.,600.):
   x=layouts.reference_layout(n,kind,maximum);assert np.isclose(np.linalg.norm(x[:,None]-x[None,:],axis=-1).max(),maximum,rtol=1e-12,atol=0);count+=1
for cls in (models.SimulationRequest,models.RmlRequest):
 c=worker.simulation_config(cls(maximum_baseline_m=100.));x=np.asarray([s['enu_m'] for s in c['stations']]);assert np.isclose(np.linalg.norm(x[:,None]-x[None,:],axis=-1).max(),100,rtol=1e-12,atol=0)
assert models.SensitivityRequest(maximum_baseline_m=200).maximum_baseline_m==200
print(json.dumps({'state':'complete','installed_modules_verified':True,'outside_checkout':True,'frozen_defaults_byte_identical':6,'layout_scale_cases_checked':count,'simulation_and_rml_config_checked':True,'sensitivity_request_checked':True,'actual_station_positions_modified':False,'image_quality_validated':False}))
'''
    env=os.environ.copy();env.pop('PYTHONPATH',None)
    with tempfile.TemporaryDirectory(prefix='vsora-layout-api-') as folder:
        result=subprocess.run([sys.executable,'-c',script,str(record)],cwd=folder,env=env,capture_output=True,text=True,check=True)
    q=json.loads(result.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--reference',required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
