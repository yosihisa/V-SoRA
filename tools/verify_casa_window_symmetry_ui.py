"""Real full native known-voltage job in a runnerless GUI workspace."""
import argparse,json,os
from decimal import Decimal,localcontext,ROUND_HALF_UP
import math
from pathlib import Path
import subprocess,sys,tempfile,time
import httpx

def javascript_exponential(value):
 """Independent decimal rounding for finite Number.toExponential(4) text.

 ECMAScript chooses the larger positive decimal coefficient at exact ties;
 Python's default formatting uses ties to even. Start from the exact binary
 float, then apply the browser's five-significant-digit presentation rule.
 """
 value=float(value)
 if not math.isfinite(value):raise ValueError('finite displayed scientific value required')
 if value==0:return '0.0000e+0'
 with localcontext() as context:
  context.prec=80
  exact=Decimal.from_float(value)
  rounded=exact.quantize(Decimal(1).scaleb(exact.adjusted()-4),rounding=ROUND_HALF_UP)
  exponent=rounded.adjusted();coefficient=rounded.scaleb(-exponent)
  return f'{coefficient:.4f}e{exponent:+d}'


def run(output,port=8792,source_checkout=False):
 from playwright.sync_api import sync_playwright
 from vsora_ui import models,worker
 checkout=Path(__file__).resolve().parents[1];module_root=checkout if source_checkout else Path(sys.prefix)
 assert all(Path(m.__file__).is_relative_to(module_root) for m in (models,worker))
 out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
 env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
 url=f'http://127.0.0.1:{port}'
 names={'point':'点源','casa':'Cas A代理形状','zero':'無信号','heterogeneous_point':'局別SEFDの点源','equal_double':'等輝度二点','unequal_double':'非等輝度二点','quadratic_phase':'点源＋二次位相','known_inverse':'点源＋真値逆位相','copied_windows':'同じwindowを複製'}
 number=javascript_exponential
 with tempfile.TemporaryDirectory(prefix='vsora-casa-symmetry-ui-') as folder:
  assert not (Path(folder)/'tools/run.py').exists()
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
    capability=httpx.get(url+'/api/environment').json()
    assert capability['available_validations']==['array_scale','casa_window_symmetry','known_template','independent_training','gaussian_template','phase_template'] and not capability['checkout_validation_available']
    page.wait_for_function('() => document.querySelector("#validation-form select").value === "array_scale"')
    assert page.locator('#validation-form select option:enabled').count()==len(capability['available_validations'])
    page.locator('#validation-form select[name=validation]').select_option('casa_window_symmetry')
    assert '十数分以上' in page.locator('#validation-form').inner_text() and '存在確率や画像の信頼度ではありません' in page.locator('#validation-form').inner_text()
    page.screenshot(path=str(out/'input.png'),full_page=True)
    page.get_by_role('button',name='検証を開始',exact=True).click()
    page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=2400000)
    job_id=httpx.get(url+'/api/jobs').json()[0]['id'];job=httpx.get(url+'/api/jobs/'+job_id).json();q=job['summary']
    assert job['state']=='complete' and q['profile']=='full' and not q['software_smoke_only'] and len(q['cases'])==53
    assert q==json.loads((checkout/'validation/runs/stage087/known-casa-window-symmetry.json').read_text())
    origin=httpx.get(url+f'/api/jobs/{job_id}/artifacts/validation/execution-origin.json').json()
    assert origin['native_scientific_module_used'] and not origin['checkout_runner_used'] and origin['formal_profile_executed']
    assert origin['scientific_module_count']==6
    for key in ('scientific_modules_under_runtime_prefix','configuration_asset_under_runtime_prefix','sky_asset_under_runtime_prefix'):assert origin[key] is (not source_checkout)
    assert origin['scientific_modules_under_gui_checkout'] is source_checkout
    assert origin['configuration_asset_sha256']==q['configuration_asset_sha256']
    (out/'execution-origin.json').write_text(json.dumps(origin,indent=2)+'\n')
    def rows(selector):return page.locator(selector).evaluate('(t)=>Array.from(t.querySelectorAll("tr")).slice(1).map(r=>Array.from(r.querySelectorAll("td")).map(c=>c.innerText))')
    display=rows('#casa-symmetry-table');assert len(display)==53
    for c,cells in zip(q['cases'],display):
     assert len(cells)==8 and c['case_id'] in cells[0]
     assert ('独立windowを生成' if c['window_draws_independent'] else '同じwindowを複製') in cells[0]
     assert names[c['mode']] in cells[1] and f'M={c["modes"]} / 最大{c["maximum_baseline_m"]:g}m' in cells[1]
     if c['mode']=='heterogeneous_point':assert '局別SEFD '+' / '.join(map(number,c['receiver_sefd_jy'])) in cells[1]
     else:assert 'receiver SEFD '+number(c['receiver_sefd_jy'][0])+' Jy' in cells[1]
     assert str(c['trials'])+'反復' in cells[2]
     assert ('生成モデルが帰無条件を支持' if c['joint_null_invariance_supported_by_generation'] else '帰無条件は保証しない') in cells[2]
     assert number(c['spatial_covariance_real_gauge_relative_residual']) in cells[2]
     for i,a in enumerate(c['levels']):
      assert f'{a["rejections"]} / {c["trials"]} = '+number(a['fraction']) in cells[i+3]
      assert number(a['reference_binomial_mc_se_at_nominal']) in cells[i+3]
      assert ('固定6 MC SE基準内' if a['null_mc_check_applied'] else '帰無MC基準は適用しない') in cells[i+3]
     assert cells[5]==' / '.join(number(c[k]) for k in ('p_value_minimum','p_value_median','p_value_maximum'))
     for k in ('maximum_gain_feature_abs_difference','maximum_conjugation_transport_abs_difference','maximum_known_inverse_feature_abs_difference'):assert number(c[k]) in cells[6]
     assert str(c['gain_checks'])+'反復確認' in cells[6]
     for k,label in [('synthetic_quadratic_phase_applied','二次位相'),('known_truth_inverse_phase_applied','真値逆補正'),('unknown_lo_estimated','未知LO推定')]:assert label+'：'+('あり' if c[k] else 'なし') in cells[7]
     saved=httpx.get(url+f'/api/jobs/{job_id}/artifacts/validation/cases/{c["case_id"]}.json').json();assert saved==c
    page.locator('#casa-symmetry-details summary').click();components=rows('#casa-symmetry-components');assert len(components)==2968
    n=0
    for c in q['cases']:
     for i,(mean,se) in enumerate(zip(c['mc_mean_window_imaginary_features'],c['mc_standard_error_window_mean_features'])):
      assert components[n]==[c['case_id'],str(i),number(mean),number(se)];n+=1
    assert '画像の誤差棒ではありません' in page.locator('#casa-symmetry-details').inner_text()
    page.locator('#casa-symmetry-details summary').click()
    for key,value,predicate in [('mode','equal_double',lambda c:c['mode']=='equal_double'),('modes','19200',lambda c:c['modes']==19200),('maximum_baseline_m','25',lambda c:c['maximum_baseline_m']==25),('receiver_sefd','heterogeneous',lambda c:c['mode']=='heterogeneous_point')]:
     field=page.locator(f'#casa-symmetry-filters select[name={key}]');field.select_option(value)
     assert len(rows('#casa-symmetry-table'))==sum(map(predicate,q['cases']))
     field.select_option('all')
    assert len(rows('#casa-symmetry-table'))==53
    text=page.locator('#job-detail').inner_text()
    for explanation in ('非棄却も点源の証明ではありません','実ADC・FFT・FIR','真値逆位相は未知LO推定の成功ではありません'):assert explanation in text
    figure=page.locator('figure').filter(has=page.locator('img[src$="casa-window-symmetry.png"]'))
    assert '実観測時間の保証ではありません' in figure.locator('figcaption').inner_text()
    figure.locator('img').wait_for();page.wait_for_function('() => Array.from(document.querySelectorAll("#job-detail img")).every(i=>i.complete && i.naturalWidth>0)')
    page.get_by_text('条件・画像・相関ファイルを保存',exact=True).click()
    with page.expect_download() as info:page.locator('#job-detail .download-list a').filter(has_text='validation/summary.json').click()
    assert json.loads(Path(info.value.path()).read_text())==q
    page.screenshot(path=str(out/'result.png'),full_page=True)
    page.locator('#casa-symmetry-filters select[name=mode]').select_option('equal_double')
    page.set_viewport_size({'width':390,'height':844});overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
    assert page.locator('.casa-symmetry-scroll').first.evaluate('(e)=>e.scrollWidth>e.clientWidth')
    assert page.locator('#casa-symmetry-table td').first.bounding_box()['width']>=100
    page.screenshot(path=str(out/'mobile.png'),full_page=True)
    page.evaluate('document.fonts.ready');font=page.evaluate('document.fonts.check("14px VSoRA Japanese")')
    external=[u for u in requests if not u.startswith(url+'/')];assert not errors and not external and not overflow and font
    result={'state':'complete','source_checkout':source_checkout,'outside_checkout_workspace':True,'pythonpath_removed':True,'native_full_worker_executed':True,'workspace_has_checkout_runner':False,'entire_scientific_result_identical_to_stage087':True,'conditions_all_numbers_checked':53,'component_rows_all_numbers_checked':n,'case_json_files_identical':53,'summary_download_identical':True,'all_four_filters_checked':True,'caption_and_limitations_checked':True,'japanese_font_loaded':font,'mobile_horizontal_overflow':overflow,'local_table_horizontal_scroll_checked':True,'javascript_errors':len(errors),'external_requests':len(external),'science_modules_and_assets_under_runtime_prefix':not source_checkout,'actual_hardware_data':False,'image_reconstructed':False,'production_rml_noise_model_changed':False,'browser_environment':'WSL headless Chromium; Windows/WSLg unverified'}
    browser.close();(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');return result
  finally:
   server.terminate()
   try:server.wait(timeout=8)
   except subprocess.TimeoutExpired:server.kill();server.wait(timeout=2)
   log.close()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--port',type=int,default=8792);p.add_argument('--source-checkout',action='store_true');print(json.dumps(run(**vars(p.parse_args())),indent=2))
