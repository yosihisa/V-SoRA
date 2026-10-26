"""現在の保存相関を既存日本語GUIで操作し、公開135/136の診断と照合する。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import httpx
from playwright.sync_api import sync_playwright


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def exponential(value, digits):
    """Python側の指数表記をブラウザのゼロなし指数へ合わせる。"""
    mantissa, exponent = f'{value:.{digits}e}'.split('e')
    return mantissa+'e'+('+' if int(exponent) >= 0 else '-')+str(abs(int(exponent)))


def fixed_cases(root):
    old = root/'outputs/stage132-source-study'
    saved = json.loads((root/'validation/runs/stage136/reference.json').read_text())
    cases = []
    for row in saved['series']:
        folder = old/(row['raw_case']+'_t0.3')/'pipeline'
        cases.append({'label':row['raw_case']+'/'+str(row['channel_index'])+'/'+row['mode'],
            'mode':'time_scatter', 'input':folder/'pilot/shard-00000.npz',
            'profile':folder/'rate-only.json' if row['mode']=='estimated_rate_rotation' else None,
            'channel':row['channel_index'], 'expected':row['diagnostic'],
            'expected_json_sha256':row['diagnostic_json_sha256'], 'kind':'pilot'})
    record = json.loads((root/'validation/runs/stage135/reference.json').read_text())
    for name, channel in [('high_a_t0.3',4),('high_a_t0.3',0),('weak_a_t1',4)]:
        row = next(x for x in record['cells'] if x['case']==name and x['channel_index']==channel)
        path = root/'outputs/stage135-source-study'/name/f'channel-{channel}/diagnostic.json'
        assert sha(path)==row['diagnostic_json_sha256']
        cases.append({'label':name+'/'+str(channel)+'/noise','mode':'noise',
            'input':old/name/'pipeline/correlation/shard-00000.npz','profile':None,
            'channel':channel,'expected':json.loads(path.read_text()),
            'expected_json_sha256':row['diagnostic_json_sha256'],'kind':'cell'})
    path = old/'high_a_t0.3/pipeline/correlation/shard-00000.npz'
    cases.append({'label':'single-final-cell/time_scatter','mode':'time_scatter','input':path,
        'profile':None,'channel':4,'expected':{**saved['final_correlation_probe'],'input_sha256':sha(path),
        'rate_profile_sha256':None},'expected_json_sha256':None,'kind':'probe'})
    assert len(cases)==28
    for case in cases:
        assert sha(case['input'])==case['expected']['input_sha256']
        if case['profile'] is not None:
            assert sha(case['profile'])==case['expected']['rate_profile_sha256']
    return cases


def check_time_display(page, result):
    if result['state']!='conditional_estimate':
        assert '32〜8192個の時間cellが必要' in page.locator('#job-detail').inner_text()
        return 0
    rows = page.locator('#time-scatter-table tr').all()[1:]
    assert len(rows)==len(result['baselines'])==28
    for row, expected in zip(rows,result['baselines'],strict=True):
        cells=row.locator('td').all_text_contents();ratio=expected['mean_to_time_power_ratio_unbounded']
        assert cells[0]==' / '.join(expected['station_ids'])+' / '+('条件付き' if ratio is not None else '未判定（信号power不足）')
        assert row.locator('td').nth(1).locator('p').all_text_contents()==['時間 '+exponential(expected['noise_subtracted_time_power'],5),'平均 '+exponential(expected['noise_subtracted_mean_power'],5),'差 '+exponential(expected['excess_time_scatter'],5)]
        assert cells[2]==('—' if ratio is None else f'{ratio:.6f}')
    return len(rows)


def check_noise_display(page, result):
    if result['state']=='inactive':
        assert '有効な基線がありません' in page.locator('#job-detail').inner_text()
        return {'baselines':0,'closures':0}
    assert result['state']=='conditional_estimate'
    metrics=page.locator('#job-detail .metric strong').all_text_contents()
    assert metrics==[f"{result['nominal_common_fft_blocks']:,}",str(sum(result['closure_joint_valid'][:result['phase_count']]))+' / '+str(result['phase_count']),str(sum(result['closure_joint_valid'][result['phase_count']:]))+' / '+str(result['logamp_count'])]
    page.get_by_text('基線ごとの条件付きSNR',exact=True).click()
    detail=page.locator('#job-detail details').filter(has=page.get_by_text('基線ごとの条件付きSNR',exact=True))
    rows=detail.locator('table tr').all()[1:]
    assert len(rows)==len(result['baseline_snr_conditional'])
    for row, pair, snr in zip(rows,result['pairs'],result['baseline_snr_conditional'],strict=True):
        assert row.locator('td').all_text_contents()==[' / '.join(result['station_ids'][k] for k in pair),f'{snr:.3f}']
    page.get_by_text('Closure行ごとの誤差と有効状態',exact=True).click()
    table=page.locator('#job-detail details').filter(has=page.get_by_text('Closure行ごとの誤差と有効状態',exact=True)).locator('table')
    rows=table.locator('tr').all()[1:]
    assert len(rows)==len(result['closure_joint_valid'])
    for i,(row,valid) in enumerate(zip(rows,result['closure_joint_valid'],strict=True)):
        phase=i<result['phase_count'];index=i if phase else i-result['phase_count']
        sigma=exponential(max(0,result['estimated_joint_closure_covariance'][i][i])**.5,4)+(' rad' if phase else '（無次元）') if valid else '—'
        assert row.locator('td').all_text_contents()==[('phase ' if phase else 'log amplitude ')+str(index+1),'一次近似の対象' if valid else '未判定（SNR不足）',sigma]
    return {'baselines':len(result['pairs']),'closures':len(rows)}


def run(repository, output, mode, limit=None):
    root=Path(repository).resolve();out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    cases=fixed_cases(root)
    if limit is not None:cases=cases[:limit]
    inputs={str(p):sha(p) for case in cases for p in [case['input'],case['profile']] if p is not None}
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');env.pop('PYTHONPATH',None)
    if mode=='source':env['PYTHONPATH']=os.pathsep.join(map(str,[root,*sorted(root.glob('apps/*/src')),*sorted(root.glob('packages/*/src'))]))
    script='''import importlib,json,pathlib,sys,sysconfig,uvicorn
names=['vsora_ui.server','vsora_ui.noise','vsora_ui.models','vsora_ui.worker','vsora_ui.jobs','vsora_correlator.time_scatter','vsora_correlator.noise_diagnostics','vsora_formats.spectral','vsora_imaging.closure_noise','vsora_simulator.visibility_noise_estimate']
modules={n:str(pathlib.Path(importlib.import_module(n).__file__).resolve()) for n in names}
root=pathlib.Path(sys.argv[1]);mode=sys.argv[2]
if mode=='installed':
 assert all(pathlib.Path(v).is_relative_to(pathlib.Path(sysconfig.get_path('purelib'))) for v in modules.values())
 assert 'PYTHONPATH' not in __import__('os').environ
else:
 roots={d.name:d for d in list((root/'apps').glob('*/src/vsora_*'))+list((root/'packages').glob('*/src/vsora_*'))}
 assert all(pathlib.Path(v)==roots[n.split('.')[0]]/('/'.join(n.split('.')[1:])+'.py') for n,v in modules.items())
pathlib.Path(sys.argv[4]).write_text(json.dumps(modules,indent=2))
from vsora_ui.server import create_app
from vsora_ui.jobs import source_root
assert source_root()==(root if mode=='source' else None)
uvicorn.run(create_app(pathlib.Path.cwd()),host='127.0.0.1',port=int(sys.argv[3]),log_level='warning')
'''
    with tempfile.TemporaryDirectory(prefix='vsora-saved-diagnostics-') as folder:
        workspace=Path(folder);assert not workspace.is_relative_to(root) and not (workspace/'tools/run.py').exists()
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        url=f'http://127.0.0.1:{port}';log=(out/'server.log').open('w')
        server=subprocess.Popen([sys.executable,'-c',script,str(root),mode,str(port),str(out/'module-paths.json')],cwd=workspace,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                if server.poll() is not None:raise AssertionError('owned server failed to start')
                try:
                    if httpx.get(url+'/api/environment',timeout=1).status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.1)
            else:raise AssertionError('owned server startup timed out')
            assert not httpx.get(url+'/api/environment').json()['checkout_validation_available']
            with sync_playwright() as playwright:
                browser=playwright.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1000},accept_downloads=True)
                errors=[];requests=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda q:requests.append(q.url))
                page.goto(url);page.evaluate('document.fonts.ready');assert page.evaluate('document.fonts.check("14px \'VSoRA Japanese\'")')
                checked=[];baseline_rows=0;negative=0;above=0;null=0
                for case in cases:
                    page.get_by_role('button',name='雑音診断',exact=True).click();form=page.locator('#noise-form')
                    form.locator('select[name=diagnostic_mode]').select_option(case['mode'])
                    form.locator('input[name=input]').fill(str(case['input']))
                    assert form.locator('button[type=submit]').is_disabled()
                    if case['mode']=='time_scatter':form.locator('input[name=rate_profile]').fill(str(case['profile']) if case['profile'] is not None else '')
                    page.get_by_role('button',name='入力の時刻・周波数を読む',exact=True).click()
                    page.wait_for_function('() => !document.querySelector("#noise-form button[type=submit]").disabled')
                    assert form.locator('select[name=time_index]').is_disabled()==(case['mode']=='time_scatter')
                    form.locator('select[name=channel_index]').select_option(str(case['channel']))
                    expected=case['expected'];frequency=f"{expected['frequency_hz']/1e6:.6f} MHz"
                    assert frequency in form.locator('select[name=channel_index] option:checked').inner_text()
                    if case['mode']=='noise':form.locator('select[name=time_index]').select_option('0')
                    with page.expect_response(lambda q:q.request.method=='POST' and q.url==url+'/api/jobs') as response:form.locator('button[type=submit]').click()
                    identity=response.value.json()['id'];page.wait_for_function('(id) => document.querySelector("#job-detail .run-id")?.textContent===id',arg=identity)
                    page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=60000)
                    detail=httpx.get(url+'/api/jobs/'+identity).json();result=detail['summary'];assert detail['state']=='complete' and result==expected
                    assert 'RMLの重み・採否は変更していません' in page.locator('#job-detail').inner_text()
                    if case['mode']=='time_scatter':
                        baseline_rows+=check_time_display(page,result)
                        ratios=[x['mean_to_time_power_ratio_unbounded'] for x in result.get('baselines',[])]
                        null+=sum(x is None for x in ratios);negative+=sum(x is not None and x<0 for x in ratios);above+=sum(x is not None and x>1 for x in ratios)
                        display={'baseline_rows':len(ratios),'null':sum(x is None for x in ratios)}
                    else:display=check_noise_display(page,result)
                    page.get_by_text('詳しい条件と数値',exact=True).click()
                    assert json.loads(page.locator('#job-detail details pre').first.inner_text())==expected
                    page.get_by_text('条件・画像・相関ファイルを保存',exact=True).click()
                    name='time-scatter.json' if case['mode']=='time_scatter' else 'noise.json'
                    downloads=[]
                    for artifact in [name,'summary.json']:
                        with page.expect_download() as download:page.locator('#job-detail').get_by_role('link',name=artifact,exact=True).click()
                        path=Path(download.value.path());assert json.loads(path.read_text())==expected
                        if artifact==name and case['expected_json_sha256'] is not None:assert sha(path)==case['expected_json_sha256']
                        downloads.append({'artifact':artifact,'json_sha256':sha(path)})
                    checked.append({'label':case['label'],'state':result['state'],'display':display,'downloads':downloads})
                    write_json(out/'progress.json',{'state':'running','completed':len(checked),'total':len(cases)})
                    if case['label']=='weak_a/4/estimated_rate_rotation':
                        page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
                        # 既存の固定幅テーブルはセル内で折り返す。存在しない横スクロールを合格扱いにしない。
                        mobile_table=page.locator('#time-scatter-table').evaluate('(t)=>({width:t.clientWidth,contentWidth:t.scrollWidth,parentWidth:t.parentElement.clientWidth,overflowWrap:getComputedStyle(t.querySelector("td")).overflowWrap})')
                        assert mobile_table['contentWidth']<=mobile_table['parentWidth'] and mobile_table['overflowWrap']=='anywhere'
                        page.screenshot(path=str(out/'mobile-result.png'),full_page=True)
                        page.set_viewport_size({'width':1440,'height':1000})
                    print(json.dumps({'mode':mode,'case':case['label'],'completed':len(checked)}),flush=True)
                page.set_viewport_size({'width':390,'height':844});page.get_by_role('button',name='雑音診断',exact=True).click()
                assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
                assert page.evaluate('document.fonts.check("14px \'VSoRA Japanese\'")')
                assert not errors and all(q==url or q.startswith(url+'/') for q in requests)
                assert not any(q['state'] in ('queued','running') for q in httpx.get(url+'/api/jobs').json())
                if limit is None:assert (baseline_rows,null,negative,above)==(672,50,174,148)
                result={'stage':137,'state':'complete','mode':mode,'browser':browser.version,'cases':checked,
                    'actual_gui_workers':len(cases),'actual_json_downloads':2*len(cases),'baseline_rows_checked':baseline_rows,
                    'null_ratios_displayed':null,'negative_ratios_displayed':negative,'above_one_ratios_displayed':above,
                    'all_values_and_json_match':True,'project_modules_verified':10,'outside_checkout':True,'runner_absent':True,
                    'installed_pythonpath_absent':mode=='installed','japanese_font_390px':True,'page_overflow':False,
                    'mobile_table_wrapping_verified':limit is None,'mobile_table_measurement':mobile_table if limit is None else None,'javascript_errors':errors,'external_requests':0,
                    'hardware_coherence_measured':False,'production_changed':False,'truth_numerical_values_used':False}
                browser.close();write_json(out/'verification.json',result)
                assert all(sha(name)==value for name,value in inputs.items())
                assert sum(p.stat().st_size for p in out.rglob('*') if p.is_file())<64*1024**2
                return result
        finally:
            server.terminate()
            try:server.wait(timeout=15)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)
            log.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--repository',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--mode',choices=['source','installed'],required=True);parser.add_argument('--limit',type=int)
    arguments=parser.parse_args();run(**vars(arguments))
