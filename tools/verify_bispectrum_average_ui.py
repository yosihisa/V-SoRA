"""Actual averaging workflow through Japanese UI, with explicit import origin."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,tempfile,time
import httpx
from playwright.sync_api import sync_playwright


def run(output,port=8783,source_checkout=False):
    from vsora_ui import models,worker
    checkout=Path(__file__).resolve().parents[1]
    module_root=checkout if source_checkout else Path(sys.prefix)
    assert all(Path(m.__file__).is_relative_to(module_root) for m in (models,worker))
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    url=f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory(prefix='vsora-average-ui-') as folder:
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
                page.locator('#validation-form select[name=validation]').select_option('bispectrum_average')
                page.screenshot(path=str(out/'input.png'),full_page=True)
                page.get_by_role('button',name='検証を開始',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=150000)
                job_id=httpx.get(url+'/api/jobs').json()[0]['id'];job=httpx.get(url+'/api/jobs/'+job_id).json();q=job['summary']
                assert job['state']=='complete' and q['type']=='averaged_bispectrum_distribution_validation'
                assert q['trials_per_model']==8192 and len(q['cases'])==20
                assert q['gaussian_u3_coverage_is_not_a_pass_requirement'] and q['q_comparisons_statistically_paired']
                for name in ('gaussian_u3_distribution_verified','physical_adc_vdif_processed','actual_temporal_independence_verified','real_hardware_validation_performed','production_rml_noise_model_changed'):assert q[name] is False
                text=page.locator('#job-detail').inner_text()
                for phrase in ('短積分平均と三次統計の誤差分布','64回平均すればGaussian尤度を使えるという判定ではありません','局電圧共分散Sは真値','Q同士の結果は独立ではありません','実機の信頼区間ではありません','Gaussian性を示しません','Qを観測秒数へ換算せず'):assert phrase in text
                table=page.locator('#bispectrum-average-table');assert table.locator('tr').count()==21
                for i,c in enumerate(q['cases']):
                    row=table.locator('tr').nth(i+1);cells=row.locator('td');assert cells.count()==4
                    assert f"M={c['samples_per_window']} / Q={c['independent_windows']} / 次元={c['real_parameter_rank']}" in cells.nth(0).inner_text()
                    assert c['means_and_covariances_within_6se'] and c['all_residuals_within_covariance_support']
                    for j,r in enumerate(c['coverage_references']):
                        cell=cells.nth(j+1).inner_text()
                        assert f"{100*r['u3_coverage_fraction']:.3f}%" in cell
                        assert f"反復標準誤差 {100*r['u3_binomial_mc_standard_error']:.3f}ポイント" in cell
                        assert f"Gaussian対照 {100*r['gaussian_control_coverage_fraction']:.3f}%" in cell
                    assert f"{c['mean_mahalanobis_per_rank']:.6f}" in cells.nth(3).inner_text()
                assert any(not r['u3_within_6_reference_se'] for c in q['cases'] for r in c['coverage_references'])
                assert '失敗' not in page.locator('#job-detail .phase-line').inner_text()
                page.wait_for_function('() => Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                caption=page.locator('#job-detail figcaption').inner_text();assert '独立短積分' in caption and '画像の信頼区間ではありません' in caption
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
                    'real_worker_workflow_executed':True,'conditions':20,'trials_per_model':8192,'all_display_numbers_checked':True,
                    'json_download_identical':True,'non_gaussian_coverage_does_not_fail_job':True,'caption_checked':True,
                    'japanese_font_loaded':font,'mobile_horizontal_overflow':overflow,'javascript_errors':len(errors),'external_requests':len(external),
                    'gaussian_u3_distribution_verified':False,'actual_hardware_data':False,'production_rml_noise_model_changed':False,
                    'browser_environment':'WSL headless Chromium; Windows/WSLg unverified',
                    'scope':'Known iid Gaussian voltages and independent equal-statistics windows, no hardware or image confidence.'}
                browser.close();(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
                (out/'scientific-summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');return summary
        finally:
            server.terminate()
            try:server.wait(timeout=8)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=2)
            log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--port',type=int,default=8783)
    p.add_argument('--source-checkout',action='store_true');print(json.dumps(run(**vars(p.parse_args())),indent=2))
