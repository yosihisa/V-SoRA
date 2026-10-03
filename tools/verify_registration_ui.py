"""Installed Japanese RML GUI comparison in a separate disposable workspace."""
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


def run(output,port=8769):
    from vsora_imaging import experiment,registration
    if not all(Path(module.__file__).is_relative_to(Path(sys.prefix)) for module in (experiment,registration)):
        raise AssertionError('installed wheel imports required')
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False);url=f'http://127.0.0.1:{port}'
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-registration-ui-') as directory:
        log=(out/'server.log').open('w')
        process=subprocess.Popen([str(Path(sys.prefix)/'bin/vsora-ui'),'--workspace',directory,'--port',str(port)],
                                 cwd=directory,env=env,stdout=log,stderr=subprocess.STDOUT)
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
                errors=[];requests=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('request',lambda r:requests.append(r.url));page.goto(url)
                page.get_by_role('button',name='Closure＋RML',exact=True).click()
                page.locator('#rml-form select[name=model]').select_option('double')
                page.locator('#rml-form select[name=stations]').select_option('4')
                page.locator('#rml-form details').evaluate_all('nodes => nodes.forEach(node => node.open = true)')
                for name,value in [('snapshots',8),('starts',1),('max_iterations',100)]:
                    page.locator(f'#rml-form input[name={name}]').fill(str(value))
                page.get_by_role('button',name='Closure＋RMLで模擬画像を復元',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=45000)
                text=page.locator('#job-detail').inner_text();assert '画面外へ出た成分も含めて' in text
                page.wait_for_function('Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                page.evaluate('document.fonts.ready');font=page.evaluate('document.fonts.check("14px \'VSoRA Japanese\'")')
                page.screenshot(path=str(out/'registration-result.png'),full_page=True)
                job=httpx.get(url+'/api/jobs').json()[0];result=httpx.get(url+'/api/jobs/'+job['id']).json()
                metric=result['summary']['metrics'];assert metric['comparison_version']==2
                assert abs(metric['registered_flux_retained_fraction']-1)<1e-12
                page.set_viewport_size({'width':390,'height':844});overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                external=[request for request in requests if not request.startswith(url+'/')]
                assert not errors and not external and not overflow and font
                summary={'installed_wheel_imports':True,'independent_temporary_workspace':True,'browser':browser.version,
                    'state':result['state'],'japanese_full_support_explanation':True,'japanese_font_loaded':font,
                    'javascript_errors':errors,'external_requests':len(external),'mobile_horizontal_overflow':overflow,
                    'metrics':metric,'scope':'WSL headless Chromium; Windows browser/WSLg desktop not directly observed'}
                browser.close();(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary
        finally:
            process.terminate()
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
            log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--port',type=int,default=8769)
    a=p.parse_args();print(json.dumps(run(a.output,a.port),indent=2))
