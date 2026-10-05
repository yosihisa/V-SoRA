"""Native array-scale comparison through Japanese UI, with explicit import origin."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,tempfile,time
import httpx
from playwright.sync_api import sync_playwright


def run(output,port=8791,source_checkout=False):
    from vsora_ui import models,worker
    checkout=Path(__file__).resolve().parents[1]
    module_root=checkout if source_checkout else Path(sys.prefix)
    assert all(Path(m.__file__).is_relative_to(module_root) for m in (models,worker))
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    url=f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory(prefix='vsora-array-scale-ui-') as folder:
        workspace=Path(folder);assert not (workspace/'tools/run.py').exists()
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
                capability=httpx.get(url+'/api/environment').json();assert capability['available_validations']==['array_scale'] and not capability['checkout_validation_available']
                page.wait_for_function('() => document.querySelector("#validation-form select").value === "array_scale"')
                assert page.locator('#validation-form button').is_enabled()
                assert page.locator('#validation-form select option:enabled').count()==1
                page.locator('#validation-form select[name=validation]').select_option('array_scale')
                page.screenshot(path=str(out/'input.png'),full_page=True)
                page.get_by_role('button',name='検証を開始',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=90000)
                job_id=httpx.get(url+'/api/jobs').json()[0]['id'];job=httpx.get(url+'/api/jobs/'+job_id).json();q=job['summary']
                assert job['state']=='complete' and q['type']=='array_scale_known_sky_comparison'
                origin=httpx.get(url+f'/api/jobs/{job_id}/artifacts/validation/execution-origin.json').json()
                assert origin['native_scientific_module_used'] and not origin['checkout_runner_used']
                for key in ('scientific_modules_under_runtime_prefix','configuration_asset_under_runtime_prefix','sky_asset_under_runtime_prefix'):assert origin[key] is (not source_checkout)
                assert origin['scientific_modules_under_gui_checkout'] is source_checkout
                (out/'execution-origin.json').write_text(json.dumps(origin,indent=2)+'\n')
                assert q==json.loads((checkout/'validation/runs/stage081/known-array-scale.json').read_text())
                assert len(q['snapshots'])==18 and len(q['conditional_scale_cases'])==108
                def number(v):return f'{float(v):.4e}'.replace('e-0','e-').replace('e+0','e+')
                def complex_value(v):return number(v[0])+(' + ' if v[1]>=0 else ' − ')+number(abs(v[1]))+' i'
                def rows(selector):return page.locator(selector).evaluate('(t)=>Array.from(t.querySelectorAll("tr")).slice(1).map(r=>Array.from(r.querySelectorAll("td")).map(c=>c.innerText))')
                layouts={'spread':'分散配置','line':'直線配置','ring':'円周配置'}
                population=rows('#array-scale-population');assert len(population)==18
                for c,cells in zip(q['snapshots'],population):
                    assert layouts[c['layout']] in cells[0] and f"最大{c['maximum_baseline_m']:g}m" in cells[0]
                    assert number(c['smallest_projected_fringe_period_arcsec']) in cells[0]
                    assert cells[1]==' / '.join(number(c[k]) for k in ('correlated_flux_fraction_minimum','correlated_flux_fraction_median','correlated_flux_fraction_maximum'))
                    p=c['population_signature']
                    for col,kind in ((2,'phase'),(3,'logamp')):assert cells[col]==' / '.join(number(p[kind+k]) for k in ('_rms_from_point','_maximum_abs_from_point'))
                assert len(rows('#array-scale-table'))==18
                for key in ('layout','maximum_baseline_m','window_seconds','assumed_receiver_background_sefd_jy'):page.locator(f'#array-scale-filters select[name={key}]').select_option('all')
                scale_rows=rows('#array-scale-table');assert len(scale_rows)==108
                for c,cells in zip(q['conditional_scale_cases'],scale_rows):
                    assert layouts[c['layout']] in cells[0] and f"最大{c['maximum_baseline_m']:g}m" in cells[0]
                    assert f"{c['window_seconds']:g}秒" in cells[0] and 'SEFD '+number(c['assumed_receiver_background_sefd_jy']) in cells[0]
                    assert 'M='+str(c['independent_samples_conditional_input']) in cells[0]
                    assert cells[1]==' / '.join(number(c[k]) for k in ('complex_rms_scale_minimum','complex_rms_scale_median','complex_rms_scale_maximum'))
                page.locator('#array-scale-details summary').click();checked=0
                for i,c in enumerate(q['conditional_scale_cases']):
                    page.locator('#array-scale-detail-case').select_option(str(i));detail=rows('#array-scale-triangle-table');assert len(detail)==56
                    for j,(triangle,cells) in enumerate(zip(c['triangles'],detail)):
                        assert '-'.join(str(v) for v in triangle) in cells[0] and complex_value(c['known_mean_real_imag'][j]) in cells[0]
                        assert cells[1]==number(c['known_complex_variance'][j]) and cells[2]==number(c['known_complex_rms_scale'][j]);checked+=1
                assert checked==6048;page.locator('#array-scale-details summary').click()
                selected={'layout':'spread','maximum_baseline_m':'100','window_seconds':'0.3','assumed_receiver_background_sefd_jy':'10000'}
                for key,value in selected.items():page.locator(f'#array-scale-filters select[name={key}]').select_option(value)
                assert len(rows('#array-scale-table'))==1 and '最大100m' in rows('#array-scale-table')[0][0]
                for key in ('layout','maximum_baseline_m'):page.locator(f'#array-scale-filters select[name={key}]').select_option('all')
                assert len(rows('#array-scale-table'))==18
                text=page.locator('#job-detail').inner_text()
                for phrase in ('最大基線と既知Cas A形状の比較','独立画像情報量ではありません','fringe周期は復元画像のbeam幅ではありません','形状の差を検出する尺度ではありません','数値上の無効行'):assert phrase in text
                page.locator('#array-scale-reference summary').click();text=page.locator('#job-detail').inner_text()
                assert q['reference']['derived_sha256'] in text and q['assumed_start_utc'] in text
                assert '2は予測' in text and '現行RMLの重みは変更していません' in text
                page.locator('#array-scale-reference summary').click()
                page.wait_for_function('() => Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                caption=page.locator('#job-detail figcaption').inner_text();assert '母集団形状差' in caption and '画像成功' in caption
                artifact=next(a for a in job['artifacts'] if a['path']=='validation/summary.json')
                page.get_by_text('条件・画像・相関ファイルを保存',exact=True).click()
                with page.expect_download() as info:page.locator('#job-detail .download-list a').filter(has_text=artifact['path']).click()
                assert json.loads(Path(info.value.path()).read_text())==q
                page.screenshot(path=str(out/'result.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844});overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                page.screenshot(path=str(out/'mobile.png'),full_page=True)
                font=page.evaluate('document.fonts.check("14px VSoRA Japanese")');external=[u for u in requests if not u.startswith(url+'/')]
                assert not errors and not external and not overflow and font
                summary={'state':'complete','source_checkout':source_checkout,'installed_imports':not source_checkout,'outside_checkout_workspace':True,'pythonpath_removed':True,'workflow_owned_by_checkout':False,'native_scientific_worker':True,'workspace_has_checkout_runner':False,'scientific_modules_under_runtime_prefix':not source_checkout,'packaged_configuration_and_sky_used':not source_checkout,
                    'real_worker_workflow_executed':True,'population_rows_checked':18,'scale_conditions_checked':108,'triangle_rows_checked':checked,'all_display_numbers_checked':True,'filters_checked':True,
                    'entire_scientific_result_identical_to_stage081':True,'json_download_identical':True,'caption_checked':True,'population_and_complex_rms_limits_visible':True,
                    'japanese_font_loaded':font,'mobile_horizontal_overflow':overflow,'javascript_errors':len(errors),'external_requests':len(external),
                    'actual_hardware_data':False,'optimal_array_selected':False,'image_reconstructed':False,'production_rml_noise_model_changed':False,
                    'browser_environment':'WSL headless Chromium; Windows/WSLg unverified'}
                browser.close();(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
                (out/'scientific-summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');return summary
        finally:
            server.terminate()
            try:server.wait(timeout=8)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=2)
            log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--port',type=int,default=8791)
    p.add_argument('--source-checkout',action='store_true');print(json.dumps(run(**vars(p.parse_args())),indent=2))
