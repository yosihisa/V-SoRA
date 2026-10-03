"""Installed Japanese four-part diagnosis and required-policy browser checks."""
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


def run(output,manifest,clock_model,sequence_manifest,sequence_clock,port=8771):
    from vsora_correlator import rate_variation
    from vsora_ui import models,worker
    assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (rate_variation,models,worker))
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False);url=f'http://127.0.0.1:{port}'
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-rate-diagnostic-ui-') as directory:
        inputs=Path(directory)/'inputs';inputs.mkdir()
        for name,path in [('session',manifest),('clock',clock_model),('sequence',sequence_manifest),('sequence-clock',sequence_clock)]:
            (inputs/name).symlink_to(Path(path).resolve().parent,target_is_directory=True)
        log=(out/'server.log').open('w')
        process=subprocess.Popen([str(Path(sys.prefix)/'bin/vsora-ui'),'--workspace',directory,'--port',str(port)],
                                 cwd=directory,env=env,stdout=log,stderr=subprocess.STDOUT)
        def latest():
            jid=httpx.get(url+'/api/jobs').json()[0]['id'];return httpx.get(url+'/api/jobs/'+jid).json()
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
                errors=[];requests=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('request',lambda r:requests.append(r.url));page.goto(url)
                page.get_by_role('button',name='VDIF解析',exact=True).click()
                for name,value in [('manifest','inputs/session/'+Path(manifest).name),('clock_model','inputs/clock/'+Path(clock_model).name),
                                   ('pilot_integrations','1500')]:page.locator(f'#analysis-form input[name={name}]').fill(value)
                page.locator('#analysis-form select[name=integration_s]').select_option('3')
                page.locator('#analysis-form details').evaluate_all('nodes => nodes.forEach(node => node.open = true)')
                page.locator('#analysis-form input[name=starts]').fill('1');page.locator('#analysis-form input[name=max_iterations]').fill('100')
                assert not page.locator('#analysis-form input[name=require_rate_consistency]').is_checked()
                page.get_by_role('button',name='VDIFを解析して相対画像を作成',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=120000)
                report=latest();assert report['summary']['rate_consistency']['state']=='variation_detected'
                assert '周波数差の変動を検出' in page.locator('#job-detail').inner_text()
                page.locator('#job-detail details').filter(has=page.get_by_text('分割した各部分の推定値',exact=True)).evaluate('node => node.open = true')
                page.wait_for_function('Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                page.screenshot(path=str(out/'report-result.png'),full_page=True)
                page.get_by_role('button',name='VDIF解析',exact=True).click()
                page.locator('#analysis-form input[name=require_rate_consistency]').check()
                page.get_by_role('button',name='VDIFを解析して相対画像を作成',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理に失敗しました',exact=True).wait_for(timeout=90000)
                required=latest();assert required['rate_consistency']['state']=='variation_detected' and required['summary'] is None
                assert '分割rateの整合を必須' in page.locator('#job-detail').inner_text()
                page.wait_for_function('Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                page.screenshot(path=str(out/'required-stop.png'),full_page=True)
                page.get_by_role('button',name='区間列解析',exact=True).click()
                for name,value in [('manifest','inputs/sequence/'+Path(sequence_manifest).name),
                                   ('clock_model','inputs/sequence-clock/'+Path(sequence_clock).name)]:
                    page.locator(f'#sequence-form input[name={name}]').fill(value)
                page.locator('#sequence-form details').evaluate_all('nodes => nodes.forEach(node => node.open = true)')
                page.locator('#sequence-form input[name=starts]').fill('1');page.locator('#sequence-form input[name=max_iterations]').fill('100')
                page.get_by_role('button',name='複数区間のVDIFをまとめて画像化',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=120000)
                sequence=latest();assert len(sequence['summary']['windows'])==3
                assert sum(sequence['summary']['rate_consistency']['window_counts'].values())==3
                assert not sequence['summary']['rate_consistency']['coherence_stability_measured']
                page.wait_for_function('Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                page.screenshot(path=str(out/'sequence-diagnosis.png'),full_page=True)
                # Required policy is forwarded and the first window's diagnosis survives failure.
                page.get_by_role('button',name='区間列解析',exact=True).click()
                for name,value in [('manifest','inputs/session/'+Path(manifest).name),('clock_model','inputs/clock/'+Path(clock_model).name),
                                   ('window_count','2'),('pilot_integrations','1500')]:
                    page.locator(f'#sequence-form input[name={name}]').fill(value)
                page.locator('#sequence-form select[name=integration_s]').select_option('3')
                page.locator('#sequence-form input[name=require_rate_consistency]').check()
                page.get_by_role('button',name='複数区間のVDIFをまとめて画像化',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理に失敗しました',exact=True).wait_for(timeout=90000)
                failed_sequence=latest();assert failed_sequence['rate_consistency']['state']=='variation_detected'
                assert failed_sequence['sequence_failure']['completed_window_count']==0
                assert failed_sequence['sequence_failure']['current_window_index']==0
                assert '停止した箇所：区間 1' in page.locator('#job-detail').inner_text()
                page.screenshot(path=str(out/'sequence-required-stop.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                result_overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                page.get_by_role('button',name='VDIF解析',exact=True).click()
                form_overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                page.evaluate('document.fonts.ready');font=page.evaluate('document.fonts.check("14px \'VSoRA Japanese\'")')
                external=[r for r in requests if not r.startswith(url+'/')]
                assert not errors and not external and not result_overflow and not form_overflow and font
                summary={'installed_wheel_imports':True,'independent_temporary_workspace':True,'browser':browser.version,
                    'javascript_errors':errors,'external_requests':len(external),'japanese_font_loaded':font,
                    'mobile_result_horizontal_overflow':result_overflow,'mobile_form_horizontal_overflow':form_overflow,
                    'report':{'state':report['state'],'diagnosis':report['summary']['rate_consistency'],'rml':report['summary']['rml']},
                    'required':{'state':required['state'],'completed_steps':required['completed_steps'],'diagnosis':required['rate_consistency'],'error_message':required['error_message']},
                    'sequence':{'state':sequence['state'],'diagnosis':sequence['summary']['rate_consistency']},
                    'required_sequence':{'state':failed_sequence['state'],'sequence_failure':failed_sequence['sequence_failure'],'diagnosis':failed_sequence['rate_consistency']},
                    'scope':'WSL headless Chromium. Report mode allows constant-rate image exploration with diagnosis; required mode stops before image. No Windows desktop, phase coherence proof or image fidelity claim.'}
                browser.close();(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary
        finally:
            process.terminate()
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
            log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--manifest',required=True)
    p.add_argument('--clock-model',required=True);p.add_argument('--sequence-manifest',required=True);p.add_argument('--sequence-clock',required=True)
    p.add_argument('--port',type=int,default=8771);print(json.dumps(run(**vars(p.parse_args())),indent=2))
