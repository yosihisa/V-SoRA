"""Actual Japanese known-sky comparison, filters, all triangle values and downloads."""
import argparse,json,os
from decimal import Decimal,localcontext,ROUND_HALF_UP
from pathlib import Path
import subprocess,sys,tempfile,time
import httpx
import numpy as np
from playwright.sync_api import sync_playwright


def run(output,port=8787,source_checkout=False):
    from vsora_ui import models,worker
    checkout=Path(__file__).resolve().parents[1]
    module_root=checkout if source_checkout else Path(sys.prefix)
    assert all(Path(m.__file__).is_relative_to(module_root) for m in (models,worker))
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    url=f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory(prefix='vsora-known-sky-ui-') as folder:
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
                page.locator('#validation-form select[name=validation]').select_option('known_sky_bispectrum')
                page.screenshot(path=str(out/'input.png'),full_page=True)
                page.get_by_role('button',name='検証を開始',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=150000)
                job_id=httpx.get(url+'/api/jobs').json()[0]['id'];job=httpx.get(url+'/api/jobs/'+job_id).json();q=job['summary']
                assert job['state']=='complete' and q['type']=='known_sky_bispectrum_scale_validation'
                assert q==json.loads((checkout/'validation/runs/stage076/known-sky-scale.json').read_text())
                assert len(q['conditional_forecasts'])==144 and q['trials_per_mc_case']==8192
                text=page.locator('#job-detail').inner_text()
                for phrase in ('天体形状と三次統計の条件比較','SEFDとfluxは測定値ではありません','検出確率や画像SNRではありません','実FFTの独立性や短積分中のOCXO','表示条件：3 / 144'):assert phrase in text
                def number(v):return f'{float(v):.4e}'.replace('e-0','e-').replace('e+0','e+')
                def count_number(v):
                    with localcontext() as context:
                        context.rounding=ROUND_HALF_UP
                        return format(Decimal.from_float(float(v)),".4E").lower()
                def complex_value(v):return number(v[0])+(' + ' if v[1]>=0 else ' − ')+number(abs(v[1]))+' i'
                def value_range(a):return ' / '.join(number(v) for v in (min(a),np.median(a),max(a)))
                def table_rows(selector):return page.locator(selector).evaluate('(t)=>Array.from(t.querySelectorAll("tr")).slice(1).map(r=>Array.from(r.querySelectorAll("td")).map(c=>c.innerText))')
                assert page.locator('#known-sky-table tr').count()==4
                for key in ('shape_model','stations','layout','window_seconds','assumed_receiver_background_sefd_jy'):
                    page.locator('#known-sky-filter-'+key).select_option('all')
                rows=table_rows('#known-sky-table');assert len(rows)==144
                shapes={'point':'点源','casa':'Cas A形状'};layouts={'spread':'分散配置','line':'直線配置','ring':'円周配置'}
                detail_rows=0
                for i,(c,cells) in enumerate(zip(q['conditional_forecasts'],rows)):
                    assert shapes[c['shape_model']] in cells[0] and str(c['stations'])+'局' in cells[0] and layouts[c['layout']] in cells[0]
                    assert 'SEFD '+number(c['assumed_receiver_background_sefd_jy']) in cells[0]
                    assert 'M='+str(c['independent_samples_conditional_input']) in cells[0]
                    assert value_range(c['known_complex_rms_scale'])==cells[1]
                    assert value_range(c['complex_to_null_variance_ratio'])==cells[2]
                page.locator('#known-sky-details summary').click()
                for i,c in enumerate(q['conditional_forecasts']):
                    page.locator('#known-sky-detail-case').select_option(str(i))
                    rows=table_rows('#known-sky-triangle-table');assert len(rows)==len(c['triangles'])
                    for j,cells in enumerate(rows):
                        assert '-'.join(str(v) for v in c['triangles'][j]) in cells[0]
                        assert complex_value(c['known_mean_real_imag'][j]) in cells[0]
                        assert number(c['known_complex_variance'][j]) in cells[1] and number(c['known_complex_rms_scale'][j]) in cells[1]
                        state=c['conditional_window_count_state'][j]
                        expected=count_number(c['required_identical_independent_windows'][j]) if state=='finite' else '上限10¹⁸を超える：反復数なし'
                        assert cells[2]==expected,(i,j,state,cells[2],expected,c["required_identical_independent_windows"][j]);detail_rows+=1
                assert detail_rows==4320
                # Display-only fixture distinguishes a numeric zero from an unsupported count.
                page.evaluate('''q=>{const s=structuredClone(q);s.conditional_forecasts=[structuredClone(q.conditional_forecasts.find(c=>c.shape_model==="casa"&&c.stations===8&&c.layout==="spread"&&c.window_seconds===.3))];const c=s.conditional_forecasts[0];c.conditional_window_count_state[0]="zero_numeric_mean";c.required_identical_independent_windows[0]=null;c.conditional_window_count_state[1]="above_supported_count_limit";c.required_identical_independent_windows[1]=null;const b=document.createElement("div");b.id="known-sky-state-fixture";document.body.append(b);renderKnownSkyBispectrum(b,s);}''',q)
                page.locator('#known-sky-state-fixture #known-sky-details summary').click()
                fixture=page.locator('#known-sky-state-fixture #known-sky-triangle-table');assert '平均が数値0：反復数なし' in fixture.inner_text() and '上限10¹⁸を超える：反復数なし' in fixture.inner_text()
                page.locator('#known-sky-state-fixture').evaluate('(e)=>e.remove()')
                rows=table_rows('#known-sky-mc-table');assert len(rows)==3
                for c,cells in zip(q['monte_carlo_cases'],rows):
                    assert shapes[c['shape_model']] in cells[0] and str(c['stations'])+'局' in cells[0]
                    assert f"M={c['samples']} / {c['trials']:,}反復 / seed={c['seed']}"==cells[1]
                    assert c['all_means_and_covariances_within_6se'] and cells[2]=='固定6反復標準誤差基準内'
                page.locator('#known-sky-reference summary').click();text=page.locator('#known-sky-reference').inner_text()
                assert q['reference']['derived_sha256'] in text and q['reference']['observed_epoch'] in text
                assert '2はIERS予測値' in text and '実観測の雑音σではありません' in text
                page.locator('#known-sky-reference summary').click()
                for key,val in [('shape_model','point'),('stations','4'),('layout','ring'),('window_seconds','0.1'),('assumed_receiver_background_sefd_jy','10000')]:
                    page.locator('#known-sky-filter-'+key).select_option(val)
                assert page.locator('#known-sky-table tr').count()==2
                for key,val in [('shape_model','casa'),('stations','8'),('layout','spread'),('window_seconds','0.3'),('assumed_receiver_background_sefd_jy','all')]:
                    page.locator('#known-sky-filter-'+key).select_option(val)
                page.locator('#known-sky-details summary').click()
                page.wait_for_function('() => Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                caption=page.locator('#job-detail figcaption').inner_text();assert '複素rms尺度' in caption and '天体由来の分散' in caption and 'SEFDとfluxは仮定値' in caption
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
                    'real_worker_workflow_executed':True,'forecast_summary_rows_checked':144,'all_triangle_detail_rows_checked':detail_rows,'all_display_numbers_checked':True,
                    'default_three_rows_and_filter_changes_checked':True,'display_only_zero_and_unsupported_fixture_checked':True,'entire_scientific_result_identical_to_stage076':True,
                    'json_download_identical':True,'caption_checked':True,'reference_sha_epoch_and_predicted_eop_checked':True,
                    'japanese_font_loaded':font,'mobile_horizontal_overflow':overflow,'javascript_errors':len(errors),'external_requests':len(external),
                    'actual_hardware_data':False,'image_reconstructed':False,'production_rml_noise_model_changed':False,
                    'browser_environment':'WSL headless Chromium; Windows/WSLg unverified'}
                browser.close();(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
                (out/'scientific-summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');return summary
        finally:
            server.terminate()
            try:server.wait(timeout=8)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=2)
            log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--port',type=int,default=8787)
    p.add_argument('--source-checkout',action='store_true');print(json.dumps(run(**vars(p.parse_args())),indent=2))
