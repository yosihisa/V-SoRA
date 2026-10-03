"""Installed GUI for a frozen synthetic correlation; no hardware assurance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import httpx
from playwright.sync_api import sync_playwright


def run(input,output,port=8777):
    from vsora_ui import models,worker,noise
    from vsora_correlator import noise_diagnostics
    from vsora_formats.spectral import load_spectral,save_spectral
    assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (models,worker,noise,noise_diagnostics))
    source=Path(input).resolve();out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    original=load_spectral(source);meta=original.pop('metadata')
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    url=f'http://127.0.0.1:{port}';cases=[]
    with tempfile.TemporaryDirectory(prefix='vsora-observation-noise-ui-') as folder:
        workspace=Path(folder);shutil.copyfile(source,workspace/'frozen.npz')
        fixture_id='20261002T080000-00000000';history=workspace/'outputs/gui'/fixture_id
        correlation=history/'analysis/correlation';correlation.mkdir(parents=True)
        shutil.copyfile(source,correlation/'shard-00000.npz')
        (history/'status.json').write_text(json.dumps({'id':fixture_id,'label':'固定相関の履歴fixture','kind':'analysis',
            'state':'complete','phase':'処理完了','created_utc':'2026-10-02T08:00:00Z','completed_steps':5,'total_steps':5}))

        for name in ('old','inactive','low'):
            data={k:v.copy() for k,v in original.items()}
            if name=='old':data.pop('valid_fft_count')
            elif name=='inactive':data['weights'][:]=0
            elif name=='low':data['visibilities']*=1e-4
            save_spectral(workspace/f'{name}.npz',data,meta)
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
                page.goto(url)
                for name,state in [('frozen','conditional_estimate'),('old','unverified'),('inactive','inactive'),('low','conditional_estimate')]:
                    page.get_by_role('button',name='雑音診断',exact=True).click()
                    form=page.locator('#noise-form');form.locator('input[name=input]').fill(name+'.npz')
                    if name=='frozen':
                        page.wait_for_function('() => document.querySelector("#noise-input-history").value.includes("shard-00000.npz")')
                        page.get_by_role('button',name='選んだファイルを入力に使う',exact=True).click()
                        assert form.locator('input[name=input]').input_value()==f'outputs/gui/{fixture_id}/analysis/correlation/shard-00000.npz'

                    assert form.locator('button[type=submit]').is_disabled()
                    page.get_by_role('button',name='入力の時刻・周波数を読む',exact=True).click()
                    page.wait_for_function('() => !document.querySelector("#noise-form button[type=submit]").disabled')
                    channel=len(original['frequencies_hz'])//2
                    assert form.locator('select[name=channel_index]').input_value()==str(channel)
                    assert f"{original['frequencies_hz'][channel]/1e6:.6f} MHz" in form.locator('select[name=channel_index]').inner_text()
                    page.get_by_role('button',name='選んだ場所の雑音を診断',exact=True).click()
                    page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=30000)
                    job_id=httpx.get(url+'/api/jobs').json()[0]['id'];job=httpx.get(url+'/api/jobs/'+job_id).json();q=job['summary']
                    assert job['state']=='complete' and q['state']==state
                    text=page.locator('#job-detail').inner_text();assert 'RMLの重み・採否は変更していません' in text
                    assert not q['iid_fft_independence_verified'] and not q['covariance_confidence_calibrated']
                    if name=='old':assert '旧ファイルの数を推測して補いません' in text
                    elif name=='inactive':assert '有効な基線がありません' in text
                    else:
                        assert '条件付き推定' in text and f"{q['nominal_common_fft_blocks']:,}" in text
                        page.get_by_text('Closure行ごとの誤差と有効状態',exact=True).click()
                        if name=='low':
                            assert not any(q['closure_joint_valid'])
                            assert '未判定（SNR不足）' in text or '未判定（SNR不足）' in page.locator('#job-detail').inner_text()
                            assert set(page.locator('#job-detail details .window-table').last.locator('tr td:last-child').all_text_contents())=={'—'}
                        else:
                            expected=noise_diagnostics.diagnose_noise_cell({**original,'metadata':meta},0,channel)
                            assert q=={**expected,'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
                            page.screenshot(path=str(out/'result.png'),full_page=True)
                    artifact=httpx.get(url+f'/api/jobs/{job_id}/artifacts/noise.json');assert artifact.json()==q
                    cases.append({'fixture':name,'state':q['state'],'nominal_common_fft_blocks':q.get('nominal_common_fft_blocks'),
                                  'valid_closure_rows':sum(q.get('closure_joint_valid',[])),'input_sha256':q['input_sha256']})
                    if name=='low':page.screenshot(path=str(out/'low-snr.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                result_overflow=page.evaluate('() => document.documentElement.scrollWidth>document.documentElement.clientWidth')
                page.screenshot(path=str(out/'mobile-result.png'),full_page=True)
                page.get_by_role('button',name='雑音診断',exact=True).click()
                form=page.locator('#noise-form');form.locator('input[name=input]').fill('missing.npz')
                page.get_by_role('button',name='入力の時刻・周波数を読む',exact=True).click()
                page.get_by_role('alert').get_by_text('相関ファイルの読込に失敗しました。保存済みのspectral NPZを確認してください。',exact=True).wait_for(timeout=5000)
                assert form.locator('button[type=submit]').is_disabled()
                page.set_viewport_size({'width':390,'height':844});overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                page.screenshot(path=str(out/'mobile.png'),full_page=True)
                font=page.evaluate('document.fonts.check("14px \'VSoRA Japanese\'")');external=[r for r in requests if not r.startswith(url+'/')]
                assert not errors and not external and not overflow and not result_overflow and font
                summary={'installed_gui_imports':True,'independent_workspace':True,'browser':browser.version,'cases':cases,
                    'history_selection_fixture_verified':True,'seeded_history_fixture_not_new_scientific_analysis':True,
                    'matches_installed_library':True,'missing_input_error_seen':True,'invalid_closure_rows_not_displayed_as_zero_error':True,
                    'javascript_errors':errors,'external_requests':len(external),'japanese_font_loaded':font,'mobile_horizontal_overflow':overflow,'mobile_result_horizontal_overflow':result_overflow,
                    'actual_hardware_data':False,'iid_fft_independence_verified':False,'production_rml_noise_model_changed':False,
                    'scope':'GUI transport of frozen synthetic NPZ; modified low-SNR/inactive/old statistics fixtures. No actual ADC/FIR covariance accuracy or hardware/image validation.',
                    'browser_environment':'WSL headless Chromium; Windows/WSLg unverified'}
                browser.close();(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary
        finally:
            server.terminate()
            try:server.wait(timeout=8)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=2)
            log.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--port',type=int,default=8777)
    print(json.dumps(run(**vars(parser.parse_args())),indent=2))
