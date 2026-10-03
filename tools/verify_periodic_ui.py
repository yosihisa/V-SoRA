"""Installed GUI invoking checkout-owned periodic validation workflow."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,tempfile,time
import httpx
from playwright.sync_api import sync_playwright


def run(output,port=8773):
    from vsora_ui import models,jobs,worker
    assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (models,jobs,worker))
    checkout=Path(__file__).resolve().parents[1]
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False);url=f'http://127.0.0.1:{port}'
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-periodic-ui-') as directory:
        workspace=Path(directory);(workspace/'tools').mkdir();(workspace/'tools/run.py').symlink_to(checkout/'tools/run.py')
        log=(out/'server.log').open('w');process=subprocess.Popen([str(Path(sys.prefix)/'bin/vsora-ui'),
            '--workspace',directory,'--port',str(port)],cwd=directory,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                try:
                    if httpx.get(url+'/api/environment',timeout=1).status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.1)
            else:raise AssertionError('GUI not ready')
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1050})
                errors=[];requests=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url))
                page.goto(url);page.get_by_role('button',name='動作検証',exact=True).click()
                page.locator('#validation-form select[name=validation]').select_option('phase')
                page.get_by_role('button',name='検証を開始',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=300000)
                jid=httpx.get(url+'/api/jobs').json()[0]['id'];job=httpx.get(url+'/api/jobs/'+jid).json();q=job['summary']
                assert q['type']=='periodic_phase_validation' and not q['actual_hardware_data']
                fast=next(r for r in q['cases'] if r['case']=='fast' and r['rate_model']=='linear')
                assert fast['state']=='complete' and fast['diagnosis']['state']=='consistent'
                assert min(fast['measured_amplitude_ratio_to_same_noise_control'])<.9
                assert next(r['state'] for r in q['cases'] if r['case']=='slow')=='incomplete'
                text=page.locator('#job-detail').inner_text();assert '仮定した周期位相変動の結果' in text and '実機の相関保持率を測定した結果ではありません' in text
                assert '相関処理は未完了' in text and '84.59%' in text
                page.wait_for_function('Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                page.screenshot(path=str(out/'result.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844});overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                page.screenshot(path=str(out/'mobile.png'),full_page=True)
                page.evaluate('document.fonts.ready');font=page.evaluate('document.fonts.check("14px \'VSoRA Japanese\'")')
                external=[r for r in requests if not r.startswith(url+'/')]
                assert not errors and not external and not overflow and font
                summary={'installed_gui_imports':True,'validation_workflow_from_checkout':True,'independent_workspace':True,
                    'browser':browser.version,'javascript_errors':errors,'external_requests':len(external),
                    'japanese_font_loaded':font,'mobile_horizontal_overflow':overflow,'state':job['state'],
                    'cases':[{'case':r['case'],'model':r['rate_model'],'state':r['state'],'diagnosis':r['diagnosis']['state']} for r in q['cases']],
                    'fast_linear_minimum_amplitude_ratio':min(fast['measured_amplitude_ratio_to_same_noise_control']),
                    'scope':'Installed GUI with explicitly checkout-owned validation runner. Synthetic point-noise IQ/VDIF, not Windows browser, WSLg, hardware or Cas A image fidelity.'}
                browser.close();(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary
        finally:
            process.terminate()
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
            log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--port',type=int,default=8773)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
