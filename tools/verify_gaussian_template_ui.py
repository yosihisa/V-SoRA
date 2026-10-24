"""Native gaussian-template study through an installed or source GUI."""
import argparse,json,os,subprocess,sys,tempfile,time
from pathlib import Path
import httpx


def run(reference,output,source_checkout=False,port=8795):
    from playwright.sync_api import sync_playwright
    from vsora_ui import models,worker
    from vsora_simulator import gaussian_template_validation
    root=Path(__file__).resolve().parents[1];prefix=root if source_checkout else Path(sys.prefix)
    assert all(Path(m.__file__).is_relative_to(prefix) for m in (models,worker,gaussian_template_validation))
    if source_checkout:
        assert Path(models.__file__).is_relative_to(root/'apps/ui/src')
        assert Path(gaussian_template_validation.__file__).is_relative_to(root/'apps/simulator/src')
    sys.path.insert(0,str(root))
    expected=json.loads(Path(reference).read_text());out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    if source_checkout:env['PYTHONPATH']=os.pathsep.join(map(str,[root,*sorted(root.glob('apps/*/src')),*sorted(root.glob('packages/*/src'))]))
    url=f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory(prefix='vsora-gaussian-template-ui-') as folder:
        workspace=Path(folder);assert not (workspace/'tools/run.py').exists()
        log=(out/'server.log').open('w')
        server=subprocess.Popen([str(Path(sys.prefix)/'bin/vsora-ui'),'--workspace',folder,'--port',str(port)],cwd=workspace,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            end=time.monotonic()+20
            while time.monotonic()<end:
                try:
                    if httpx.get(url+'/api/environment',timeout=1).status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.1)
            else:raise AssertionError('GUI not ready')
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1000},accept_downloads=True)
                errors=[];requests=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url))
                page.goto(url);page.get_by_role('button',name='動作検証',exact=True).click()
                cap=httpx.get(url+'/api/environment').json()
                assert cap['available_validations']==['array_scale','casa_window_symmetry','known_template','independent_training','gaussian_template']
                assert not cap['checkout_validation_available']
                page.wait_for_function('()=>!document.querySelector("#validation-form option[value=gaussian_template]").disabled')
                assert page.locator('#validation-form option:enabled').count()==len(cap['available_validations'])
                page.locator('#validation-form select').select_option('gaussian_template')
                page.screenshot(path=str(out/'input.png'),full_page=True)
                with page.expect_response(lambda r:r.url==url+'/api/jobs' and r.request.method=='POST') as created:
                    page.locator('#validation-form button[type=submit]').click()
                id=created.value.json()['id']
                page.wait_for_function('(id)=>document.querySelector("#job-detail .run-id")?.textContent===id',arg=id)
                page.wait_for_function('()=>["処理完了","処理に失敗しました","中止しました"].some(s=>document.querySelector("#job-detail .phase-line")?.textContent.includes(s))||document.querySelector("#gaussian-template-summary-table")!==null',timeout=1800000)
                job=httpx.get(url+'/api/jobs/'+id).json();assert job['state']=='complete' and job['summary']==expected
                page.locator('#gaussian-template-summary-table').wait_for()
                assert httpx.get(url+f'/api/jobs/{id}/artifacts/validation/summary.json').json()==expected
                for c in expected['cases']:
                    assert httpx.get(url+f"/api/jobs/{id}/artifacts/validation/cases/{c['case_id']}.json").json()==c
                origin=httpx.get(url+f'/api/jobs/{id}/artifacts/validation/execution-origin.json').json()
                assert origin['native_scientific_module_used'] and not origin['checkout_runner_used'] and origin['formal_profile_executed']
                assert origin['scientific_module_count']==10 and origin['configuration_asset_sha256']==expected['configuration_asset_sha256']
                if source_checkout:assert origin['scientific_modules_under_gui_checkout']
                else:assert origin['scientific_modules_under_runtime_prefix'] and origin['configuration_asset_under_runtime_prefix'] and origin['sky_asset_under_runtime_prefix']
                # Summary can exist while the last running-state view is still displayed.
                # Wait for the final DOM state before opening details/selecting a case.
                page.wait_for_function('()=>document.querySelector("#job-detail .phase-line")?.textContent.includes("処理完了")&&!document.querySelector("#job-detail .spinner")')
                checked=check_tables(page,expected)
                text=page.locator('#job-detail').inner_text()
                for phrase in ('未知gain・SEFD・LOを推定した結果ではありません','評価データで閾値やモデルを選び直していません','画像の信頼区間ではありません','将来のリスク0を保証しません','実測値ではありません','現在のRMLへの適用はありません','零天空の対照'):
                    assert phrase in text
                caption=page.locator('#job-detail figcaption').inner_text()
                assert '既知共分散の参照比較' in caption and '画像の信頼区間ではありません' in caption
                assert page.locator('#job-detail figure img').get_attribute('alt')==caption
                page.locator("#job-detail .download-list").evaluate("e=>e.closest('details').open=true")
                with page.expect_download() as downloaded:
                    page.locator('#job-detail .download-list a').filter(has_text='validation/summary.json').click()
                assert json.loads(Path(downloaded.value.path()).read_text())==expected
                page.locator('#gaussian-template-case').select_option('g06')
                for _ in range(2):
                    with page.expect_response(lambda r:r.url==url+'/api/jobs/'+id and r.request.method=='GET'):
                        page.wait_for_timeout(2500)
                    page.wait_for_function('()=>!refreshing')
                    assert page.locator('#gaussian-template-case').input_value()=='g06'
                    assert page.locator('#gaussian-template-case').evaluate("e=>e.closest('details').open")

                page.screenshot(path=str(out/'result.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                scrolls=[]
                for element in page.locator('.gaussian-template-scroll').all():
                    scrolls.append(element.evaluate('(e)=>{e.scrollLeft=e.scrollWidth-e.clientWidth;return e.scrollLeft>0}'))
                assert scrolls==[True,True]
                page.screenshot(path=str(out/'mobile-values.png'),full_page=True)
                for element in page.locator('.gaussian-template-scroll').all():element.evaluate('(e)=>e.scrollLeft=0')
                page.screenshot(path=str(out/'mobile-result.png'),full_page=True)
                overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                font=page.evaluate('document.fonts.check("14px \'VSoRA Japanese\'")')
                external=[r for r in requests if not r.startswith(url+'/')]
                assert not errors and not external and not overflow and font
                result={'state':'complete','source_checkout':source_checkout,**checked,
                    'full_scientific_json_identical_to_stage101':True,'all_nine_case_json_files_identical':True,'summary_download_identical':True,
                    'completed_view_survived_two_poll_responses':True,'native_origin':origin,'scientific_module_count':10,'workspace_has_checkout_runner':False,'outside_checkout_workspace':True,
                    'japanese_qualification_labels_checked':True,'caption_and_alt_checked':True,'japanese_font_loaded':font,
                    'mobile_root_horizontal_overflow':overflow,'actual_both_table_scrolls_performed':scrolls,
                    'javascript_errors':errors,'external_requests':len(external),'browser':browser.version,
                    'production_rml_noise_model_changed':False,'actual_hardware_data':False}
                (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');browser.close();return result
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()
            log.close()





def check_tables(page,expected):
    from tools.verify_bispectrum_power_ui import javascript_exponential as number
    rows=page.locator('#gaussian-template-summary-table tr').all();assert len(rows)==10
    for row,c in zip(rows[1:],expected['cases'],strict=True):
        cells=row.locator('td').all();assert len(cells)==5
        text=cells[0].inner_text()
        state='零天空・同一候補の対照' if c['zero_sky_control'] else '受信機モデル一致' if c['receiver_model_matches_generation'] else '受信機モデル誤指定'
        assert c['case_id'] in text and 'M：'+format(c['modes'],',') in text and state in text
        for label,key in (('仮定：','assumed_receiver_sefd_jy'),('点源生成：','point_generated_sefd_jy'),('Cas A生成：','casa_generated_sefd_jy')):
            assert label+number(c[key]) in cells[1].inner_text()
        for label,key in (('正答率：','balanced_accuracy'),('AUROC：','empirical_auroc')):
            assert label+number(c[key]) in cells[2].inner_text()
        for cell,key in zip(cells[3:],('false_casa_on_point','missed_casa'),strict=True):
            rate=c[key];text=cell.inner_text()
            assert '件数：'+str(rate['errors'])+' / '+str(rate['trials']) in text
            assert '誤り率：'+number(rate['fraction']) in text
            assert '個別95%区間：'+number(rate['clopper_pearson_interval'][0])+'〜'+number(rate['clopper_pearson_interval'][1]) in text
    select=page.locator('#gaussian-template-case')
    select.evaluate("e=>e.closest('details').open=true")
    assert page.locator('#gaussian-template-detail-table th').nth(2).inner_text()=='対数尤度比 log[L(Cas A)/L(点源)]'
    assert select.locator('option').count()==9
    total=0
    for c in expected['cases']:
        select.select_option(c['case_id'])
        rows=page.locator('#gaussian-template-detail-table tr').evaluate_all('(rows)=>rows.slice(1).map(r=>Array.from(r.cells).map(c=>c.innerText))')
        assert len(rows)==1024
        expected_rows=[]
        for label,key,is_casa in (('点源群','point_test_log_likelihood_ratios',False),('Cas A群','casa_test_log_likelihood_ratios',True)):
            for index,score in enumerate(c[key]):
                predicted=score>0
                expected_rows.append([label,str(index),number(score),'Cas A' if predicted else '点源','正答' if predicted==is_casa else '誤判定'])
        assert rows==expected_rows,c['case_id'];total+=len(rows)
    vertical=page.locator('.gaussian-template-detail').evaluate('(e)=>{e.scrollTop=e.scrollHeight-e.clientHeight;let moved=e.scrollTop>0;e.scrollTop=0;return moved}')
    assert vertical
    return {'summary_rows':9,'detail_rows':total,'case_filters':9,'all_display_numbers_checked':True,
            'all_window_labels_predictions_and_errors_checked':True,'actual_detail_vertical_scroll_performed':vertical}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('reference','output'):p.add_argument('--'+name,required=True)
    p.add_argument('--source-checkout',action='store_true');p.add_argument('--port',type=int,default=8840)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
