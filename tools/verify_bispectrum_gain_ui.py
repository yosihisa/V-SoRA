"""Actual population gain workflow through Japanese UI, with explicit import origin."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,tempfile,time
import httpx
from playwright.sync_api import sync_playwright


def run(output,port=8784,source_checkout=False):
    from vsora_ui import models,worker
    checkout=Path(__file__).resolve().parents[1]
    module_root=checkout if source_checkout else Path(sys.prefix)
    assert all(Path(m.__file__).is_relative_to(module_root) for m in (models,worker))
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    url=f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory(prefix='vsora-gain-ui-') as folder:
        workspace=Path(folder);(workspace/'tools').mkdir();(workspace/'tools/run.py').symlink_to(checkout/'tools/run.py')
        command=[sys.executable,str(checkout/'tools/run.py'),'vsora_ui'] if source_checkout else [str(Path(sys.prefix)/'bin/vsora-ui')]
        command+=['--workspace',folder,'--port',str(port)]
        log=(out/'server.log').open('w');server=subprocess.Popen(command,cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                try:
                    if httpx.get(url+'/api/environment',timeout=1).status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.1)
            else:raise AssertionError('GUI not ready')
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1000},accept_downloads=True)
                errors=[];requests=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url))
                page.goto(url);page.get_by_role('button',name='動作検証',exact=True).click()
                page.locator('#validation-form select[name=validation]').select_option('bispectrum_gain')
                page.screenshot(path=str(out/'input.png'),full_page=True)
                page.get_by_role('button',name='検証を開始',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=150000)
                job_id=httpx.get(url+'/api/jobs').json()[0]['id'];job=httpx.get(url+'/api/jobs/'+job_id).json();q=job['summary']
                assert job['state']=='complete' and q['type']=='population_bispectrum_gain_validation'
                assert len(q['cases'])==6
                for name in ('observed_statistic_logarithms_taken','extra_station_powers_or_higher_moments_used_as_constraints','noise_likelihood_implemented','physical_adc_vdif_processed','real_hardware_validation_performed','production_rml_noise_model_changed'):assert q[name] is False
                text=page.locator('#job-detail').inner_text()
                for phrase in ('未知の局gainと三次統計の平均制約','母平均は同じ条件で無限回測定','雑音が統計的に独立な測定数ではありません','rankをU₃の雑音共分散のrankとして使いません','全データの分布が同じという反例ではありません','Cas Aの二つの画像を作った実験でもありません','現行RMLの雑音モデルは変更していません'):assert phrase in text
                table=page.locator('#bispectrum-gain-table');assert table.locator('tr').count()==7
                for i,c in enumerate(q['cases']):
                    row=table.locator('tr').nth(i+1);cells=row.locator('td');assert cells.count()==3
                    assert f"{c['stations']}局 / {c['baselines']}基線" in cells.nth(0).inner_text()
                    assert f"{c['triangle_count']}三角形" in cells.nth(0).inner_text()
                    for label,key in [('三角形平均振幅：','gain_invariant_amplitude_rank'),('従来のClosure amplitude：','conventional_logamp_rank')]:assert label+str(c[key]) in cells.nth(1).inner_text()
                    for label,key in [('Closure phase：','closure_phase_rank'),('gainを消す行数：','left_null_weight_rows'),('母平均上の恒等式方向：','zero_identity_directions_in_left_null')]:assert label+str(c[key]) in cells.nth(2).inner_text()
                example=page.locator('#bispectrum-gain-example');assert example.locator('tr').count()==4
                e=q['four_station_example'];assert e['population_means_identical'] and e['all_covariances_positive_definite']
                assert not e['station_powers_identical'] and not e['conditional_u3_covariances_identical']
                for i,(base,matched) in enumerate([('base_population_bispectrum_amplitudes','matched_population_bispectrum_amplitudes'),('base_conventional_logamps','matched_conventional_logamps'),('base_station_powers','matched_station_powers')]):
                    cells=example.locator('tr').nth(i+1).locator('td')
                    for j,key in enumerate((base,matched)):assert ' / '.join(f'{v:.6f}' for v in e[key]) in cells.nth(j+1).inner_text()
                page.wait_for_function('() => Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                caption=page.locator('#job-detail figcaption').inner_text();assert '母平均' in caption and '制約数' in caption and '画像化の可否ではありません' in caption
                assert '画像復元の比較' not in caption
                artifact=next(a for a in job['artifacts'] if a['path']=='validation/summary.json')
                page.get_by_text('条件・画像・相関ファイルを保存',exact=True).click()
                with page.expect_download() as info:
                    page.locator('#job-detail .download-list a').filter(has_text=artifact['path']).click()
                downloaded=info.value.path();assert json.loads(Path(downloaded).read_text())==q
                page.screenshot(path=str(out/'result.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844});overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                page.screenshot(path=str(out/'mobile.png'),full_page=True)
                font=page.evaluate('document.fonts.check("14px VSoRA Japanese")')
                external=[u for u in requests if not u.startswith(url+'/')]
                assert not errors and not external and not overflow and font
                summary={'state':'complete','source_checkout':source_checkout,'installed_imports':not source_checkout,
                    'outside_checkout_workspace':True,'pythonpath_removed':True,'workflow_owned_by_checkout':True,
                    'real_worker_workflow_executed':True,'station_count_conditions':6,'four_station_example_checked':True,'all_display_numbers_checked':True,
                    'json_download_identical':True,'population_constraints_only':True,'caption_checked':True,
                    'japanese_font_loaded':font,'mobile_horizontal_overflow':overflow,'javascript_errors':len(errors),'external_requests':len(external),
                    'noise_likelihood_implemented':False,'actual_hardware_data':False,'production_rml_noise_model_changed':False,
                    'browser_environment':'WSL headless Chromium; Windows/WSLg unverified',
                    'scope':'Complete nonzero population baseline mean constraints; no noisy logs, full likelihood, geometry or imaging feasibility.'}
                browser.close();(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
                (out/'scientific-summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');return summary
        finally:
            server.terminate()
            try:server.wait(timeout=8)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=2)
            log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--port',type=int,default=8784)
    p.add_argument('--source-checkout',action='store_true');print(json.dumps(run(**vars(p.parse_args())),indent=2))
