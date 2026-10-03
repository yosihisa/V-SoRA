"""Installed GUI transport of frozen Stage051 pilot; constructed weak/old fixtures."""
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


def run(archive,source_profiles,output,port=8777):
    from vsora_ui import models,worker,noise
    from vsora_correlator import time_scatter
    from vsora_formats.spectral import load_spectral,save_spectral
    assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (models,worker,noise,time_scatter))
    archive=Path(archive).resolve();profiles=Path(source_profiles).resolve();out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    url=f'http://127.0.0.1:{port}';cases=[]
    with tempfile.TemporaryDirectory(prefix='vsora-time-scatter-ui-') as folder:
        workspace=Path(folder)
        for name in ('fast','control'):
            shutil.copyfile(archive/name/'pilot/shard-00000.npz',workspace/f'{name}.npz')
        shutil.copyfile(profiles/'fast-linear/rate-linear.json',workspace/'fast-rate.json')
        shutil.copyfile(profiles/'control-constant/rate-only.json',workspace/'control-rate.json')
        original=load_spectral(workspace/'fast.npz');meta=original.pop('metadata')
        for name in ('old','weak','double'):
            data={k:v.copy() for k,v in original.items()};metadata=dict(meta)
            if name=='old':data.pop('valid_fft_count')
            elif name=='weak':data['visibilities'][:]=0
            else:metadata['rate_profile_type']='station_rate_linear'
            save_spectral(workspace/f'{name}.npz',data,metadata)
        fixture_id='20261003T080000-00000000';history=workspace/'outputs/gui'/fixture_id
        pilot=history/'analysis/pilot';pilot.mkdir(parents=True);shutil.copyfile(workspace/'fast.npz',pilot/'shard-00000.npz')
        (history/'status.json').write_text(json.dumps({'id':fixture_id,'label':'固定pilotの履歴fixture','kind':'analysis',
            'state':'complete','phase':'処理完了','created_utc':'2026-10-03T08:00:00Z','completed_steps':5,'total_steps':5}))
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
                browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1100})
                errors=[];requests=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url));page.goto(url)
                for name,state in [('fast','conditional_estimate'),('control','conditional_estimate'),('old','unverified'),('weak','conditional_estimate')]:
                    page.get_by_role('button',name='雑音診断',exact=True).click();form=page.locator('#noise-form')
                    form.locator('select[name=diagnostic_mode]').select_option('time_scatter')
                    form.locator('input[name=input]').fill(name+'.npz')
                    if name=='fast':
                        page.wait_for_function('() => document.querySelector("#noise-input-history").value.includes("pilot/shard-00000.npz")')
                        page.get_by_role('button',name='選んだファイルを入力に使う',exact=True).click()
                        assert form.locator('input[name=input]').input_value()==f'outputs/gui/{fixture_id}/analysis/pilot/shard-00000.npz'
                    assert form.locator('button[type=submit]').is_disabled()
                    form.locator('input[name=rate_profile]').fill('control-rate.json' if name=='control' else 'fast-rate.json')
                    page.get_by_role('button',name='入力の時刻・周波数を読む',exact=True).click()
                    page.wait_for_function('() => !document.querySelector("#noise-form button[type=submit]").disabled')
                    assert form.locator('select[name=time_index]').is_disabled()
                    assert form.locator('select[name=channel_index]').input_value()=='16'
                    assert '1420.000000 MHz' in form.locator('select[name=channel_index]').inner_text()
                    with page.expect_response(lambda r:r.request.method=='POST' and r.url==url+'/api/jobs') as created:
                        page.get_by_role('button',name='時間方向の散らばりを診断',exact=True).click()
                    job_id=created.value.json()['id']
                    page.locator('#job-detail').get_by_text(job_id,exact=True).wait_for(timeout=5000)
                    page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=30000)
                    job=httpx.get(url+'/api/jobs/'+job_id).json();q=job['summary']
                    assert job['state']=='complete' and q['state']==state
                    text=page.locator('#job-detail').inner_text();assert 'RMLの重み・採否は変更していません' in text
                    assert not q['hardware_coherence_measured'] and not q['covariance_confidence_calibrated']
                    if name=='old':assert '条件を満たさない時間cell' in text
                    else:
                        values=page.locator('#time-scatter-table tr td:last-child').all_text_contents()
                        assert len(values)==6
                        if name=='weak':assert values==['—']*6 and '未判定（信号power不足）' in text
                        else:
                            assert values==[f"{b['mean_to_time_power_ratio_unbounded']:.6f}" for b in q['baselines']]
                            if name=='fast':assert min(b['mean_to_time_power_ratio_unbounded'] for b in q['baselines'])<.8
                            else:assert min(b['mean_to_time_power_ratio_unbounded'] for b in q['baselines'])>.97
                    actual_input=workspace/form.locator('input[name=input]').input_value()
                    profile=workspace/('control-rate.json' if name=='control' else 'fast-rate.json')
                    expected=time_scatter.diagnose_time_scatter(load_spectral(actual_input),16,json.loads(profile.read_text()))
                    assert q=={**expected,'input_sha256':hashlib.sha256(actual_input.read_bytes()).hexdigest(),'rate_profile_sha256':hashlib.sha256(profile.read_bytes()).hexdigest()}
                    assert httpx.get(url+f'/api/jobs/{job_id}/artifacts/time-scatter.json').json()==q
                    cases.append({'fixture':name,'state':q['state'],'valid_baselines':sum(b['state']=='conditional_estimate' for b in q.get('baselines',[])),
                        'ratios':[b['mean_to_time_power_ratio_unbounded'] for b in q.get('baselines',[])],'input_sha256':q['input_sha256']})
                    if name=='fast':page.screenshot(path=str(out/'result.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                overflow=page.evaluate('() => document.documentElement.scrollWidth>document.documentElement.clientWidth')
                page.screenshot(path=str(out/'mobile-result.png'),full_page=True)
                page.get_by_role('button',name='雑音診断',exact=True).click();form=page.locator('#noise-form')
                form.locator('input[name=input]').fill('double.npz');form.locator('input[name=rate_profile]').fill('fast-rate.json')
                page.get_by_role('button',name='入力の時刻・周波数を読む',exact=True).click()
                page.wait_for_function('() => !document.querySelector("#noise-form button[type=submit]").disabled')
                form.locator('select[name=diagnostic_mode]').select_option('noise');assert form.locator('select[name=time_index]').is_enabled()
                assert form.locator('input[name=rate_profile]').is_disabled()
                form.locator('select[name=diagnostic_mode]').select_option('time_scatter')
                input_overflow=page.evaluate('() => document.documentElement.scrollWidth>document.documentElement.clientWidth')
                page.screenshot(path=str(out/'mobile-input.png'),full_page=True)
                page.get_by_role('button',name='時間方向の散らばりを診断',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理に失敗しました',exact=True).wait_for(timeout=30000)
                assert '保存相関はrate補正済み' in page.locator('#job-detail').inner_text()
                font=page.evaluate('() => document.fonts.check("14px \'VSoRA Japanese\'")');external=[r for r in requests if not r.startswith(url+'/')]
                assert not errors and not external and not overflow and not input_overflow and font
                summary={'state':'complete','installed_gui_imports':True,'independent_workspace':True,'browser':browser.version,'cases':cases,
                    'history_selection_fixture_verified':True,'seeded_history_fixture_not_new_analysis':True,
                    'matches_installed_library':True,'json_download_verified':True,'mode_switch_preserves_axes':True,'double_correction_failure_japanese':True,
                    'nonpositive_power_ratio_displayed_as_unverified':True,'javascript_errors':errors,'external_requests':len(external),'japanese_font_loaded':font,
                    'mobile_horizontal_overflow':overflow,'mobile_input_horizontal_overflow':input_overflow,
                    'actual_hardware_data':False,'hardware_coherence_measured':False,'production_rml_noise_model_changed':False,
                    'scope':'Frozen Stage051 synthetic VDIF-derived pilot and constructed old/zero-visibility fixtures. GUI transport only; no hardware covariance or confidence.',
                    'browser_environment':'WSL headless Chromium; Windows/WSLg unverified'}
                browser.close();(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary
        finally:
            server.terminate()
            try:server.wait(timeout=8)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=2)
            log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',required=True);p.add_argument('--source-profiles',required=True);p.add_argument('--output',required=True);p.add_argument('--port',type=int,default=8777)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
