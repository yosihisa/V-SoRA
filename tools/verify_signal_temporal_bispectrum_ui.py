"""Actual signal/common-time mean workflow through Japanese UI, with explicit import origin."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,tempfile,time
import httpx
from playwright.sync_api import sync_playwright


def run(output,port=8785,source_checkout=False):
    from vsora_ui import models,worker
    checkout=Path(__file__).resolve().parents[1]
    module_root=checkout if source_checkout else Path(sys.prefix)
    assert all(Path(m.__file__).is_relative_to(module_root) for m in (models,worker))
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    url=f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory(prefix='vsora-signal-time-ui-') as folder:
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
                page.locator('#validation-form select[name=validation]').select_option('signal_temporal_bispectrum')
                page.screenshot(path=str(out/'input.png'),full_page=True)
                page.get_by_role('button',name='検証を開始',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=150000)
                job_id=httpx.get(url+'/api/jobs').json()[0]['id'];job=httpx.get(url+'/api/jobs/'+job_id).json();q=job['summary']
                assert job['state']=='complete' and q['type']=='signal_temporal_bispectrum_validation'
                assert len(q['cases'])==25 and q['trials_per_condition']==8192
                for key in ('observed_bias_correction_performed','variance_or_likelihood_calculated','station_specific_kernels_modelled','physical_raw_filter_convolution_performed','physical_adc_vdif_processed','actual_temporal_independence_verified','real_hardware_validation_performed','production_rml_noise_model_changed'):assert q[key] is False
                text=page.locator('#job-detail').inner_text()
                for phrase in ('天体信号と共通時間相関・三次統計の平均','KからGaussian係数を直接生成','局ごとに異なる時計や補間','観測値の偏り補正は行っていません','角度の期待値や画像品質を確認した意味ではありません','実受信機の推奨間隔を測った結果ではありません'):assert phrase in text
                def number(value):return f'{float(value):.4e}'.replace('e-0','e-').replace('e+0','e+')
                def complex_value(values):return number(values[0])+(' + ' if values[1]>=0 else ' − ')+number(abs(values[1]))+' i'
                table=page.locator('#signal-temporal-bispectrum-table');assert table.locator('tr').count()==26
                for i,c in enumerate(q['cases']):
                    cells=table.locator('tr').nth(i+1).locator('td');assert cells.count()==4
                    assert f"M={c['retained_outputs']} / 公称 {c['nominal_time_outputs']} / {c['guard_step_outputs']}出力おき" in cells.nth(0).inner_text()
                    assert complex_value(c['true_marginal_bispectrum_real_imag'][0]) in cells.nth(1).inner_text()
                    d=c['methods']['distinct'];values=cells.nth(2).inner_text()
                    assert complex_value(d['known_mean_real_imag'][0]) in values and complex_value(d['ensemble_mean_real_imag'][0]) in values
                    assert ' / '.join(number(v) for v in d['mc_mean_standard_error'][0]) in values
                    assert f"{d['maximum_absolute_normalized_mean_difference']:.4f}" in cells.nth(3).inner_text()
                    assert c['all_mean_components_within_6se']
                page.locator('#signal-temporal-all-details summary').click();all_rows=page.locator('#signal-temporal-all-table tr');assert all_rows.count()==201
                row_index=1
                for c in q['cases']:
                    for triangle in range(len(c['triangles'])):
                        for method in ('ordinary','distinct'):
                            cells=all_rows.nth(row_index).locator('td');d=c['methods'][method]
                            assert '-'.join(str(v) for v in c['triangles'][triangle]) in cells.nth(0).inner_text()
                            assert complex_value(d['known_mean_real_imag'][triangle]) in cells.nth(1).inner_text()
                            assert complex_value(d['ensemble_mean_real_imag'][triangle]) in cells.nth(2).inner_text()
                            assert ' / '.join(number(v) for v in d['mc_mean_standard_error'][triangle]) in cells.nth(3).inner_text()
                            row_index+=1
                page.locator('#signal-temporal-all-details summary').click()
                page.wait_for_function('() => Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                caption=page.locator('#job-detail figcaption').inner_text();assert '共通時間相関' in caption and '平均' in caption and '実ADC・FIR・VDIF' in caption
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
                    'real_worker_workflow_executed':True,'conditions':25,'trials_per_condition':8192,'all_triangle_method_rows_checked':200,'all_display_numbers_checked':True,
                    'json_download_identical':True,'conditional_means_only':True,'caption_checked':True,
                    'japanese_font_loaded':font,'mobile_horizontal_overflow':overflow,'javascript_errors':len(errors),'external_requests':len(external),
                    'variance_or_likelihood_calculated':False,'actual_hardware_data':False,'production_rml_noise_model_changed':False,
                    'browser_environment':'WSL headless Chromium; Windows/WSLg unverified',
                    'scope':'Known supplied S times common K Gaussian means only; no physical FIR/ADC, observed correction, likelihood or image confidence.'}
                browser.close();(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
                (out/'scientific-summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');return summary
        finally:
            server.terminate()
            try:server.wait(timeout=8)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=2)
            log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--port',type=int,default=8785)
    p.add_argument('--source-checkout',action='store_true');print(json.dumps(run(**vars(p.parse_args())),indent=2))
