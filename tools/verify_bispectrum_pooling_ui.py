"""Actual independent-group pooling workflow through Japanese UI, with explicit import origin."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,tempfile,time
import httpx
from playwright.sync_api import sync_playwright


def run(output,port=8786,source_checkout=False):
    from vsora_ui import models,worker
    checkout=Path(__file__).resolve().parents[1]
    module_root=checkout if source_checkout else Path(sys.prefix)
    assert all(Path(m.__file__).is_relative_to(module_root) for m in (models,worker))
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    url=f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory(prefix='vsora-pooling-ui-') as folder:
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
                page.locator('#validation-form select[name=validation]').select_option('bispectrum_pooling')
                page.screenshot(path=str(out/'input.png'),full_page=True)
                page.get_by_role('button',name='検証を開始',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=150000)
                job_id=httpx.get(url+'/api/jobs').json()[0]['id'];job=httpx.get(url+'/api/jobs/'+job_id).json();q=job['summary']
                assert job['state']=='complete' and q['type']=='independent_group_bispectrum_pooling_validation'
                assert len(q['cases'])==15 and q['trials_per_model']==8192
                for key in ('actual_frequency_independence_verified','observed_frequency_coaddition_performed','frequency_phase_alignment_performed','physical_adc_vdif_processed','real_hardware_validation_performed','gaussian_u3_distribution_verified','production_rml_noise_model_changed'):assert q[key] is False
                text=page.locator('#job-detail').inner_text()
                for phrase in ('周波数群の三次統計・標本のまとめ方','実FFTの周波数間独立性を測定した結果ではありません','検出確率・画像SNR・実観測時間ではありません','異なるSの群をまとめた雑音共分散は計算していません','実観測のU₃の雑音σではありません'):assert phrase in text
                def number(value):return f'{float(value):.4e}'.replace('e-0','e-').replace('e+0','e+')
                def complex_value(values):return number(values[0])+(' + ' if values[1]>=0 else ' − ')+number(abs(values[1]))+' i'
                def variance(d,i,n):return d['known_real_covariance'][i][i]+d['known_real_covariance'][i+n][i+n]
                names={'average':'群別U₃の平均','pooled':'全標本をまとめたU₃'}
                labels={'zero':'天体なし','weak':'とても弱い共有点源','low':'より強い共有点源','two_components':'位相の異なる二成分','rank_one':'完全共有電圧（受信機雑音なし）'}
                table=page.locator('#bispectrum-pooling-table');assert table.locator('tr').count()==16
                for i,c in enumerate(q['cases']):
                    cells=table.locator('tr').nth(i+1).locator('td');assert cells.count()==4
                    assert labels[c['model']] in cells.nth(0).inner_text()
                    assert f"G={c['independent_groups']} / 各群M={c['samples_per_group']} / 全体N={c['pooled_samples']}" in cells.nth(0).inner_text()
                    for j,t in enumerate(c['triangles']):
                        assert '-'.join(str(v) for v in t)+': '+number(c['average_to_pooled_complex_variance_ratio'][j]) in cells.nth(1).inner_text()
                    for name in names:
                        assert names[name]+': '+number(variance(c['methods'][name],0,len(c['triangles']))) in cells.nth(2).inner_text()
                    assert c['all_calculated_moments_within_6se'] and '平均・実共分散が固定基準内' in cells.nth(3).inner_text()
                page.locator('#bispectrum-pooling-all-details summary').click();rows=page.locator('#bispectrum-pooling-all-table tr');assert rows.count()==121
                row_index=1
                for c in q['cases']:
                    n=len(c['triangles'])
                    for i,t in enumerate(c['triangles']):
                        for name in names:
                            d=c['methods'][name];cells=rows.nth(row_index).locator('td')
                            assert '-'.join(str(v) for v in t) in cells.nth(0).inner_text() and names[name] in cells.nth(0).inner_text()
                            assert complex_value(d['known_mean_real_imag'][i]) in cells.nth(1).inner_text()
                            assert complex_value(d['ensemble_mean_real_imag'][i]) in cells.nth(1).inner_text()
                            assert ' / '.join(number(d['mean_mc_standard_error_all_real_then_imag'][j]) for j in (i,i+n)) in cells.nth(2).inner_text()
                            assert number(variance(d,i,n)) in cells.nth(3).inner_text();row_index+=1
                page.locator('#bispectrum-pooling-all-details summary').click()
                phase=q['frequency_dependent_phase_example'];rows=page.locator('#bispectrum-pooling-phase-table tr');assert rows.count()==9
                assert phase['fixed_per_group_phase_invariance_checked'] and phase['all_calculated_moments_within_6se']
                assert not phase['heterogeneous_group_covariance_calculated']
                assert number(phase['maximum_per_group_u3_gain_invariance_difference']) in text
                n=len(phase['triangles']);row_index=1
                for i,t in enumerate(phase['triangles']):
                    for name in names:
                        d=phase['methods'][name];cells=rows.nth(row_index).locator('td')
                        assert '-'.join(str(v) for v in t) in cells.nth(0).inner_text() and names[name] in cells.nth(0).inner_text()
                        assert complex_value(d['known_mean_real_imag'][i]) in cells.nth(1).inner_text()
                        assert complex_value(d['ensemble_mean_real_imag'][i]) in cells.nth(2).inner_text()
                        assert ' / '.join(number(d['mean_mc_standard_error_all_real_then_imag'][j]) for j in (i,i+n)) in cells.nth(3).inner_text();row_index+=1
                page.wait_for_function('() => Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                caption=page.locator('#job-detail figcaption').inner_text();assert '分散比' in caption and '母平均' in caption and '実FFT・帯域補正' in caption
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
                    'real_worker_workflow_executed':True,'conditions':15,'trials_per_model':8192,'all_triangle_method_rows_checked':128,'all_display_numbers_checked':True,
                    'json_download_identical':True,'conditional_covariances_for_identical_groups_only':True,'frequency_dependent_phase_example_checked':True,'caption_checked':True,
                    'japanese_font_loaded':font,'mobile_horizontal_overflow':overflow,'javascript_errors':len(errors),'external_requests':len(external),
                    'heterogeneous_group_covariance_calculated':False,'observed_frequency_coaddition_performed':False,'actual_hardware_data':False,'production_rml_noise_model_changed':False,
                    'browser_environment':'WSL headless Chromium; Windows/WSLg unverified',
                    'scope':'Known independent Gaussian groups: constant S covariance comparison and varying station-phase means. No actual FFT, observed band alignment, detection probability or image confidence.'}
                browser.close();(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
                (out/'scientific-summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');return summary
        finally:
            server.terminate()
            try:server.wait(timeout=8)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=2)
            log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--port',type=int,default=8786)
    p.add_argument('--source-checkout',action='store_true');print(json.dumps(run(**vars(p.parse_args())),indent=2))
