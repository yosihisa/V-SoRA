"""Installed browser checks for stored raw values and closed input identity."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from itertools import combinations

import httpx
import numpy as np
from playwright.sync_api import sync_playwright
from vsora_correlator.bispectrum_accumulator import BispectrumAccumulator
from vsora_correlator.bispectrum_inspect import inspect_bispectrum_cell
from vsora_formats.bispectrum import load_bispectrum, save_bispectrum
from vsora_formats.spectral import save_spectral

def fixture_pair(path, blocks=7):
    rng = np.random.default_rng(67)
    x = rng.normal(size=(max(blocks, 1), 4, 4)) + 1j * rng.normal(size=(max(blocks, 1), 4, 4))
    good = np.full((len(x), 4), blocks > 0, dtype=bool)
    acc = BispectrumAccumulator(4, 4)
    acc.consume(x, good)
    q = acc.finish()
    pairs = np.array(list(combinations(range(4), 2)))
    count = np.array([(good[:, i] & good[:, j]).sum() for i, j in pairs])
    means = np.zeros((4, 6), complex)
    for k, (i, j) in enumerate(pairs):
        if count[k]:
            means[:, k] = (x[:, :, i] * x[:, :, j].conj())[good[:, i] & good[:, j]].mean(axis=0)
    times = np.array([.01, .02])
    frequencies = 1.42e9 + np.arange(4, dtype=float)
    weights = np.broadcast_to(count > 0, (2, 4, 6)).astype(float).copy()
    weights[:, 0] = 0
    source = path / 'source.npz'
    raw = path / 'raw.npz'
    save_spectral(source, {'visibilities': np.stack([means] * 2), 'weights': weights,
        'pairs': pairs, 'times_s': times, 'frequencies_hz': frequencies,
        'uvw_lambda': np.zeros((2, 4, 6, 3)), 'valid_fft_count': np.stack([count] * 2)},
        {'visibility_unit': 'ADC^2', 'time_origin_utc': '2026-10-05T00:00:00Z',
         'config': {'stations': [{'id': 'A' + str(i)} for i in range(4)]},
         'fft_length': 4, 'fft_sample_rate_hz': 1024.})
    usable = np.broadcast_to(q['common_sample_count'] >= 3, (2, 4, 4)).copy()
    usable[:, 0] = False
    data = {'triangles': q['triangles'], 'times_s': times, 'frequencies_hz': frequencies,
        'common_fft_count': np.stack([q['common_sample_count']] * 2), 'nominal_fft_count': np.full(2, len(x)),
        'edge_sums': np.stack([q['edge_sums']] * 2), 'paired_edge_sums': np.stack([q['paired_edge_sums']] * 2),
        'triple_edge_sum': np.stack([q['triple_edge_sum']] * 2), 'channel_triangle_usable': usable}
    save_bispectrum(raw, data, {'station_ids': ['A' + str(i) for i in range(4)],
        'time_origin_utc': '2026-10-05T00:00:00Z', 'voltage_unit': 'ADC',
        'fft_length': 4, 'sample_rate_hz': 1024., 'visibility_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'processing_notes': ['Synthetic independent spectra, stored-value GUI transport only.']})
    return raw, source


def run(input, source_visibility, output, port=8782, source_checkout=False):
    from vsora_ui import raw_bispectrum, models, worker
    from vsora_correlator import bispectrum_inspect
    checkout = Path(__file__).resolve().parents[1]
    module_root = checkout if source_checkout else Path(sys.prefix)
    assert all(Path(m.__file__).is_relative_to(module_root) for m in (raw_bispectrum, models, worker, bispectrum_inspect))
    raw, source = Path(input).resolve(), Path(source_visibility).resolve()
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    if source_checkout:
        roots = [checkout, *sorted(checkout.glob('apps/*/src')), *sorted(checkout.glob('packages/*/src'))]
        env['PYTHONPATH'] = os.pathsep.join(map(str, roots))
    url = f'http://127.0.0.1:{port}'
    cases = []
    with tempfile.TemporaryDirectory(prefix='vsora-raw-inspection-ui-') as folder:
        workspace = Path(folder)
        shutil.copyfile(raw, workspace / 'raw.npz')
        shutil.copyfile(source, workspace / 'source.npz')
        (workspace / 'wrong.npz').write_bytes(source.read_bytes() + b'different')
        for blocks in (0, 1, 2):
            small = workspace / f'm{blocks}'
            small.mkdir()
            fixture_pair(small, blocks)
        # Closed history fixtures exercise selection, without claiming new VDIF processing.
        for index, kind in enumerate(('analysis', 'sequence')):
            job_id = f'20261005T00000{index}-0000000{index}'
            history = workspace / 'outputs/gui' / job_id
            relative = 'analysis/correlation' if kind == 'analysis' else 'sequence/windows/window-0000/analysis/correlation'
            archive = history / relative
            archive.mkdir(parents=True)
            shutil.copyfile(raw, archive / 'raw-bispectrum.npz')
            shutil.copyfile(source, archive / 'shard-00000.npz')
            (history / 'status.json').write_text(json.dumps({'id': job_id, 'label': '保存統計の履歴fixture',
                'kind': kind, 'state': 'complete', 'phase': '処理完了', 'created_utc': f'2026-10-05T00:00:0{index}Z',
                'completed_steps': 5, 'total_steps': 5}))
        log = (out / 'server.log').open('w')
        server = subprocess.Popen([str(Path(sys.prefix) / 'bin/vsora-ui'), '--workspace', folder, '--port', str(port)],
            cwd=folder, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                try:
                    if httpx.get(url + '/api/environment', timeout=1).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(.1)
            else:
                raise AssertionError('GUI not ready')
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                errors, requests = [], []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('request', lambda r: requests.append(r.url))
                page.goto(url)
                for name, ti, fi in [('frozen', 0, 10), ('masked', 1, 16), ('m0', 0, 1), ('m1', 0, 1), ('m2', 0, 1)]:
                    page.get_by_role('button', name='保存三次統計', exact=True).click()
                    form = page.locator('#raw-form')
                    if name == 'frozen':
                        page.wait_for_function('() => document.querySelector("#raw-input-history").options.length===2')
                        values = page.locator('#raw-input-history option').evaluate_all('(opts) => opts.map(o=>o.value)')
                        assert any('window-0000' in v for v in values) and any('/analysis/correlation/' in v for v in values)
                        page.get_by_role('button', name='選んだ二つのファイルを入力に使う', exact=True).click()
                        assert 'outputs/gui/' in form.locator('input[name=input]').input_value()
                    else:
                        prefix = name + '/' if name.startswith('m') and name != 'masked' else ''
                        form.locator('input[name=input]').fill(prefix + 'raw.npz')
                        form.locator('input[name=source_visibility]').fill(prefix + 'source.npz')
                    assert form.locator('button[type=submit]').is_disabled()
                    page.get_by_role('button', name='二つの入力を照合し時刻・周波数を読む', exact=True).click()
                    page.wait_for_function('() => !document.querySelector("#raw-form button[type=submit]").disabled')
                    if name == 'frozen':
                        form.locator('input[name=source_visibility]').dispatch_event('input')
                        assert form.locator('button[type=submit]').is_disabled()
                        assert form.locator('select[name=channel_index]').is_disabled()
                        page.get_by_role('button', name='二つの入力を照合し時刻・周波数を読む', exact=True).click()
                        page.wait_for_function('() => !document.querySelector("#raw-form button[type=submit]").disabled')
                    form.locator('select[name=time_index]').select_option(str(ti))
                    form.locator('select[name=channel_index]').select_option(str(fi))
                    selected_raw = workspace / form.locator('input[name=input]').input_value()
                    selected_source = workspace / form.locator('input[name=source_visibility]').input_value()
                    data = load_bispectrum(selected_raw, selected_source)
                    expected = inspect_bispectrum_cell(data, ti, fi)
                    expected.update(source_visibility_verified=True, raw_bispectrum_sha256=hashlib.sha256(selected_raw.read_bytes()).hexdigest(), source_visibility_sha256=hashlib.sha256(selected_source.read_bytes()).hexdigest())
                    if name == 'frozen':
                        page.screenshot(path=str(out / 'input.png'), full_page=True)
                    page.get_by_role('button', name='選んだ三次統計の値を確認', exact=True).click()
                    page.locator('#job-detail .phase-line').get_by_text('処理完了', exact=True).wait_for(timeout=30000)
                    job_id = httpx.get(url + '/api/jobs').json()[0]['id']
                    job = httpx.get(url + '/api/jobs/' + job_id).json()
                    assert job['state'] == 'complete' and job['summary'] == expected
                    rows = page.locator('#raw-inspection-table tr').all()
                    assert len(rows) == len(expected['triangles']) + 1
                    state_labels = {'usable_raw_value': '形式上利用可', 'masked_raw_value': '品質マスクで利用不可', 'insufficient_samples': '未計算（共通FFT数が3未満）'}
                    for displayed, actual in zip(rows[1:], expected['triangles']):
                        text = displayed.inner_text()
                        assert ' / '.join(actual['station_ids']) in text
                        assert f"{actual['common_fft_count']:,}" in text and state_labels[actual['state']] in text
                        for key in ('distinct_sample_bispectrum_real', 'distinct_sample_bispectrum_imag', 'ordinary_common_sample_product_real', 'ordinary_common_sample_product_imag'):
                            value = actual[key]
                            if value is None:
                                rendered = '未計算'
                            else:
                                mantissa, exponent = format(value, '.6e').split('e')
                                rendered = mantissa + 'e' + format(int(exponent), '+d')
                            assert rendered in text
                    assert '現在のRMLへの適用はありません' in page.locator('#job-detail').inner_text()
                    assert httpx.get(url + f'/api/jobs/{job_id}/artifacts/bispectrum-inspection.json').json() == expected
                    cases.append({'fixture': name, 'time_index': ti, 'channel_index': fi, 'frequency_hz': expected['frequency_hz'],
                        'raw_bispectrum_sha256': expected['raw_bispectrum_sha256'],
                        'source_visibility_sha256': expected['source_visibility_sha256'],
                        'common_fft_count': [r['common_fft_count'] for r in expected['triangles']],
                        'states': [r['state'] for r in expected['triangles']], 'json_matches_library': True})
                    page.screenshot(path=str(out / (name + '-result.png')), full_page=True)
                page.set_viewport_size({'width': 390, 'height': 844})
                result_overflow = page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                page.screenshot(path=str(out / 'mobile-result.png'), full_page=True)
                page.get_by_role('button', name='保存三次統計', exact=True).click()
                form = page.locator('#raw-form')
                form.locator('input[name=input]').fill('raw.npz')
                form.locator('input[name=source_visibility]').fill('wrong.npz')
                with page.expect_response('**/api/bispectrum-input') as checked:
                    page.get_by_role('button', name='二つの入力を照合し時刻・周波数を読む', exact=True).click()
                assert checked.value.status == 400
                page.get_by_role('alert').get_by_text('三次統計と元相関の照合に失敗しました。対応する保存済みNPZを確認してください。', exact=True).wait_for(timeout=10000)
                assert form.locator('button[type=submit]').is_disabled()
                form.locator('input[name=input]').fill('missing.npz')
                with page.expect_response('**/api/bispectrum-input') as checked:
                    page.get_by_role('button', name='二つの入力を照合し時刻・周波数を読む', exact=True).click()
                assert checked.value.status == 400
                page.get_by_role('alert').get_by_text('三次統計と元相関の照合に失敗しました。対応する保存済みNPZを確認してください。', exact=True).wait_for(timeout=10000)
                assert form.locator('button[type=submit]').is_disabled()
                mobile_overflow = page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth')
                page.screenshot(path=str(out / 'mobile-input.png'), full_page=True)
                font = page.evaluate('document.fonts.check("14px \'VSoRA Japanese\'")')
                external = [r for r in requests if not r.startswith(url + '/')]
                assert not errors and not external and not mobile_overflow and not result_overflow and font
                result = {'state': 'complete', 'installed_gui_imports': not source_checkout,
                    'source_checkout': source_checkout, 'outside_checkout': not source_checkout,
                    'pythonpath_removed': not source_checkout,
                    'browser': browser.version, 'cases': cases, 'history_analysis_sequence_pair_selection': True,
                    'history_is_seeded_closed_fixture': True, 'downloaded_json_identical': True, 'input_edit_invalidates_selection': True,
                    'missing_and_mismatched_source_errors': True, 'unavailable_values_not_numeric_zero': True,
                    'japanese_font_loaded': font, 'javascript_errors': errors, 'external_requests': len(external),
                    'mobile_input_horizontal_overflow': mobile_overflow, 'mobile_result_horizontal_overflow': result_overflow,
                    'noise_covariance_estimated': False, 'production_rml_noise_model_changed': False, 'actual_hardware_data': False,
                    'scope': 'Stored stage064 VDIF output and independent synthetic spectra M0/1/2; UI transport and identity only. No uncertainty, phase confidence, real FFT independence or image validation.'}
                browser.close()
                (out / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
                return result
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
            log.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('input', 'source-visibility', 'output'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--port', type=int, default=8782)
    p.add_argument('--source-checkout', action='store_true')
    print(json.dumps(run(**vars(p.parse_args())), indent=2))
