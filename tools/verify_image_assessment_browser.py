"""保存済み実RML記録と実workerを、日本語GUIの実Chromiumで照合する。"""
import argparse
from copy import deepcopy
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


def run(repository, output, mode):
    root = Path(repository).resolve()
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    rows = json.loads((root/'validation/runs/stage119/reference.json').read_text())['cases']

    def data(pixels=8):
        row = next(x for x in rows if x['pixels'] == pixels and x['branch'] == 'estimated_rate')
        return deepcopy({'rml': row['science']['rml_summary'], 'metrics': row['science']['reference_metrics']})

    no_ref = data(); no_ref.pop('metrics')
    broken = data(); broken['rml']['selected_start'] = 999
    legacy = data(); legacy['metrics']['comparison_version'] = 1
    cases = [('収束と参照', 'rml', 'complete', data(), 'converged', 'evaluated'),
             ('未収束と参照', 'analysis', 'complete', data(32), 'not_converged', 'evaluated'),
             ('参照なし', 'synthesis', 'complete', no_ref, 'converged', 'not_evaluated'),
             ('画像未実行', 'analysis', 'failed', None, 'not_run', 'not_evaluated'),
             ('壊れた記録', 'analysis', 'complete', broken, None, None),
             ('旧参照形式', 'sequence', 'complete', legacy, 'converged', 'not_evaluated')]
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    env.pop('PYTHONPATH', None)
    if mode == 'source':
        paths = [root, *sorted(root.glob('apps/*/src')), *sorted(root.glob('packages/*/src'))]
        env['PYTHONPATH'] = os.pathsep.join(map(str, paths))
    with tempfile.TemporaryDirectory(prefix='vsora-image-assessment-') as folder:
        workspace = Path(folder)
        assert not workspace.is_relative_to(root) and not (workspace/'tools/run.py').exists()
        fixtures = []
        for i, (label, kind, state, summary, numerical, ref) in enumerate(cases, 1):
            identity = f'20261026T00000{i}-00000121'
            directory = workspace/'outputs/gui'/identity; directory.mkdir(parents=True)
            (directory/'status.json').write_text(json.dumps({'id': identity, 'kind': kind, 'state': state,
                'label': label, 'phase': '処理完了' if state == 'complete' else '処理に失敗しました',
                'created_utc': f'2026-10-26T00:00:0{i}Z', 'completed_steps': 1, 'total_steps': 1}))
            if summary is not None: (directory/'summary.json').write_text(json.dumps(summary))
            fixtures.append((identity, label, summary, numerical, ref, directory))
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        url = f'http://127.0.0.1:{port}'
        # 起動する実serverと同じprocessで導入元を検査し、内部pathは非公開出力だけへ残す。
        script = '''import importlib,json,pathlib,sys,sysconfig,uvicorn
names=['vsora_ui.server','vsora_ui.image_assessment','vsora_ui.worker','vsora_ui.jobs','vsora_imaging.assessment','vsora_imaging.experiment','vsora_imaging.rml','vsora_simulator','vsora_correlator','vsora_formats','vsora_observation']
root=pathlib.Path(sys.argv[1]); mode=sys.argv[2]; modules={n:str(pathlib.Path(importlib.import_module(n).__file__).resolve()) for n in names}
if mode=='installed':
 prefix=pathlib.Path(sysconfig.get_path('purelib')); assert all(pathlib.Path(p).is_relative_to(prefix) for p in modules.values())
else:
 assert all(pathlib.Path(p).is_relative_to(root) for p in modules.values())
pathlib.Path(sys.argv[4]).write_text(json.dumps(modules,indent=2))
from vsora_ui.server import create_app
uvicorn.run(create_app(pathlib.Path.cwd()),host='127.0.0.1',port=int(sys.argv[3]),log_level='warning')
'''
        log = (out/'server.log').open('w')
        server = subprocess.Popen([sys.executable, '-c', script, str(root), mode, str(port), str(out/'module-paths.json')],
                                  cwd=workspace, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            until = time.monotonic()+30
            while time.monotonic() < until:
                if server.poll() is not None: raise AssertionError('GUI startup failed; see server.log')
                try:
                    if httpx.get(url+'/api/environment', timeout=1).status_code == 200: break
                except httpx.HTTPError: pass
                time.sleep(.1)
            else: raise AssertionError('GUI startup timeout')
            environment = httpx.get(url+'/api/environment').json()
            assert not environment['checkout_validation_available']
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
                errors = []; requests = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('request', lambda request: requests.append(request.url))
                page.goto(url); page.evaluate('document.fonts.ready')
                assert page.evaluate('document.fonts.check("14px \'VSoRA Japanese\'")')
                # 期待値は新GUI helperを使わず既存109の公開APIから別processで作る。
                expected_script = '''import json,sys
from vsora_imaging.assessment import assess_rml_result
x=json.load(sys.stdin);print(json.dumps(assess_rml_result(x['rml'],processing_state=x['processing'],reference_metrics=x['metrics'])))
'''

                def check_record(identity, summary, numerical, ref, directory, filename):
                    panel = page.locator('#image-assessment-panel'); panel.wait_for()
                    detail = httpx.get(url+'/api/jobs/'+identity).json(); info = detail['image_assessment']
                    raw = None if summary is None else (directory/'summary.json').read_bytes()
                    assert info['source_summary_sha256'] == (None if raw is None else hashlib.sha256(raw).hexdigest())
                    text = panel.inner_text()
                    if numerical is None:
                        assert info['state'] == 'invalid_record' and '記録を確認できません' in text
                    else:
                        payload = {'rml': None if summary is None else summary['rml'],
                            'processing': detail['state'], 'metrics': summary['metrics'] if ref == 'evaluated' else None}
                        result = subprocess.run([sys.executable, '-c', expected_script], input=json.dumps(payload),
                                                capture_output=True, text=True, check=True, cwd=workspace, env=env)
                        assert info['assessment'] == json.loads(result.stdout)
                        a = info['assessment']; assert a['numerical']['state'] == numerical
                        assert a['reference_fidelity']['state'] == ref
                        processing = {'complete': '処理完了', 'failed': '失敗'}[detail['state']]
                        selected = {'converged': '収束', 'not_converged': '未収束', 'not_run': '未実行'}[numerical]
                        values = panel.locator('.metric strong').all_text_contents()
                        # JS Number.toPrecision(4)を独立に評価し、表示文字列を全三カード照合する。
                        reference = '参照なし・未評価' if ref != 'evaluated' else 'NRMSE '+page.evaluate('(x)=>x.toPrecision(4)', a['reference_fidelity']['registered_nrmse'])
                        assert values == [processing, selected, reference], values
                        if a['image_computed']:
                            counts = a['independent_constraints']
                            assert f"{counts['phase']} / {counts['logamp']}" in text
                            if 'closure_chisq_per_measurement' in summary['rml']:
                                expected = page.evaluate('(x)=>x.toFixed(3)', summary['rml']['closure_chisq_per_measurement'])
                                assert expected in page.locator('#job-detail').inner_text()
                        else: assert '最終RML画像の計算結果がありません' in text
                        if info['reference_note'] == 'legacy_reference_record': assert '旧形式の参照値' in text
                    with page.expect_download() as event: panel.locator('.image-assessment-download').click()
                    event.value.save_as(out/filename)
                    assert json.loads((out/filename).read_text()) == info
                    if raw is not None: assert (directory/'summary.json').read_bytes() == raw
                    assert not info.get('assessment', {}).get('actual_observation_success_certified', False) if info['assessment'] else True
                    return info

                page.get_by_role('button', name='実行履歴', exact=True).click(); checked = []
                for identity, label, summary, numerical, ref, directory in fixtures:
                    page.locator('#job-list button').filter(has=page.get_by_text(label, exact=True)).click()
                    page.wait_for_function('(id)=>document.querySelector("#job-detail .run-id")?.textContent===id', arg=identity)
                    info = check_record(identity, summary, numerical, ref, directory, identity+'.json')
                    checked.append({'label': label, 'assessment': info})
                # 既存RMLフォームから実workerを起動する。参照図は実workerが新たに生成する。
                page.get_by_role('button', name='Closure＋RML', exact=True).click()
                form = page.locator('#rml-form')
                form.locator('details > summary').click()
                form.locator('select[name=model]').select_option('double')
                form.locator('select[name=stations]').select_option('4')
                for name, value in [('snapshots', '8'), ('duration_s', '600'), ('starts', '1'), ('max_iterations', '100')]:
                    form.locator(f'input[name={name}]').fill(value)
                page.get_by_role('button', name='Closure＋RMLで模擬画像を復元', exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了', exact=True).wait_for(timeout=90000)
                identity = page.locator('#job-detail .run-id').inner_text()
                detail = httpx.get(url+'/api/jobs/'+identity).json(); summary = detail['summary']
                numerical = 'converged' if summary['rml']['runs'][summary['rml']['selected_start']]['optimizer_success'] else 'not_converged'
                worker = check_record(identity, summary, numerical, 'evaluated', workspace/'outputs/gui'/identity, 'actual-worker-assessment.json')
                page.wait_for_function('Array.from(document.querySelectorAll("#job-detail img")).length>0 && Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                page.set_viewport_size({'width': 390, 'height': 1000})
                assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
                page.locator('#image-assessment-panel').screenshot(path=str(out/'assessment-panel.png'))
                page.screenshot(path=str(out/'mobile.png'), full_page=True)
                # 画像判定を付けない既存CLEAN経路も、フォームと画像を実行して回帰確認する。
                page.set_viewport_size({'width': 1440, 'height': 1000})
                page.get_by_role('button', name='模擬観測', exact=True).click()
                form = page.locator('#simulation-form'); form.locator('select[name=stations]').select_option('4')
                form.locator('input[name=duration_s]').fill('600'); form.locator('input[name=integration_s]').fill('60')
                page.get_by_role('button', name='模擬観測して画像化', exact=True).click()
                page.locator('#job-detail .phase-line').get_by_text('処理完了', exact=True).wait_for(timeout=60000)
                identity = page.locator('#job-detail .run-id').inner_text(); clean = httpx.get(url+'/api/jobs/'+identity).json()
                assert 'image_assessment' not in clean and abs(clean['summary']['imaging']['image_peak_jy']-1000) < 1e-6
                assert page.locator('#image-assessment-panel').count() == 0
                page.wait_for_function('Array.from(document.querySelectorAll("#job-detail img")).length>=2 && Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
                page.set_viewport_size({'width': 390, 'height': 1000}); assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
                assert not errors, errors
                external = [x for x in requests if not x.startswith(url+'/')]
                assert not external, external
                report = {'state': 'complete', 'mode': mode, 'browser': browser.version,
                    'fixture_count': len(checked), 'fixtures': checked, 'all_displayed_cards_counts_and_chisq_checked': True,
                    'actual_rml_worker': worker, 'actual_clean_worker_complete': True, 'clean_peak_jy_per_beam': clean['summary']['imaging']['image_peak_jy'],
                    'all_seven_actual_json_downloads_equal_api': True, 'all_original_summaries_unchanged': True,
                    'all_assessments_equal_independent_existing_api': True, 'no_repository_runner_in_workspace': True,
                    'checked_project_module_prefixes': len(json.loads((out/'module-paths.json').read_text())),
                    'japanese_font_390px': True, 'mobile_horizontal_overflow': False, 'javascript_errors': errors, 'external_requests': len(external),
                    'scope': 'Headless Chromium on WSL; Windows browser and desktop WSLg not directly observed'}
                (out/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
                browser.close(); print(json.dumps({k: v for k, v in report.items() if k not in ('fixtures', 'actual_rml_worker')}, ensure_ascii=False))
        finally:
            server.terminate()
            try: server.wait(timeout=20)
            except subprocess.TimeoutExpired: server.kill(); server.wait()
            log.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='日本語RML判定GUIをsource/installedで実ブラウザ照合')
    parser.add_argument('--repository', required=True); parser.add_argument('--output', required=True)
    parser.add_argument('--mode', choices=('source', 'installed'), required=True)
    args = parser.parse_args(); run(args.repository, args.output, args.mode)
