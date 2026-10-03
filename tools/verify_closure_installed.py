"""Verify installed closure entrypoints and GUI outside the checkout."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import httpx


def run(manifest,clock_model,output,port=8768,pilot_integrations=256,pilot_integration_s=None,integration_s=.3,max_rate_hz=100.):
    from vsora_imaging import rml
    from vsora_correlator import rate,closure_pipeline
    from vsora_ui import server
    if not all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (rml,rate,closure_pipeline,server)):
        raise AssertionError('installed wheel imports required')
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    manifest=Path(manifest).resolve();clock=Path(clock_model).resolve()
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    binary=Path(sys.prefix)/'bin';checks=[]
    with tempfile.TemporaryDirectory(prefix='vsora-installed-closure-') as directory:
        for name in ['vsora-closure','vsora-rml','vsora-rate','vsora-closure-session','vsora-synthesis','vsora-ui']:
            result=subprocess.run([str(binary/name),'--help'],cwd=directory,env=env,capture_output=True,text=True)
            if result.returncode:raise AssertionError('installed entrypoint help failed')
            checks.append(name)
        pilot_options=['--pilot-integrations',str(pilot_integrations),'--integration-s',str(integration_s),'--max-rate-hz',str(max_rate_hz)]
        if pilot_integration_s is not None:pilot_options+=['--pilot-integration-s',str(pilot_integration_s)]
        result=subprocess.run([str(binary/'vsora-closure-session'),'--manifest',str(manifest),'--clock-model',str(clock),
            '--output',str(out/'cli'),'--starts','1','--max-iterations','100',*pilot_options],cwd=directory,env=env,capture_output=True,text=True)
        (out/'cli.log').write_text(result.stdout+result.stderr)
        if result.returncode:raise AssertionError('installed pipeline CLI failed; inspect local cli.log')
        cli=json.loads((out/'cli/summary.json').read_text())
        url=f'http://127.0.0.1:{port}';log=(out/'gui.log').open('w')
        process=subprocess.Popen([str(binary/'vsora-ui'),'--workspace',directory,'--port',str(port)],
                                  cwd=directory,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                try:
                    environment=httpx.get(url+'/api/environment',timeout=1)
                    if environment.status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.1)
            else:raise AssertionError('installed GUI not ready')
            assert not environment.json()['validation_available']
            submit=httpx.post(url+'/api/jobs',headers={'X-VSoRA-Request':'1'},json={'kind':'analysis','manifest':str(manifest),
                    'clock_model':str(clock),'starts':1,'max_iterations':100,'pilot_integrations':pilot_integrations,
                    'pilot_integration_s':pilot_integration_s,'integration_s':integration_s,'max_rate_hz':max_rate_hz}).json()
            job_id=submit['id'];deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                job=httpx.get(url+'/api/jobs/'+job_id).json()
                if job['state'] not in ('queued','running'):break
                time.sleep(.2)
            if job['state']!='complete':raise AssertionError('installed GUI analysis failed')
            gui=job['summary']
            submit=httpx.post(url+'/api/jobs',headers={'X-VSoRA-Request':'1'},json={'kind':'sensitivity'}).json()
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                planner=httpx.get(url+'/api/jobs/'+submit['id']).json()
                if planner['state'] not in ('queued','running'):break
                time.sleep(.2)
            assert planner['state']=='complete'
            assert planner['summary']['assumptions']['station_sefd_jy'][0]>500000
            assert planner['summary']['independent_closure_counts']=={'phase':0,'logamp':0}
        finally:
            process.terminate()
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
            log.close()
    summary={'installed_wheel_imports':True,'entrypoints_outside_checkout':checks,
             'cli_state':cli['state'],'gui_state':job['state'],'sensitivity_gui_state':planner['state'],'checkout_validation_available':False,
             'cli_input_unit':cli['rml']['input_unit'],'gui_input_unit':gui['rml']['input_unit'],
             'relative_flux_sum':gui['rml']['image_sum'],'absolute_flux_measured':gui['absolute_flux_measured'],
             'cli_rate_acquisition':cli.get('rate_acquisition'),'gui_rate_acquisition':gui.get('rate_acquisition'),
             'valid_phase_closures':gui['closures']['phase_valid'],'valid_logamp_closures':gui['closures']['logamp_valid']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--clock-model',required=True)
    p.add_argument('--output',required=True);p.add_argument('--port',type=int,default=8768)
    p.add_argument('--pilot-integrations',type=int,default=256);p.add_argument('--pilot-integration-s',type=float)
    p.add_argument('--integration-s',type=float,default=.3);p.add_argument('--max-rate-hz',type=float,default=100.)
    a=p.parse_args();print(json.dumps(run(a.manifest,a.clock_model,a.output,a.port,a.pilot_integrations,a.pilot_integration_s,a.integration_s,a.max_rate_hz),indent=2))
