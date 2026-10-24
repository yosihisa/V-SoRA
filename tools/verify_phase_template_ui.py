"""Native phase-template study through an installed or source GUI."""
import argparse,json,os,subprocess,sys,tempfile,time
from pathlib import Path
import httpx


def run(reference,output,source_checkout=False,port=8796):
    from playwright.sync_api import sync_playwright
    from vsora_ui import models,worker
    from vsora_simulator import gaussian_phase_template
    root=Path(__file__).resolve().parents[1];prefix=root if source_checkout else Path(sys.prefix)
    assert all(Path(m.__file__).is_relative_to(prefix) for m in (models,worker,gaussian_phase_template))
    if source_checkout:
        assert Path(models.__file__).is_relative_to(root/'apps/ui/src')
        assert Path(gaussian_phase_template.__file__).is_relative_to(root/'apps/simulator/src')
    sys.path.insert(0,str(root))
    expected=json.loads(Path(reference).read_text());out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    if source_checkout:env['PYTHONPATH']=os.pathsep.join(map(str,[root,*sorted(root.glob('apps/*/src')),*sorted(root.glob('packages/*/src'))]))
    url=f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory(prefix='vsora-phase-template-ui-') as folder:
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
                assert cap['available_validations']==['array_scale','casa_window_symmetry','known_template','independent_training','gaussian_template','phase_template']
                assert not cap['checkout_validation_available']
                page.wait_for_function('()=>!document.querySelector("#validation-form option[value=phase_template]").disabled')
                assert page.locator('#validation-form option:enabled').count()==len(cap['available_validations'])
                page.locator('#validation-form select').select_option('phase_template')
                page.screenshot(path=str(out/'input.png'),full_page=True)
                with page.expect_response(lambda r:r.url==url+'/api/jobs' and r.request.method=='POST') as created:
                    page.locator('#validation-form button[type=submit]').click()
                id=created.value.json()['id']
                page.wait_for_function('(id)=>document.querySelector("#job-detail .run-id")?.textContent===id',arg=id)
                page.wait_for_function('()=>["処理完了","処理に失敗しました","中止しました"].some(s=>document.querySelector("#job-detail .phase-line")?.textContent.includes(s))||document.querySelector("#phase-template-summary-table")!==null',timeout=1800000)
                job=httpx.get(url+'/api/jobs/'+id).json();assert job['state']=='complete' and job['summary']==expected
                page.locator('#phase-template-summary-table').wait_for()
                assert httpx.get(url+f'/api/jobs/{id}/artifacts/validation/summary.json').json()==expected
                for c in expected['cases']:
                    assert httpx.get(url+f"/api/jobs/{id}/artifacts/validation/cases/{c['case_id']}.json").json()==c
                origin=httpx.get(url+f'/api/jobs/{id}/artifacts/validation/execution-origin.json').json()
                assert origin['native_scientific_module_used'] and not origin['checkout_runner_used'] and origin['formal_profile_executed']
                assert origin['scientific_module_count']==12 and origin['configuration_asset_sha256']==expected['configuration_asset_sha256']
                if source_checkout:assert origin['scientific_modules_under_gui_checkout']
                else:assert origin['scientific_modules_under_runtime_prefix'] and origin['configuration_asset_under_runtime_prefix'] and origin['sky_asset_under_runtime_prefix']
                # Summary can exist while the last running-state view is still displayed.
                # Wait for the final DOM state before opening details/selecting a case.
                page.wait_for_function('()=>document.querySelector("#job-detail .phase-line")?.textContent.includes("処理完了")&&!document.querySelector("#job-detail .spinner")')
                checked=check_tables(page,expected)
                text=page.locator('#job-detail').inner_text()
                for phrase in ('真の局位相を与え','両方とも振幅・SEFD','実OCXOの変動','大域解は保証しません','画像の信頼区間ではありません','未収束を0点や除外へ置き換えません','現在のClosure＋RMLへの適用はありません','零天空の対照'):
                    assert phrase in text
                fixture=__import__('copy').deepcopy(expected);c=fixture['cases'][0];row=c['point_generation']['rows'][0]
                row.update(phase_profile_score=None,profile_prediction_casa=None,profile_state='not_converged',fit_states=None,fit_gradient_normalized=None)
                c['metrics']['phase_profile'].update(state='unresolved_windows',balanced_accuracy=None,empirical_auroc=None,false_casa_on_point=None,missed_casa=None)
                c['unresolved_profile_windows']=1
                page.evaluate('(s)=>{const b=node("div");b.id="explicit-null-fixture";document.body.append(b);renderPhaseTemplate(b,s)}',fixture)
                f=page.locator('#explicit-null-fixture');assert '正答率：未解決' in f.inner_text() and '未解決のため未算出' in f.inner_text()
                f.locator('#phase-template-case').evaluate("e=>e.closest('details').open=true")
                first=f.locator('#phase-template-detail-table tr').nth(1).locator('td').all_inner_texts()
                assert first[3]=='未解決' and first[5]=='未解決' and first[6]=='未収束' and first[7].endswith('探索：未解決')
                f.evaluate('e=>e.remove()')
                page.locator("#job-detail .download-list").evaluate("e=>e.closest('details').open=true")
                with page.expect_download() as downloaded:
                    page.locator('#job-detail .download-list a').filter(has_text='validation/summary.json').click()
                assert json.loads(Path(downloaded.value.path()).read_text())==expected
                page.locator('#phase-template-case').select_option('p05')
                for _ in range(2):
                    with page.expect_response(lambda r:r.url==url+'/api/jobs/'+id and r.request.method=='GET'):
                        page.wait_for_timeout(2500)
                    page.wait_for_function('()=>!refreshing')
                    assert page.locator('#phase-template-case').input_value()=='p05'
                    assert page.locator('#phase-template-case').evaluate("e=>e.closest('details').open")

                page.screenshot(path=str(out/'result.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                scrolls=[]
                for element in page.locator('.phase-template-scroll').all():
                    scrolls.append(element.evaluate('(e)=>{e.scrollLeft=e.scrollWidth-e.clientWidth;return e.scrollLeft>0}'))
                assert scrolls==[True,True]
                page.screenshot(path=str(out/'mobile-values.png'),full_page=True)
                for element in page.locator('.phase-template-scroll').all():element.evaluate('(e)=>e.scrollLeft=0')
                page.screenshot(path=str(out/'mobile-result.png'),full_page=True)
                overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                font=page.evaluate('document.fonts.check("14px \'VSoRA Japanese\'")')
                external=[r for r in requests if not r.startswith(url+'/')]
                assert not errors and not external and not overflow and font
                result={'state':'complete','source_checkout':source_checkout,**checked,
                    'full_scientific_json_identical_to_stage104':True,'all_seven_case_json_files_identical':True,'summary_download_identical':True,
                    'completed_view_survived_two_poll_responses':True,'native_origin':origin,'scientific_module_count':12,'workspace_has_checkout_runner':False,'outside_checkout_workspace':True,
                    'japanese_qualification_labels_checked':True,'explicit_unresolved_renderer_fixture_checked':True,'japanese_font_loaded':font,
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
    rows=page.locator('#phase-template-summary-table tr').all();assert len(rows)==8
    for row,c in zip(rows[1:],expected['cases'],strict=True):
        cells=row.locator('td').all();assert len(cells)==6
        assert c['case_id'] in cells[0].inner_text() and 'M：'+format(c['modes'],',') in cells[0].inner_text()
        assert 'SEFD（Jy）：'+number(c['sefd_jy']) in cells[0].inner_text()
        for cell,key in zip(cells[1:3],('oracle','phase_profile'),strict=True):
            m=c['metrics'][key]
            assert '正答率：'+number(m['balanced_accuracy']) in cell.inner_text()
            assert 'AUROC：'+number(m['empirical_auroc']) in cell.inner_text()
        for cell,role in zip(cells[3:5],('false_casa_on_point','missed_casa'),strict=True):
            for label,key in (('真値あり','oracle'),('探索','phase_profile')):
                rate=c['metrics'][key][role];text=cell.inner_text()
                assert label+' 件数：'+str(rate['errors'])+' / '+str(rate['trials']) in text
                assert label+' 誤り率：'+number(rate['fraction']) in text
                assert label+' 個別95%区間：'+number(rate['clopper_pearson_interval'][0])+'〜'+number(rate['clopper_pearson_interval'][1]) in text
        text=cells[5].inner_text();assert '未解決：'+str(c['unresolved_profile_windows'])+' / '+str(2*c['test_per_label']) in text
        for label,key in (('点源群','point_generation'),('Cas A群','casa_generation')):
            m=c[key]['oracle_by_profile_prediction_counts_on_resolved_only']
            assert label+'：'+' / '.join(map(str,m[0]))+' ; '+' / '.join(map(str,m[1])) in text
    select=page.locator('#phase-template-case');select.evaluate("e=>e.closest('details').open=true")
    assert select.locator('option').count()==7
    total=0
    for c in expected['cases']:
        select.select_option(c['case_id'])
        rows=page.locator('#phase-template-detail-table tr').evaluate_all('(rows)=>rows.slice(1).map(r=>Array.from(r.cells).map(c=>c.innerText))')
        assert len(rows)==128
        expected_rows=[]
        for label,key,is_casa in (('点源群','point_generation',False),('Cas A群','casa_generation',True)):
            for r in c[key]['rows']:
                op=r['oracle_prediction_casa'];pp=r['profile_prediction_casa']
                state='位相依存なし' if all(v=='phase_independent' for v in r['fit_states']) else '局所停留候補'
                expected_rows.append([label,str(r['window_index']),number(r['oracle_score']),number(r['phase_profile_score']),'Cas A' if op else '点源','Cas A' if pp else '点源',state,'真値あり：'+('正答' if op==is_casa else '誤判定')+' / 探索：'+('正答' if pp==is_casa else '誤判定')])
        assert rows==expected_rows,c['case_id'];total+=len(rows)
    vertical=page.locator('.phase-template-detail').evaluate('(e)=>{e.scrollTop=e.scrollHeight-e.clientHeight;let moved=e.scrollTop>0;e.scrollTop=0;return moved}');assert vertical
    return {'summary_rows':7,'detail_rows':total,'case_filters':7,'all_display_numbers_checked':True,'all_paired_scores_predictions_labels_and_states_checked':True,'actual_detail_vertical_scroll_performed':vertical}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('reference','output'):p.add_argument('--'+name,required=True)
    p.add_argument('--source-checkout',action='store_true');p.add_argument('--port',type=int,default=8841)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
