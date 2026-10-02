"""Optional real-browser check of the Japanese simulation/validation UI."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import httpx
from playwright.sync_api import sync_playwright


def run(output,port=8767,analysis_manifest=None,clock_model=None):
    root=Path(__file__).resolve().parents[1];out=Path(output)
    if out.exists(): raise FileExistsError('new output required')
    out.mkdir(parents=True);url=f'http://127.0.0.1:{port}'
    log=(out/'server.log').open('w')
    process=subprocess.Popen([sys.executable,str(root/'tools/run.py'),'vsora_ui','--workspace',str(root),'--port',str(port)],
                    cwd=root,stdout=log,stderr=subprocess.STDOUT)
    try:
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            try:
                if httpx.get(url+'/api/environment',timeout=1).status_code==200: break
            except httpx.HTTPError: pass
            time.sleep(.1)
        else: raise AssertionError('GUI server not ready')
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1440,'height':1000})
            errors=[];requests=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('request',lambda request:requests.append(request.url))
            page.goto(url);page.evaluate('document.fonts.ready')
            font=page.evaluate('document.fonts.check("14px \'VSoRA Japanese\'")')
            assert font,'Japanese font did not load'
            page.screenshot(path=str(out/'simulation-screen.png'),full_page=True)
            page.locator('#simulation-form select[name=stations]').select_option('4')
            page.locator('#simulation-form input[name=duration_s]').fill('600');page.locator('#simulation-form input[name=integration_s]').fill('60')
            page.get_by_role('button',name='模擬観測して画像化').click()
            page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=45000)
            assert page.locator('#job-detail img').count()>=2
            page.wait_for_function('Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
            simulation=httpx.get(url+'/api/jobs').json()[0];sid=simulation['id']
            result=httpx.get(url+'/api/jobs/'+sid).json()
            assert abs(result['summary']['imaging']['image_peak_jy']-1000)<1e-6
            page.screenshot(path=str(out/'point-result-screen.png'),full_page=True)
            page.get_by_role('button',name='Closure＋RML',exact=True).click()
            page.screenshot(path=str(out/'rml-screen.png'),full_page=True)
            page.get_by_role('button',name='Closure＋RMLで模擬画像を復元',exact=True).click()
            page.locator('#job-detail h2').get_by_text('Closure＋RMLの模擬画像復元',exact=True).wait_for()
            page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=45000)
            rid=httpx.get(url+'/api/jobs').json()[0]['id'];rresult=httpx.get(url+'/api/jobs/'+rid).json()
            assert rresult['summary']['rml']['input_unit']=='ADC^2'
            assert rresult['summary']['metrics']['registered_nrmse']<.2
            page.wait_for_function('Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
            page.screenshot(path=str(out/'rml-result-screen.png'),full_page=True)
            analysis_result=None
            if analysis_manifest:
                if not clock_model:raise ValueError('analysis clock model required')
                page.get_by_role('button',name='VDIF解析',exact=True).click()
                page.locator('#analysis-form input[name=manifest]').fill(analysis_manifest)
                page.locator('#analysis-form input[name=clock_model]').fill(clock_model)
                page.screenshot(path=str(out/'analysis-screen.png'),full_page=True)
                page.get_by_role('button',name='VDIFを解析して相対画像を作成',exact=True).click()
                page.locator('#job-detail h2').get_by_text('VDIFからClosure＋RMLで解析',exact=True).wait_for()
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=60000)
                aid=httpx.get(url+'/api/jobs').json()[0]['id'];analysis_result=httpx.get(url+'/api/jobs/'+aid).json()
                assert analysis_result['summary']['rml']['input_unit']=='ADC^2'
                assert analysis_result['summary']['closures']['phase_valid']>0
                page.wait_for_function('Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                page.screenshot(path=str(out/'analysis-result-screen.png'),full_page=True)
            page.get_by_role('button',name='動作検証',exact=True).click()
            page.locator('select[name=validation]').select_option('quality')
            page.get_by_role('button',name='検証を開始',exact=True).click()
            page.locator('#job-detail h2').get_by_text('雑音・電波妨害の検証',exact=True).wait_for()
            page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=45000)
            quality=httpx.get(url+'/api/jobs').json()[0];qid=quality['id']
            qresult=httpx.get(url+'/api/jobs/'+qid).json()
            assert qresult['summary']['continuum_visibility_error_after']<.08
            page.screenshot(path=str(out/'quality-result-screen.png'),full_page=True)
            page.get_by_role('button',name='模擬観測',exact=True).click()
            page.locator('#simulation-form select[name=model]').select_option('casa');page.locator('#simulation-form select[name=stations]').select_option('8')
            page.locator('#simulation-form input[name=duration_s]').fill('14400');page.locator('#simulation-form input[name=integration_s]').fill('120')
            page.get_by_role('button',name='模擬観測して画像化').click()
            page.get_by_role('button',name='処理を中止',exact=True).wait_for(timeout=15000)
            cid=httpx.get(url+'/api/jobs').json()[0]['id'];page.get_by_role('button',name='処理を中止',exact=True).click()
            page.locator('#job-detail .phase-line').get_by_text('中止しました',exact=True).wait_for(timeout=15000)
            cancelled=httpx.get(url+'/api/jobs/'+cid).json();assert cancelled['state']=='cancelled'
            page.get_by_role('button',name='模擬観測',exact=True).click();page.set_viewport_size({'width':390,'height':844})
            page.evaluate('document.fonts.ready')
            overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
            page.screenshot(path=str(out/'mobile-screen.png'),full_page=True)
            page.get_by_role('button',name='VDIF解析',exact=True).click()
            overflow=overflow or page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
            page.screenshot(path=str(out/'analysis-mobile-screen.png'),full_page=True)
            external=[x for x in requests if not x.startswith(url+'/')]
            report={'browser':browser.version,'japanese_font_loaded':font,'javascript_errors':errors,
                    'external_requests':len(external),'mobile_horizontal_overflow':overflow,
                    'simulation_state':result['state'],'point_peak_jy_per_beam':result['summary']['imaging']['image_peak_jy'],
                    'quality_state':qresult['state'],'quality_relative_error':qresult['summary']['continuum_visibility_error_after'],
                    'rml_state':rresult['state'],'rml_registered_nrmse':rresult['summary']['metrics']['registered_nrmse'],
                    'analysis_state':analysis_result['state'] if analysis_result else 'not run',
                    'cancel_state':cancelled['state'],'job_ids':[sid,rid,qid,cid],
                    'scope':'Headless Chromium in WSL; Windows browser and WSLg desktop not directly observed'}
            browser.close();(out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
            if errors or external or overflow: raise AssertionError('browser validation failed; see saved summary')
            return report
    finally:
        process.terminate()
        try: process.wait(timeout=8)
        except subprocess.TimeoutExpired: process.kill();process.wait(timeout=2)
        log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--port',type=int,default=8767)
    p.add_argument('--analysis-manifest');p.add_argument('--clock-model')
    a=p.parse_args();print(json.dumps(run(a.output,a.port,a.analysis_manifest,a.clock_model),indent=2))
