"""Installed Japanese smooth-model selection, sequence, failure, and browser."""
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


def run(output,manifest,clock_model,sequence_manifest,sequence_clock,port=8772):
    from vsora_correlator import rate_linear,sequence
    from vsora_ui import models,worker
    assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (rate_linear,sequence,models,worker))
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False);url=f'http://127.0.0.1:{port}'
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-linear-ui-') as directory:
        checkout=Path(__file__).resolve().parents[1]
        (Path(directory)/'tools').mkdir();(Path(directory)/'tools/run.py').symlink_to(checkout/'tools/run.py')
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
                form=page.locator('#analysis-form');assert form.locator('select[name=rate_model]').input_value()=='constant'
                form.locator('input[name=require_rate_consistency]').check()
                form.locator('select[name=rate_model]').select_option('linear')
                assert form.locator('input[name=require_rate_consistency]').is_disabled()
                assert not form.locator('input[name=require_rate_consistency]').is_checked()
                for name,value in [('manifest','inputs/session/'+Path(manifest).name),('clock_model','inputs/clock/'+Path(clock_model).name),('pilot_integrations','1500')]:
                    form.locator(f'input[name={name}]').fill(value)
                form.locator('select[name=integration_s]').select_option('3')
                form.locator('details').evaluate_all('nodes => nodes.forEach(node => node.open = true)')
                form.locator('input[name=starts]').fill('1');form.locator('input[name=max_iterations]').fill('100')
                page.get_by_role('button',name='VDIFを解析して相対画像を作成',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=180000)
                analysis=latest();assert analysis['summary']['rate_model']=='linear'
                assert analysis['summary']['rate_estimate']['type']=='station_rate_linear'
                text=page.locator('#job-detail').inner_text();assert '滑らかな線形rateによるIQ補正' in text and '実測の保持率ではありません' in text and '近似σ' in text
                assert '一定rateで補正した結果です' not in text
                assert '推定誤差だけから計算した条件付き予測' in text and '欠損や除外maskを含みません' in text
                diagnostic=analysis['summary']['rate_estimate']['integration_uncertainty']
                assert not diagnostic['coherence_stability_measured']
                assert f"{100*diagnostic['minimum_expected_centered_complex_coherence']:.4f}%" in text
                page.wait_for_function('Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                page.screenshot(path=str(out/'analysis.png'),full_page=True)
                page.get_by_role('button',name='区間列解析',exact=True).click();form=page.locator('#sequence-form')
                for name,value in [('manifest','inputs/sequence/'+Path(sequence_manifest).name),('clock_model','inputs/sequence-clock/'+Path(sequence_clock).name)]:
                    form.locator(f'input[name={name}]').fill(value)
                form.locator('select[name=rate_model]').select_option('linear')
                form.locator('details').evaluate_all('nodes => nodes.forEach(node => node.open = true)')
                form.locator('input[name=starts]').fill('1');form.locator('input[name=max_iterations]').fill('100')
                page.get_by_role('button',name='複数区間のVDIFをまとめて画像化',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=180000)
                result=latest();assert result['summary']['rate_model']=='linear' and len(result['summary']['windows'])==3
                assert all(w['rate_estimate']['type']=='station_rate_linear' for w in result['summary']['windows'])
                page.locator('#job-detail details').filter(has=page.get_by_text('区間ごとの周波数差とpilot条件',exact=True)).evaluate('node => node.open = true')
                assert page.locator('#job-detail').get_by_text('推定誤差だけから計算した条件付き予測',exact=True).count()==3
                page.wait_for_function('Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                page.screenshot(path=str(out/'sequence.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                result_overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                page.screenshot(path=str(out/'mobile.png'),full_page=True)
                page.get_by_role('button',name='VDIF解析',exact=True).click();form=page.locator('#analysis-form')
                form_overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                form.locator('input[name=pilot_integrations]').fill('16');form.locator('input[name=pilot_integration_s]').fill('.016')
                form.locator('select[name=integration_s]').select_option('0.1')
                form.locator('input[name=max_rate_hz]').fill('25')
                page.get_by_role('button',name='VDIFを解析して相対画像を作成',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理に失敗しました',exact=True).wait_for(timeout=60000)
                failure=latest();assert failure['summary'] is None and failure['completed_steps']==1
                assert failure['rate_consistency']['state']=='unverified' and '4部分の推定が揃いません' in failure['error_message']
                page.screenshot(path=str(out/'unverified.png'),full_page=True)
                page.get_by_role('button',name='VDIF解析',exact=True).click()
                form.locator('select[name=rate_model]').select_option('constant')
                assert not form.locator('input[name=require_rate_consistency]').is_disabled()
                page.get_by_role('button',name='動作検証',exact=True).click()
                page.locator('#validation-form select[name=validation]').select_option('uncertainty')
                page.get_by_role('button',name='検証を開始',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=90000)
                gaussian=latest();assert gaussian['summary']['type']=='rate_uncertainty_validation'
                text=page.locator('#job-detail').inner_text();assert '仮定Gaussian誤差の計算検証' in text and '65,536' in text
                assert '振幅の平均は違う量' in text and '標本の振幅平均' in text
                gaussian_overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                page.wait_for_function('Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                page.screenshot(path=str(out/'gaussian.png'),full_page=True)
                page.evaluate('document.fonts.ready');font=page.evaluate('document.fonts.check("14px \'VSoRA Japanese\'")')
                external=[r for r in requests if not r.startswith(url+'/')]
                assert not errors and not external and not result_overflow and not form_overflow and not gaussian_overflow and font
                summary={'installed_imports':True,'independent_workspace':True,'browser':browser.version,
                    'javascript_errors':errors,'external_requests':len(external),'japanese_font_loaded':font,
                    'mobile_result_horizontal_overflow':result_overflow,'mobile_form_horizontal_overflow':form_overflow,
                    'mobile_gaussian_horizontal_overflow':gaussian_overflow,
                    'validation_workflow_from_checkout':True,'gaussian_validation_state':gaussian['state'],
                    'conditional_diagnostic_displayed':True,'sequence_diagnostics_displayed':3,
                    'model_selection_clears_and_disables_constant_requirement':True,
                    'analysis':{'state':analysis['state'],'model':analysis['summary']['rate_estimate'],'rml':analysis['summary']['rml']},
                    'sequence':{'state':result['state'],'rate_model':result['summary']['rate_model'],
                        'models':[w['rate_estimate'] for w in result['summary']['windows']],
                        'input_identity':result['summary']['input_identity'],'rml':result['summary']['rml']},
                    'unverified':{'state':failure['state'],'completed_steps':failure['completed_steps'],'error_message':failure['error_message']},
                    'scope':'WSL installed headless Chromium, actual synthetic VDIF and RML. One start100 iterations checks protocol/UI; no Windows, hardware or image fidelity claim.'}
                browser.close();(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary
        finally:
            process.terminate()
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
            log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--manifest',required=True)
    p.add_argument('--clock-model',required=True);p.add_argument('--sequence-manifest',required=True);p.add_argument('--sequence-clock',required=True)
    p.add_argument('--port',type=int,default=8772);print(json.dumps(run(**vars(p.parse_args())),indent=2))
