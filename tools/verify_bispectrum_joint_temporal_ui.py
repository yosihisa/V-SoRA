"""Actual joint station/time mean comparison through Japanese UI, with explicit import origin."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,tempfile,time
import httpx
from playwright.sync_api import sync_playwright


def run(output,port=8788,source_checkout=False):
    from vsora_ui import models,worker
    checkout=Path(__file__).resolve().parents[1]
    module_root=checkout if source_checkout else Path(sys.prefix)
    assert all(Path(m.__file__).is_relative_to(module_root) for m in (models,worker))
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    url=f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory(prefix='vsora-joint-time-ui-') as folder:
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
                page.locator('#validation-form select[name=validation]').select_option('joint_temporal_bispectrum')
                page.screenshot(path=str(out/'input.png'),full_page=True)
                page.get_by_role('button',name='検証を開始',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=150000)
                job_id=httpx.get(url+'/api/jobs').json()[0]['id'];job=httpx.get(url+'/api/jobs/'+job_id).json();q=job['summary']
                assert job['state']=='complete' and q['type']=='joint_station_time_bispectrum_validation'
                assert q==json.loads((checkout/'validation/runs/stage078/known-joint-time.json').read_text())
                assert len(q['cases'])==12 and q['trials_per_case']==8192 and q['known_inverse_phase_supplied']
                for key in ('physical_adc_vdif_processed','actual_temporal_independence_verified','observed_gain_or_clock_estimated','covariance_of_bispectrum_calculated','gaussian_u3_distribution_verified','production_rml_noise_model_changed','real_hardware_validation_performed'):assert q[key] is False
                text=page.locator('#job-detail').inner_text()
                for phrase in ('局別時間変化と三次統計の平均（既知補正）','逆位相は真値を供給しています','弱い実観測から周波数差を推定できた結果ではありません','実FFT数や帯域×時間の標本数へ換算しません'):assert phrase in text
                def number(value):return f'{float(value):.4e}'.replace('e-0','e-').replace('e+0','e+')
                def complex_value(v):return number(v[0])+(' + ' if v[1]>=0 else ' − ')+number(abs(v[1]))+' i'
                def table_rows(selector):return page.locator(selector).evaluate('(t)=>Array.from(t.querySelectorAll("tr")).slice(1).map(r=>Array.from(r.querySelectorAll("td")).map(c=>c.innerText))')
                models={'white':'白色時間','common_correlated':'共通時間相関','station_coefficients':'局別線形係数'}
                states={'uncorrected':'位相変更後','known_inverse_phase':'与えた逆位相後'};methods={'distinct':'U₃','ordinary':'通常積'}
                rows=table_rows('#joint-time-table');assert len(rows)==12
                for c,cells in zip(q['cases'],rows):
                    assert models[c['coefficient_model']] in cells[0] and str(c['stations'])+'局' in cells[0]
                    assert f"位相係数 {c['known_phase_cycles_multiplier']:g}" in cells[0]
                    assert f"M={c['samples']} / seed={c['seed']}" in cells[0] and c['triangles'][0]==[0,1,2]
                    assert complex_value(c['mean_instantaneous_population_bispectrum_real_imag'][0]) in cells[0]
                    for state in states:
                        assert states[state]+'：'+complex_value(c['methods'][state]['distinct']['known_mean_real_imag'][0]) in cells[1]
                        assert states[state]+'：'+complex_value(c['methods'][state]['ordinary']['known_mean_real_imag'][0]) in cells[2]
                    assert c['all_calculated_means_and_known_phase_invariance_checked'] and '全平均が固定6反復標準誤差基準内' in cells[3]
                    assert '元の標本との差 '+number(c['maximum_sample_statistic_after_known_inverse_phase_difference']) in cells[3]
                    assert '瞬間の母積の差 '+number(c['maximum_instant_population_phase_difference']) in cells[3]
                page.locator('#joint-time-all-details summary').click();rows=table_rows('#joint-time-all-table');assert len(rows)==816
                index=0
                for c in q['cases']:
                    n=len(c['triangles'])
                    for i,t in enumerate(c['triangles']):
                        for state in states:
                            for name in methods:
                                d=c['methods'][state][name];cells=rows[index]
                                assert '-'.join(str(v) for v in t) in cells[0] and states[state] in cells[0] and methods[name] in cells[0]
                                assert '既知式 '+complex_value(d['known_mean_real_imag'][i]) in cells[1]
                                assert '反復平均 '+complex_value(d['ensemble_mean_real_imag'][i]) in cells[1]
                                assert ' / '.join(number(d['mean_mc_standard_error_all_real_then_imag'][j]) for j in (i,i+n))==cells[2];index+=1
                page.locator('#joint-time-all-details summary').click()
                text=page.locator('#job-detail').inner_text();assert '実観測のU₃の雑音σではありません' in text and '現行RMLの重みは変更していません' in text
                page.wait_for_function('() => Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                caption=page.locator('#job-detail figcaption').inner_text();assert '母平均の絶対値の比' in caption and '位相は真値を供給' in caption and '実LO推定' in caption
                artifact=next(a for a in job['artifacts'] if a['path']=='validation/summary.json')
                page.get_by_text('条件・画像・相関ファイルを保存',exact=True).click()
                with page.expect_download() as info:page.locator('#job-detail .download-list a').filter(has_text=artifact['path']).click()
                assert json.loads(Path(info.value.path()).read_text())==q
                page.screenshot(path=str(out/'result.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844});overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                page.screenshot(path=str(out/'mobile.png'),full_page=True)
                font=page.evaluate('document.fonts.check("14px VSoRA Japanese")');external=[u for u in requests if not u.startswith(url+'/')]
                assert not errors and not external and not overflow and font
                summary={'state':'complete','source_checkout':source_checkout,'installed_imports':not source_checkout,'outside_checkout_workspace':True,'pythonpath_removed':True,'workflow_owned_by_checkout':True,
                    'real_worker_workflow_executed':True,'conditions':12,'all_triangle_method_rows_checked':816,'all_display_numbers_checked':True,
                    'entire_scientific_result_identical_to_stage078':True,'json_download_identical':True,'caption_checked':True,'known_inverse_phase_and_model_sample_limits_visible':True,
                    'japanese_font_loaded':font,'mobile_horizontal_overflow':overflow,'javascript_errors':len(errors),'external_requests':len(external),
                    'observed_gain_or_clock_estimated':False,'covariance_of_bispectrum_calculated':False,'actual_hardware_data':False,'production_rml_noise_model_changed':False,
                    'browser_environment':'WSL headless Chromium; Windows/WSLg unverified'}
                browser.close();(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
                (out/'scientific-summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');return summary
        finally:
            server.terminate()
            try:server.wait(timeout=8)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=2)
            log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--port',type=int,default=8788)
    p.add_argument('--source-checkout',action='store_true');print(json.dumps(run(**vars(p.parse_args())),indent=2))
