"""Installed Gaussian diagnostic GUI; explicitly checkout-owned workflow."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import httpx
from playwright.sync_api import sync_playwright


def run(output, port=8774):
    from vsora_ui import models, worker
    assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (models, worker))
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    checkout=Path(__file__).resolve().parents[1];url=f'http://127.0.0.1:{port}'
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-gaussian-ui-') as folder:
        workspace=Path(folder);(workspace/'tools').mkdir();(workspace/'tools/run.py').symlink_to(checkout/'tools/run.py')
        log=(out/'server.log').open('w');server=subprocess.Popen([str(Path(sys.prefix)/'bin/vsora-ui'),
            '--workspace',folder,'--port',str(port)],cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                try:
                    if httpx.get(url+'/api/environment',timeout=1).status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.1)
            else:raise AssertionError('GUI not ready')
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1000})
                errors=[];requests=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url))
                page.goto(url);page.get_by_role('button',name='動作検証',exact=True).click()
                page.locator('#validation-form select[name=validation]').select_option('uncertainty')
                page.get_by_role('button',name='検証を開始',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=90000)
                job_id=httpx.get(url+'/api/jobs').json()[0]['id'];job=httpx.get(url+'/api/jobs/'+job_id).json();q=job['summary']
                assert q['type']=='rate_uncertainty_validation' and q['draws']==65536 and len(q['gaussian_results'])==6
                assert not q['actual_hardware_data'] and not q['covariance_calibrated_against_rate_solver']
                text=page.locator('#job-detail').inner_text();assert '仮定Gaussian誤差の計算検証' in text and '標本の振幅平均' in text
                assert '推定器の誤差や実機の位相安定性を測った実験ではありません' in text
                page.wait_for_function('Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                page.screenshot(path=str(out/'result.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844});overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                page.screenshot(path=str(out/'mobile.png'),full_page=True)
                font=page.evaluate('document.fonts.check("14px \'VSoRA Japanese\'")');external=[r for r in requests if not r.startswith(url+'/')]
                assert not errors and not external and not overflow and font
                summary={'installed_gui_imports':True,'validation_workflow_from_checkout':True,'independent_workspace':True,
                    'state':job['state'],'browser':browser.version,'javascript_errors':errors,'external_requests':len(external),
                    'japanese_font_loaded':font,'mobile_horizontal_overflow':overflow,'draws':q['draws'],
                    'cases':len(q['gaussian_results']),'actual_hardware_data':False,'covariance_calibrated_against_rate_solver':False,
                    'scope':'Conditional Gaussian calculation/UI, WSL headless Chromium. No real rate covariance calibration, OCXO, Windows or image-fidelity guarantee.'}
                browser.close();(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary
        finally:
            server.terminate()
            try:server.wait(timeout=8)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=2)
            log.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--port',type=int,default=8774)
    print(json.dumps(run(**vars(parser.parse_args())),indent=2))
