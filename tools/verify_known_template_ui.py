"""Actual native GUI holdout study and complete metric/JSON transport."""
import argparse,json,os,subprocess,sys,tempfile,time
from pathlib import Path
import httpx

def run(reference,output,source_checkout=False,port=8794):
    from playwright.sync_api import sync_playwright
    from vsora_ui import models,worker
    from vsora_simulator import known_template_validation,template_score
    from vsora_observation import reference as assets
    root=Path(__file__).resolve().parents[1];prefix=root if source_checkout else Path(sys.prefix)
    assert all(Path(m.__file__).is_relative_to(prefix) for m in (models,worker,known_template_validation,template_score,assets))
    sys.path.insert(0,str(root/'tools'));from verify_bispectrum_power_ui import javascript_exponential as number
    expected=json.loads(Path(reference).read_text());out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    if source_checkout:env['PYTHONPATH']=os.pathsep.join(map(str,[root,*sorted(root.glob('apps/*/src')),*sorted(root.glob('packages/*/src'))]))
    url=f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory(prefix='vsora-known-template-ui-') as folder:
        workspace=Path(folder);assert not (workspace/'tools/run.py').exists()
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
                browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1000})
                errors=[];requests=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url))
                page.goto(url);page.get_by_role('button',name='動作検証',exact=True).click()
                capability=httpx.get(url+'/api/environment').json()
                assert capability['available_validations']==['array_scale','casa_window_symmetry','known_template','independent_training','gaussian_template','phase_template']
                assert not capability['checkout_validation_available']
                page.wait_for_function('()=>!document.querySelector("#validation-form option[value=known_template]").disabled')
                page.locator('#validation-form select').select_option('known_template')
                page.screenshot(path=str(out/'input.png'),full_page=True)
                with page.expect_response(lambda r:r.url==url+'/api/jobs' and r.request.method=='POST') as created:
                    page.locator('#validation-form button[type=submit]').click()
                id=created.value.json()['id']
                page.wait_for_function('(id)=>document.querySelector("#job-detail .run-id")?.textContent===id',arg=id)
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=900000)
                q=httpx.get(url+'/api/jobs/'+id).json()
                assert q['state']=='complete' and q['summary']==expected
                assert httpx.get(url+f'/api/jobs/{id}/artifacts/validation/summary.json').json()==expected
                origin=httpx.get(url+f'/api/jobs/{id}/artifacts/validation/execution-origin.json').json()
                assert origin['native_scientific_module_used'] and not origin['checkout_runner_used']
                assert origin['scientific_module_count']==8 and origin['formal_profile_executed']
                if source_checkout:assert origin['scientific_modules_under_gui_checkout']
                else:assert origin['scientific_modules_under_runtime_prefix'] and origin['configuration_asset_under_runtime_prefix'] and origin['sky_asset_under_runtime_prefix']
                rows=page.locator('#known-template-table tr').all();assert len(rows)==10
                checked=[]
                for row,c in zip(rows[1:],expected['cases'],strict=True):
                    cells=row.locator('td').all();assert len(cells)==5
                    text=cells[0].inner_text()
                    assert c['case_id'] in text and 'M：'+format(c['modes'],',') in text
                    for label,key in (('学習：','training_sefd_jy'),('点源評価：','point_test_sefd_jy'),('Cas A評価：','casa_test_sefd_jy')):
                        assert label+number(c[key]) in cells[1].inner_text()
                    for label,key in (('正答率：','balanced_accuracy'),('AUROC：','empirical_auroc')):
                        assert label+number(c[key]) in cells[2].inner_text()
                    for cell,key in zip(cells[3:],('false_casa_on_point','missed_casa'),strict=True):
                        r=c[key];value_text=cell.inner_text()
                        assert '件数：'+str(r['errors'])+' / '+str(r['trials']) in value_text
                        assert '誤り率：'+number(r['fraction']) in value_text
                        assert '個別95%区間：'+number(r['clopper_pearson_interval'][0])+'〜'+number(r['clopper_pearson_interval'][1]) in value_text
                    state='零天空・同一分布の負対照' if c['zero_sky_control'] else '受信機モデル一致' if c['receiver_model_matches_training'] else '受信機モデル不一致'
                    assert state in text
                    checked.append({'case_id':c['case_id'],'all_display_numbers_checked':True,'state':state})
                detail=page.locator('#job-detail').inner_text()
                for phrase in ('個別95%区間','学習の揺らぎ','画像信頼度は含みません','評価データで閾値や方向を調整していません','実測値ではありません','現在のRMLへの適用はありません'):
                    assert phrase in detail
                caption=page.locator('#job-detail figcaption').inner_text()
                assert '既知二モデルの独立評価' in caption and '画像信頼度ではありません' in caption
                assert page.locator('#job-detail figure img').get_attribute('alt')==caption
                page.screenshot(path=str(out/'result.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                scroll=page.locator('.raw-normalization-scroll').evaluate('(e)=>{e.scrollLeft=e.scrollWidth-e.clientWidth;return e.scrollLeft>0}')
                assert scroll
                page.screenshot(path=str(out/'mobile-values.png'),full_page=True)
                page.locator('.raw-normalization-scroll').evaluate('(e)=>e.scrollLeft=0')
                page.screenshot(path=str(out/'mobile-result.png'),full_page=True)
                overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                font=page.evaluate('document.fonts.check("14px \'VSoRA Japanese\'")')
                external=[r for r in requests if not r.startswith(url+'/')]
                assert not errors and not external and not overflow and font
                result={'state':'complete','source_checkout':source_checkout,'installed_module_imports':not source_checkout,
                    'case_rows':checked,'case_count':9,'full_scientific_json_identical_to_stage096':True,'artifact_json_identical':True,
                    'native_origin':origin,'scientific_module_count':8,'workspace_has_checkout_runner':False,
                    'outside_checkout_workspace':True,'pythonpath_removed':not source_checkout,
                    'all_metric_and_confidence_interval_numbers_checked':True,'japanese_qualification_labels_checked':True,
                    'caption_and_alt_checked':True,'japanese_font_loaded':font,'mobile_root_horizontal_overflow':overflow,
                    'actual_table_scroll_performed':scroll,'javascript_errors':errors,'external_requests':len(external),
                    'browser':browser.version,'production_rml_noise_model_changed':False,'actual_hardware_data':False}
                (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');browser.close();return result
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()
            log.close()

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('reference','output'):p.add_argument('--'+name,required=True)
    p.add_argument('--source-checkout',action='store_true');p.add_argument('--port',type=int,default=8794)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
