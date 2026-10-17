"""Actual browser transport for the stored conditional whole-window test."""
import argparse,importlib.util,json,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
import httpx

def run(fixtures,reference,output,source_checkout=False,port=8793):
    from playwright.sync_api import sync_playwright
    from vsora_ui import models,worker,raw_bispectrum
    from vsora_correlator import bispectrum_window_symmetry
    from vsora_imaging import window_symmetry
    from vsora_formats import bispectrum
    checkout=Path(__file__).resolve().parents[1]
    runtime=checkout if source_checkout else Path(sys.prefix)
    assert all(Path(m.__file__).is_relative_to(runtime) for m in
               (models,worker,raw_bispectrum,bispectrum_window_symmetry,window_symmetry,bispectrum))
    sys.path.insert(0,str(checkout/'tools'))
    from verify_bispectrum_power_ui import javascript_exponential as number
    spec=importlib.util.spec_from_file_location('window_fixture',checkout/'workflows/bispectrum_window_validation.py')
    helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
    expected=json.loads(Path(reference).read_text());inputs=Path(fixtures).resolve()
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    if source_checkout:
        env['PYTHONPATH']=os.pathsep.join(map(str,[checkout,*sorted(checkout.glob('apps/*/src')),*sorted(checkout.glob('packages/*/src'))]))
    url=f'http://127.0.0.1:{port}';cases=[]
    with tempfile.TemporaryDirectory(prefix='vsora-stored-window-ui-') as folder:
        workspace=Path(folder)
        for case in expected['cases']:
            name=case['case_id'];(workspace/name).mkdir()
            for file in ('raw.npz','visibility.npz'):shutil.copyfile(inputs/name/file,workspace/name/file)
        helpers.fixture(workspace/'thirteen',windows=13,modes=3)
        (workspace/'wrong.npz').write_bytes((inputs/'vdif/visibility.npz').read_bytes()+b'changed')
        assert not (workspace/'tools/run.py').exists()
        log=(out/'server.log').open('w')
        server=subprocess.Popen([str(Path(sys.prefix)/'bin/vsora-ui'),'--workspace',folder,'--port',str(port)],
                                cwd=workspace,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                try:
                    if httpx.get(url+'/api/environment',timeout=1).status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.1)
            else:raise AssertionError('GUI not ready')
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True)
                page=browser.new_page(viewport={'width':1440,'height':1000})
                errors=[];requests=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.on('request',lambda request:requests.append(request.url))
                page.goto(url)
                for case in expected['cases']:
                    name=case['case_id'];page.get_by_role('button',name='保存三次統計',exact=True).click()
                    form=page.locator('#raw-form');button=page.locator('#raw-window-test')
                    form.locator('input[name=input]').fill(name+'/raw.npz')
                    form.locator('input[name=source_visibility]').fill(name+'/visibility.npz')
                    assert button.is_disabled()
                    page.locator('#read-raw-input').click()
                    page.wait_for_function('()=>!document.querySelector("#raw-form button[type=submit]").disabled')
                    form.locator('select[name=channel_index]').select_option(str(case['channel_index']))
                    if name=='legacy':
                        assert button.is_disabled() and '旧形式' in page.locator('#raw-window-note').inner_text()
                        cases.append({'case_id':name,'legacy_disabled':True});continue
                    assert button.is_enabled()
                    with page.expect_request(lambda request:request.url==url+'/api/jobs' and request.method=='POST') as submitted, page.expect_response(lambda response:response.url==url+'/api/jobs' and response.request.method=='POST') as created:
                        button.click()
                    job_id=created.value.json()['id']
                    page.wait_for_function('(id)=>document.querySelector("#job-detail .run-id")?.textContent===id',arg=job_id)
                    request=submitted.value.post_data_json
                    assert set(request)=={'kind','input','source_visibility','channel_index','raw_bispectrum_sha256','source_visibility_sha256'}
                    assert request['kind']=='bispectrum_window_symmetry' and request['channel_index']==case['channel_index']
                    complete='処理完了' if case['expected_success'] else '処理に失敗しました'
                    page.locator('#job-detail .phase-line').get_by_text(complete,exact=True).wait_for(timeout=30000)
                    job=httpx.get(url+'/api/jobs/'+job_id).json()
                    if case['expected_success']:
                        q=case['result'];assert job['state']=='complete' and job['summary']==q
                        detail=page.locator('#job-detail').inner_text();test=q['conditional_test']
                        assert number(test['upper_tail_p_value']) in detail
                        assert number(test['minimum_two_sided_resolution']) in detail
                        assert '全'+str(test['windows'])+'区間' in detail and str(test['features'])+'三角形' in detail
                        assert format(test['group_size'],',')+'通り' in detail
                        assert format(q['frequency_hz']/1e6,'.6f')+' MHz' in detail
                        assert '区間の独立性・結合対称性・上流選別の妥当性：未確認' in detail
                        assert 'p値はCas Aの検出率や画像信頼度ではありません' in detail
                        assert ('5%の判定に必要な分解能がありません' in detail)==(not q['nominal_five_percent_resolution_available'])
                        rows=page.locator('#stored-window-feature-table tr').all()
                        assert len(rows)==1+test['windows']*test['features']
                        for wi in range(test['windows']):
                            for ki in range(test['features']):
                                text=rows[1+wi*test['features']+ki].inner_text()
                                assert str(wi)+' / '+format(q['times_s'][wi],'.6f')+' 秒' in text
                                assert ' / '.join(q['triangle_station_ids'][ki]) in text
                                assert format(q['common_fft_count'][wi][ki],',') in text
                                assert number(q['imaginary_normalized_u3'][wi][ki]) in text
                        assert httpx.get(url+f'/api/jobs/{job_id}/artifacts/window-symmetry.json').json()==q
                        cases.append({'case_id':name,'success':True,'all_scientific_json_identical':True,
                                      'all_feature_rows_checked':test['windows']*test['features'],
                                      'conditional_p_value':test['upper_tail_p_value']})
                        page.screenshot(path=str(out/(name+'-result.png')),full_page=True)
                        if name=='copied':
                            page.set_viewport_size({'width':390,'height':844})
                            assert page.locator('.raw-normalization-scroll').evaluate('(e)=>e.scrollWidth>e.clientWidth')
                            assert not page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                            page.screenshot(path=str(out/'mobile-result.png'),full_page=True)
                            page.set_viewport_size({'width':1440,'height':1000})
                    else:
                        assert job['state']=='failed' and job['summary'] is None
                        assert 'すべての区間・三角形' in job['error_message']
                        assert page.locator('#stored-window-feature-table').count()==0
                        assert '条件付きp値' not in page.locator('#job-detail').inner_text()
                        assert httpx.get(url+f'/api/jobs/{job_id}/artifacts/window-symmetry.json').status_code!=200
                        cases.append({'case_id':name,'success':False,'japanese_failure_without_partial_result':True})
                page.get_by_role('button',name='保存三次統計',exact=True).click()
                form=page.locator('#raw-form')
                form.locator('input[name=input]').fill('thirteen/raw.npz')
                form.locator('input[name=source_visibility]').fill('thirteen/visibility.npz')
                page.locator('#read-raw-input').click()
                page.wait_for_function('()=>!document.querySelector("#raw-form button[type=submit]").disabled')
                assert page.locator('#raw-window-test').is_disabled() and '12を超え' in page.locator('#raw-window-note').inner_text()
                form.locator('input[name=input]').fill('independent/raw.npz')
                form.locator('input[name=source_visibility]').fill('independent/visibility.npz')
                page.locator('#read-raw-input').click()
                page.wait_for_function('()=>!document.querySelector("#raw-window-test").disabled')
                form.locator('input[name=input]').dispatch_event('input')
                assert page.locator('#raw-window-test').is_disabled()
                assert form.locator('button[type=submit]').is_disabled()
                page.locator('#read-raw-input').click()
                page.wait_for_function('()=>!document.querySelector("#raw-window-test").disabled')
                page.evaluate('rawSelection.raw_bispectrum_sha256="0".repeat(64)')
                with page.expect_response(lambda response:response.url==url+'/api/jobs' and response.request.method=='POST') as changed:
                    page.locator('#raw-window-test').click()
                job_id=changed.value.json()['id']
                page.wait_for_function('(id)=>document.querySelector("#job-detail .run-id")?.textContent===id',arg=job_id)
                page.locator('#job-detail .phase-line').get_by_text('処理に失敗しました',exact=True).wait_for(timeout=30000)
                assert '読み直' in page.locator('#job-detail').inner_text()
                assert page.locator('#stored-window-feature-table').count()==0
                page.set_viewport_size({'width':390,'height':844})
                page.get_by_role('button',name='保存三次統計',exact=True).click()
                form.locator('input[name=source_visibility]').fill('wrong.npz')
                with page.expect_response('**/api/bispectrum-input') as checked:page.locator('#read-raw-input').click()
                assert checked.value.status==400 and page.locator('#raw-window-test').is_disabled()
                page.screenshot(path=str(out/'mobile-input.png'),full_page=True)
                font=page.evaluate('document.fonts.check("14px \'VSoRA Japanese\'")')
                overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                external=[r for r in requests if not r.startswith(url+'/')]
                assert font and not overflow and not errors and not external
                result={'state':'complete','source_checkout':source_checkout,'installed_module_imports':not source_checkout,
                    'cases':cases,'total_successful_feature_rows_checked':sum(c.get('all_feature_rows_checked',0) for c in cases),
                    'strict_request_has_no_time_or_window_subset':True,'all_scientific_json_identical_to_stage093':True,
                    'legacy_and_thirteen_window_buttons_disabled':True,'input_edit_invalidates_both_actions':True,
                    'selected_sha_rechecked_by_worker':True,'wrong_companion_rejected':True,
                    'japanese_font_loaded':font,'mobile_root_horizontal_overflow':overflow,'local_table_horizontal_scroll':True,
                    'javascript_errors':errors,'external_requests':len(external),'outside_checkout_workspace':True,
                    'workspace_has_checkout_runner':False,'pythonpath_removed':not source_checkout,'browser':browser.version,
                    'production_rml_noise_model_changed':False,'new_monte_carlo_or_image_validation':False,'actual_hardware_data':False}
                (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');browser.close()
                return result
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()
            log.close()

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('fixtures','reference','output'):p.add_argument('--'+name,required=True)
    p.add_argument('--source-checkout',action='store_true');p.add_argument('--port',type=int,default=8793)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
