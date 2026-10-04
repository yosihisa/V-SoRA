"""Installed Japanese sequence GUI in an independent temporary workspace."""
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


def run(output,manifest,clock_model,short_manifest,short_clock,port=8770,save_bispectrum=False):
    from vsora_correlator import sequence
    from vsora_ui import models,worker
    if not all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (sequence,models,worker)):
        raise AssertionError('installed wheel imports required')
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False);url=f'http://127.0.0.1:{port}'
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-sequence-ui-') as directory:
        inputs=Path(directory)/'inputs';inputs.mkdir()
        for name,path in [('session',manifest),('clock',clock_model),('short',short_manifest),('short-clock',short_clock)]:
            (inputs/name).symlink_to(Path(path).resolve().parent,target_is_directory=True)
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
                page.get_by_role('button',name='区間列解析',exact=True).click()
                page.locator('#sequence-form input[name=manifest]').fill('inputs/session/'+Path(manifest).name)
                page.locator('#sequence-form input[name=clock_model]').fill('inputs/clock/'+Path(clock_model).name)
                page.locator('#sequence-form details').evaluate_all('nodes => nodes.forEach(node => node.open = true)')
                page.locator('#sequence-form input[name=starts]').fill('1')
                page.locator('#sequence-form input[name=max_iterations]').fill('100')
                assert page.locator('#sequence-form input[name=step_s]').input_value()==''
                if save_bispectrum:
                    assert not page.locator('#sequence-form input[name=save_bispectrum]').is_checked()
                    page.locator('#sequence-form input[name=save_bispectrum]').check()
                page.screenshot(path=str(out/'sequence-input.png'),full_page=True)
                page.get_by_role('button',name='複数区間のVDIFをまとめて画像化',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=90000)
                page.locator('#job-detail details').filter(has=page.get_by_text('区間ごとの周波数差とpilot条件',exact=True)).evaluate('node => node.open = true')
                page.wait_for_function('Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                text=page.locator('#job-detail').inner_text()
                assert '0.90 秒' in text and '10 / 10 工程' in text and '区間の間は補間していません' in text
                rate_details=page.locator('#job-detail details').filter(has=page.get_by_text('区間ごとの周波数差とpilot条件',exact=True))
                assert rate_details.locator('table tr').count()==4
                page.evaluate('document.fonts.ready');font=page.evaluate('document.fonts.check("14px \'VSoRA Japanese\'")')
                page.screenshot(path=str(out/'sequence-result.png'),full_page=True)
                jid=httpx.get(url+'/api/jobs').json()[0]['id'];complete=httpx.get(url+'/api/jobs/'+jid).json()
                q=complete['summary'];assert q['completed_windows']==[0,1,2] and abs(q['rml']['image_sum']-1)<1e-12
                assert q['rml']['input_unit']=='ADC^2'
                raw_records=[]
                if save_bispectrum:
                    from vsora_formats.bispectrum import load_bispectrum
                    import numpy as np
                    assert '再解析用の三次統計' in text and '今回の画像は従来のClosure' in text
                    for w in q['windows']:
                        raw=w['correlation']['raw_bispectrum'];counts=np.array(raw['common_fft_count']).reshape(-1)
                        assert ('三局共通FFT数：'+str(counts.min())+'〜'+str(counts.max())) in text
                        assert ('利用可channel・三角形：'+str(raw['usable_channel_triangles'])+' / '+str(raw['total_channel_triangles'])) in text
                        assert ('追加ファイル：'+format(raw['bytes']/1024,'.1f')+' KiB') in text
                        relative='sequence/'+w['relative_directory']+'/correlation/'
                        local=out/('download-window-'+str(w['window_index']));local.mkdir()
                        for name in ('raw-bispectrum.npz','shard-00000.npz'):
                            response=httpx.get(url+f'/api/jobs/{jid}/artifacts/'+relative+name);assert response.status_code==200
                            (local/name).write_bytes(response.content)
                        checked=load_bispectrum(local/'raw-bispectrum.npz',local/'shard-00000.npz')
                        assert checked['source_visibility_verified'] and not checked['metadata']['production_rml_noise_model_changed']
                        raw_records.append({'window_index':w['window_index'],**raw})
                # Preserve independent installed GUI numeric diagnostics, not its local workspace paths.
                (out/'rates.png').write_bytes(httpx.get(url+f'/api/jobs/{jid}/artifacts/sequence/rates.png').content)
                page.set_viewport_size({'width':390,'height':844})
                overflow_result=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                page.screenshot(path=str(out/'sequence-mobile.png'),full_page=True)
                page.get_by_role('button',name='区間列解析',exact=True).click()
                overflow_form=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                page.set_viewport_size({'width':1440,'height':1000})
                for name,value in [('manifest','inputs/short/'+Path(short_manifest).name),
                                   ('clock_model','inputs/short-clock/'+Path(short_clock).name),('window_count','2')]:
                    page.locator(f'#sequence-form input[name={name}]').fill(value)
                page.get_by_role('button',name='複数区間のVDIFをまとめて画像化',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理に失敗しました',exact=True).wait_for(timeout=60000)
                assert '完了した区間：1 / 2' in page.locator('#job-detail').inner_text()
                assert '停止した箇所：区間 2' in page.locator('#job-detail').inner_text()
                fid=httpx.get(url+'/api/jobs').json()[0]['id'];failed=httpx.get(url+'/api/jobs/'+fid).json()
                assert failed['state']=='failed' and failed['summary'] is None
                page.screenshot(path=str(out/'sequence-failed.png'),full_page=True)
                # Start another actual scientific subprocess, then cancel it from the browser.
                page.get_by_role('button',name='区間列解析',exact=True).click()
                page.get_by_role('button',name='複数区間のVDIFをまとめて画像化',exact=True).click()
                cid=httpx.get(url+'/api/jobs').json()[0]['id']
                deadline=time.monotonic()+10
                while time.monotonic()<deadline:
                    if httpx.get(url+'/api/jobs/'+cid).json()['state']=='running':break
                    time.sleep(.1)
                else:raise AssertionError('cancel test did not reach running subprocess')
                page.get_by_role('button',name='処理を中止',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('中止しました',exact=True).wait_for(timeout=10000)
                cancelled=httpx.get(url+'/api/jobs/'+cid).json();assert cancelled['state']=='cancelled'
                analysis_storage=None
                if save_bispectrum:
                    page.get_by_role('button',name='VDIF解析',exact=True).click()
                    page.locator('#analysis-form input[name=manifest]').fill('inputs/short/'+Path(short_manifest).name)
                    page.locator('#analysis-form input[name=clock_model]').fill('inputs/short-clock/'+Path(short_clock).name)
                    page.locator('#analysis-form details').evaluate_all('nodes => nodes.forEach(node => node.open = true)')
                    page.locator('#analysis-form input[name=starts]').fill('1')
                    page.locator('#analysis-form input[name=max_iterations]').fill('100')
                    assert not page.locator('#analysis-form input[name=save_bispectrum]').is_checked()
                    page.locator('#analysis-form input[name=save_bispectrum]').check()
                    page.get_by_role('button',name='VDIFを解析して相対画像を作成',exact=True).click()
                    page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=60000)
                    aid=httpx.get(url+'/api/jobs').json()[0]['id'];analysis=httpx.get(url+'/api/jobs/'+aid).json()
                    ar=analysis['summary']['correlation']['raw_bispectrum'];at=page.locator('#job-detail').inner_text()
                    counts=np.array(ar['common_fft_count']).reshape(-1)
                    assert ('三局共通FFT数：'+str(counts.min())+'〜'+str(counts.max())) in at
                    assert ('利用可channel・三角形：'+str(ar['usable_channel_triangles'])+' / '+str(ar['total_channel_triangles'])) in at
                    assert ('追加ファイル：'+format(ar['bytes']/1024,'.1f')+' KiB') in at
                    local=out/'download-analysis';local.mkdir()
                    for name in ('raw-bispectrum.npz','shard-00000.npz'):
                        response=httpx.get(url+f'/api/jobs/{aid}/artifacts/analysis/correlation/'+name);assert response.status_code==200
                        (local/name).write_bytes(response.content)
                    checked=load_bispectrum(local/'raw-bispectrum.npz',local/'shard-00000.npz')
                    assert checked['source_visibility_verified']
                    page.wait_for_function('Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                    page.screenshot(path=str(out/'analysis-storage.png'),full_page=True)
                    page.set_viewport_size({'width':390,'height':844})
                    analysis_overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                    page.screenshot(path=str(out/'analysis-storage-mobile.png'),full_page=True)
                    assert not analysis_overflow
                    analysis_storage={'state':analysis['state'],'completed_steps':analysis['completed_steps'],
                        'raw_bispectrum':ar,'download_source_verified':True,'mobile_horizontal_overflow':analysis_overflow}
                external=[r for r in requests if not r.startswith(url+'/')]
                assert not errors and not external and not overflow_form and not overflow_result and font
                summary={'installed_wheel_imports':True,'independent_temporary_workspace':True,'browser':browser.version,
                    'raw_bispectrum_requested':save_bispectrum,'raw_bispectrum_downloads':raw_records,
                    'analysis_storage':analysis_storage,
                    'japanese_font_loaded':font,'javascript_errors':errors,'external_requests':len(external),
                    'mobile_form_horizontal_overflow':overflow_form,'mobile_result_horizontal_overflow':overflow_result,
                    'complete':{'state':complete['state'],'completed_steps':complete['completed_steps'],
                        'total_steps':complete['total_steps'],'sequence':q},
                    'failed':{'state':failed['state'],'error_message':failed['error_message'],'sequence_failure':failed['sequence_failure']},
                    'cancelled':{'state':cancelled['state'],'reached_running_subprocess':True},
                    'scope':'WSL headless Chromium; Windows browser/WSLg desktop not directly observed'}
                browser.close();(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary
        finally:
            process.terminate()
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
            log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--manifest',required=True)
    p.add_argument('--clock-model',required=True);p.add_argument('--short-manifest',required=True);p.add_argument('--short-clock',required=True)
    p.add_argument('--save-bispectrum',action='store_true');p.add_argument('--port',type=int,default=8770);a=vars(p.parse_args());print(json.dumps(run(**a),indent=2))
