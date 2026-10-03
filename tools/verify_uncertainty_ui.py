"""Installed noise-diagnostic GUI; explicitly checkout-owned workflows."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import httpx
from playwright.sync_api import sync_playwright


def run(output, port=8774, validation='uncertainty'):
    if validation not in ('uncertainty', 'covariance', 'closure_noise'):
        raise ValueError('Unknown validation workflow')
    from vsora_ui import models, worker
    assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (models, worker))
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    checkout=Path(__file__).resolve().parents[1];url=f'http://127.0.0.1:{port}'
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-gaussian-ui-') as folder:
        workspace=Path(folder);(workspace/'tools').mkdir();(workspace/'tools/run.py').symlink_to(checkout/'tools/run.py')
        log=(out/'server.log').open('w');server=subprocess.Popen([str(Path(sys.prefix)/'bin/vsora-ui'),
            '--workspace',folder,'--port',str(port)],cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+15
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
                page.locator('#validation-form select[name=validation]').select_option(validation)
                page.get_by_role('button',name='検証を開始',exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了',exact=True).wait_for(timeout=90000)
                job_id=httpx.get(url+'/api/jobs').json()[0]['id'];job=httpx.get(url+'/api/jobs/'+job_id).json();q=job['summary']
                text=page.locator('#job-detail').inner_text()
                assert not q['actual_hardware_data']
                if validation=='uncertainty':
                    assert q['type']=='rate_uncertainty_validation' and q['draws']==65536 and len(q['gaussian_results'])==6
                    assert not q['covariance_calibrated_against_rate_solver']
                    assert '仮定Gaussian誤差の計算検証' in text and '標本の振幅平均' in text
                    assert '推定器の誤差や実機の位相安定性を測った実験ではありません' in text
                    scientific={'draws':q['draws'],'cases':len(q['gaussian_results']),
                        'covariance_calibrated_against_rate_solver':False,
                        'scope':'Conditional Gaussian calculation/UI. No real rate covariance calibration or image fidelity.'}
                elif validation=='covariance':
                    assert q['type']=='rate_covariance_validation' and q['trials_per_group']==1024 and len(q['groups'])==8
                    assert not q['physical_iq_vdif_processed']
                    assert 'rate近似σと推定誤差の比較' in text and '誤差統計は採用例だけ' in text
                    assert '実IQ・VDIFや実OCXOの測定ではありません' in text
                    assert '条件ごとのSNRは揃えていません' in text
                    assert page.locator('#job-detail .window-table tr').count()==9
                    for r in q['groups']:
                        assert r['statistics_conditioned_on_accepted']
                        assert f"{r['accepted_count']} / {r['trials']}" in text
                        value=r['accepted_fraction_inside_nominal_95pct_ellipsoid']
                        if value is not None: assert f'{100*value:.2f}%' in text
                    scientific={'trials_per_group':q['trials_per_group'],'groups':len(q['groups']),
                        'statistics_conditioned_on_accepted':True,'physical_iq_vdif_processed':False,
                        'scope':'Finite assumed visibility-noise experiment/UI, conditional on accepted fits. No physical IQ, OCXO or image fidelity.'}
                else:
                    assert q['type']=='joint_closure_noise_validation' and q['trials_per_case']==16384 and len(q['cases'])==8
                    assert not q['physical_iq_vdif_processed'] and not q['production_rml_noise_model_changed']
                    assert '共有信号がClosureの雑音へ与える影響' in text
                    assert '実受信機から未知の雑音を推定した結果ではありません' in text
                    assert 'Gaussian電圧512標本' in text and '観測された値による選別はしていません' in text
                    assert 'phaseとlog amplitudeの交差共分散' in text
                    assert page.locator('#job-detail .window-table tr').count()==9
                    for r in q['cases']:
                        assert not r['selection_on_observed_visibility']
                        for key in ('empirical_to_first_order_variance_ratio','first_order_to_independent_circular_variance_ratio'):
                            values=r[key];assert f'{min(values):.3f}〜{max(values):.3f}' in text
                    scientific={'trials_per_case':q['trials_per_case'],'cases':len(q['cases']),
                        'generation_methods':sorted({r['noise_generation'] for r in q['cases']}),
                        'selection_on_observed_visibility':False,'physical_iq_vdif_processed':False,
                        'production_rml_noise_model_changed':False,
                        'scope':'Known station covariance and first-order closure propagation. Visibility approximation and iid Gaussian voltage samples shown separately. No ADC/FIR/VDIF, hardware or image fidelity.'}
                page.wait_for_function('Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                page.screenshot(path=str(out/'result.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844});overflow=page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                page.screenshot(path=str(out/'mobile.png'),full_page=True)
                font=page.evaluate('document.fonts.check("14px \'VSoRA Japanese\'")');external=[r for r in requests if not r.startswith(url+'/')]
                assert not errors and not external and not overflow and font
                summary={'installed_gui_imports':True,'validation_workflow_from_checkout':True,'independent_workspace':True,
                    'state':job['state'],'browser':browser.version,'javascript_errors':errors,'external_requests':len(external),
                    'japanese_font_loaded':font,'mobile_horizontal_overflow':overflow,
                    'validation':validation,'actual_hardware_data':False,'browser_environment':'WSL headless Chromium; Windows/WSLg unverified',**scientific}
                browser.close();(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary
        finally:
            server.terminate()
            try:server.wait(timeout=8)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=2)
            log.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--port',type=int,default=8774)
    parser.add_argument('--validation',choices=('uncertainty','covariance','closure_noise'),default='uncertainty')
    print(json.dumps(run(**vars(parser.parse_args())),indent=2))
