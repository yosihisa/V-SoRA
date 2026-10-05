"""Actual maximum baseline inputs in three Japanese scientific workflows, with explicit import origin."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,tempfile,time
import httpx
from playwright.sync_api import sync_playwright


def run(output,port=8789,source_checkout=False):
    from vsora_ui import models,worker
    checkout=Path(__file__).resolve().parents[1]
    module_root=checkout if source_checkout else Path(sys.prefix)
    assert all(Path(m.__file__).is_relative_to(module_root) for m in (models,worker))
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    url=f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory(prefix='vsora-layout-ui-') as folder:
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
                records=[]
                cases=[
                    ('simulation','模擬観測','simulation-form','模擬観測して画像化',{'model':'point','stations':'4','layout':'ring','duration_s':'60','integration_s':'60'},50.),
                    ('rml','Closure＋RML','rml-form','Closure＋RMLで模擬画像を復元',{'model':'casa','stations':'8','layout':'spread','duration_s':'3600','snapshots':'8','integration_s':'0.3','sefd_jy':'1000','starts':'1','max_iterations':'100'},100.),
                    ('sensitivity','感度計画','sensitivity-form','短積分の感度を概算',{'stations':'8','layout':'line','diameter_m':'1','system_temperature_k':'100','integration_s':'0.3','bandwidth_hz':'256000'},200.),
                ]
                page.goto(url)
                for kind,title,form_id,button,fields,maximum in cases:
                    page.get_by_role('button',name=title,exact=True).click();form=page.locator('#'+form_id);field=form.locator('input[name=maximum_baseline_m]')
                    assert field.input_value()=='600' and field.get_attribute('min')=='10' and field.get_attribute('max')=='600'
                    assert '全局間距離の最大値' in form.inner_text()
                    if kind=='rml':form.locator('details summary').click()
                    for key,value in fields.items():
                        element=form.locator('[name='+key+']')
                        if element.evaluate('(e)=>e.tagName')=='SELECT':element.select_option(value)
                        else:element.fill(value)
                    field.fill(str(maximum))
                    if kind!='sensitivity':form.locator('input[name=noise]').uncheck()
                    page.screenshot(path=str(out/(kind+'-input.png')),full_page=True)
                    form.get_by_role('button',name=button,exact=True).click()
                    page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=150000)
                    job_id=httpx.get(url+'/api/jobs').json()[0]['id'];job=httpx.get(url+'/api/jobs/'+job_id).json();q=job['summary'];assert job['state']=='complete'
                    positions=[s['enu_m'] for s in q['config']['stations']]
                    import math,copy
                    distance=max(math.dist(a,b) for a in positions for b in positions);assert abs(distance-maximum)<1e-10
                    page.locator('#job-detail .metric').filter(has_text='設定の最大局間距離').get_by_text(f'{maximum:.1f} m',exact=True).wait_for()
                    page.wait_for_function('() => Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                    page.get_by_text('条件・画像・相関ファイルを保存',exact=True).click()
                    with page.expect_download() as info:page.get_by_role('link',name='summary.json',exact=True).click()
                    assert json.loads(Path(info.value.path()).read_text())==q
                    numeric={'kind':kind,'requested_maximum_baseline_m':maximum,'calculated_maximum_enu_baseline_m':distance,'config':q['config'],'metrics':q.get('metrics'),'imaging':q.get('imaging'),'independent_closure_counts':q.get('independent_closure_counts')}
                    if kind=='rml':
                        rml=copy.deepcopy(q['rml']);rml.pop('input_sha256',None)
                        for item in rml['runs']:item.pop('elapsed_s',None)
                        numeric['rml']=rml;numeric['coherent_integration_s']=q['coherent_integration_s'];numeric['recorded_exposure_per_station_s']=q['recorded_exposure_per_station_s']
                        assert q['coherent_integration_s']==.3 and q['recorded_exposure_per_station_s']==2.4 and q['rml']['image_sum']>0
                    if kind=='sensitivity':assert q['independent_closure_counts']=={'phase':0,'logamp':0}
                    records.append(numeric)
                    page.screenshot(path=str(out/(kind+'-result.png')),full_page=True)
                    page.set_viewport_size({'width':390,'height':844});overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth');assert not overflow
                    page.screenshot(path=str(out/(kind+'-mobile.png')),full_page=True);page.set_viewport_size({'width':1440,'height':1000})
                font=page.evaluate('document.fonts.check("14px VSoRA Japanese")');external=[u for u in requests if not u.startswith(url+'/')]
                assert font and not errors and not external
                summary={'state':'complete','source_checkout':source_checkout,'installed_imports':not source_checkout,'outside_checkout_workspace':True,'pythonpath_removed':True,
                    'real_simulation_rml_sensitivity_workers_executed':True,'maximum_baselines_m':[50.,100.,200.],
                    'form_limits_and_defaults_checked':True,'saved_coordinates_and_actual_distance_metrics_checked':True,'json_downloads_identical':True,
                    'japanese_font_loaded':font,'mobile_horizontal_overflow':False,'javascript_errors':len(errors),'external_requests':len(external),
                    'low_sensitivity_zero_expected_counts_preserved':True,'rml_optimizer_stops_recorded':True,'image_quality_validated':False,
                    'actual_station_positions_modified':False,'actual_hardware_data':False,'browser_environment':'WSL headless Chromium; Windows/WSLg unverified'}
                browser.close();(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
                (out/'numeric-results.json').write_text(json.dumps(records,indent=2,allow_nan=False)+'\n');return summary
        finally:
            server.terminate()
            try:server.wait(timeout=8)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=2)
            log.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--port',type=int,default=8789)
    p.add_argument('--source-checkout',action='store_true');print(json.dumps(run(**vars(p.parse_args())),indent=2))
