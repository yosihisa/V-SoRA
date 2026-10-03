"""Installed CLI/API outside checkout against a frozen source result."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import vsora_correlator.time_scatter as module


def run(input,profile,expected,output):
    if not Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError('installed module outside environment prefix')
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    target=json.loads(Path(expected).read_text())
    with tempfile.TemporaryDirectory(prefix='vsora-time-scatter-') as folder:
        work=Path(folder);source=work/'pilot.npz';rate=work/'rate.json';result=work/'result.json'
        shutil.copyfile(input,source);shutil.copyfile(profile,rate)
        env=os.environ.copy();env.pop('PYTHONPATH',None)
        entry=Path(sys.prefix)/'bin/vsora-time-scatter'
        if not entry.is_file():raise RuntimeError('installed console entry point missing')
        cmd=[str(entry),'--input',str(source),
            '--rate-profile',str(rate),'--channel-index',str(target['channel_index']),'--output',str(result)]
        first=subprocess.run(cmd,cwd=work,env=env,capture_output=True,text=True)
        if first.returncode:raise RuntimeError('installed CLI failed')
        actual=json.loads(result.read_text());assert actual==target
        assert module.diagnose_time_scatter(module.load_spectral(source),target['channel_index'],json.loads(rate.read_text()))=={k:v for k,v in actual.items() if k not in ('input_sha256','rate_profile_sha256')}
        original=result.read_bytes();repeat=subprocess.run(cmd,cwd=work,env=env,capture_output=True,text=True)
        assert repeat.returncode!=0 and original==result.read_bytes()
    q={'state':'complete','installed_imports':True,'outside_checkout':True,'pythonpath_removed':True,
        'console_entry_point_verified':True,'cli_equals_frozen_source':True,'direct_api_equals_cli':True,'overwrite_rejected':True,
        'input_sha256':actual['input_sha256'],'rate_profile_sha256':actual['rate_profile_sha256'],
        'scientific_state':actual['state'],'hardware_coherence_measured':False,'production_rml_noise_model_changed':False}
    (out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for arg in ('input','profile','expected','output'):p.add_argument('--'+arg,required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
