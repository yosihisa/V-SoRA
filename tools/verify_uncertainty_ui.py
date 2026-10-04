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
    if validation not in ('uncertainty', 'covariance', 'closure_noise', 'filtered_noise', 'bispectrum', 'temporal_bispectrum', 'bispectrum_sensitivity', 'bispectrum_moments'):
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
                hardware_markers=[q[k] for k in ('actual_hardware_data','real_hardware_validation_performed') if k in q]
                assert hardware_markers and all(marker is False for marker in hardware_markers)
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
                elif validation=='closure_noise':
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
                elif validation=='filtered_noise':
                    assert q['type']=='filtered_visibility_noise_validation' and q['trials_per_case']==8192 and len(q['cases'])==6
                    assert not q['physical_adc_vdif_processed'] and not q['measured_effective_sample_count']
                    assert not q['production_rml_noise_model_changed']
                    assert '固定フィルターとFFT間の雑音' in text and '実機の独立標本数を測った結果ではありません' in text
                    assert '単一の換算数を仮定しない' in text and '全共分散の差' in text
                    assert page.locator('#job-detail .window-table tr').count()==7
                    for r in q['cases']:
                        assert r['raw_covariance_supplied'] and not r['observed_visibility_selection']
                        assert f"{r['maximum_normalized_covariance_difference']:.6f}" in text
                        assert f"{r['maximum_normalized_iid_counterfactual_difference']:.6f}" in text
                        if r['common_kernel_effective_count'] is not None:assert f"{r['common_kernel_effective_count']:.4f}" in text
                    scientific={'trials_per_case':q['trials_per_case'],'cases':len(q['cases']),
                        'raw_covariance_supplied':True,'measured_effective_sample_count':False,
                        'physical_adc_vdif_processed':False,'production_rml_noise_model_changed':False,
                        'scope':'Known fixed Gaussian raw covariance and fixed station operators. Model-only effective-count calculation/UI, no real receiver spectrum, variable clocks, ADC or image confidence.'}
                elif validation=='bispectrum':
                    assert q['type']=='distinct_sample_bispectrum_validation' and q['trials_per_case']==16384 and len(q['cases'])==5
                    assert not q['physical_adc_vdif_processed'] and not q['production_correlator_statistics_changed']
                    assert not q['production_rml_noise_model_changed'] and not q['observed_sample_selection_used']
                    assert '三基線の積と共通標本の雑音偏り' in text and '既知真値はこの試行数では未分解' in text
                    assert '角度・振幅の不偏性を保証せず' in text and '平均相関・局power・標本数だけから再構成できません' in text
                    assert page.locator('#bispectrum-table tr').count()==6
                    def number(v):return f'{v:.4e}'.replace('e-0','e-').replace('e+0','e+')
                    def complex_text(v):return number(v[0])+(' + ' if v[1]>=0 else ' − ')+number(abs(v[1]))+' i'
                    for c in q['cases']:
                        assert c['all_mean_components_within_6se'] and not c['estimator_generating_truth_used']
                        assert complex_text(c['true_bispectrum']) in text
                        assert complex_text(c['ordinary_analytic_bias']) in text
                        assert complex_text(c['methods']['distinct']['ensemble_mean']) in text
                        assert ' / '.join(number(v) for v in c['methods']['distinct']['mean_standard_error']) in text
                    weak=next(c for c in q['cases'] if c['model']=='weak_unresolved')
                    assert not weak['known_true_mean_above_six_mc_standard_errors']
                    scientific={'trials_per_case':q['trials_per_case'],'cases':len(q['cases']),
                        'estimator_generating_truth_used':False,'weak_true_mean_unresolved':True,
                        'physical_adc_vdif_processed':False,'production_correlator_statistics_changed':False,
                        'production_rml_noise_model_changed':False,
                        'scope':'Fixed iid Gaussian voltage/gain bispectrum means. Known model bias and unresolved weak mean; no unbiased phase, actual independent FFTs, hardware sensitivity or image guarantee.'}
                elif validation=='temporal_bispectrum':
                    assert q['type']=='temporal_bispectrum_validation' and q['trials_per_case']==8192 and len(q['cases'])==5
                    assert not q['physical_adc_vdif_processed'] and not q['actual_temporal_independence_verified']
                    assert not q['production_rml_noise_model_changed'] and not q['physical_raw_filter_convolution_performed']
                    assert '時間相関が三基線の積へ残す偏り' in text
                    assert '観測から未知の共分散や独立標本数を測った結果ではありません' in text
                    assert '実機に一律の間引き間隔を推奨する結果ではありません' in text
                    assert page.locator('#temporal-bispectrum-table tr').count()==6
                    def number(v):return f'{v:.4e}'.replace('e-0','e-').replace('e+0','e+')
                    def complex_text(v):return number(v[0])+(' + ' if v[1]>=0 else ' − ')+number(abs(v[1]))+' i'
                    for c in q['cases']:
                        assert c['all_mean_components_within_6se'] and not c['actual_temporal_independence_verified']
                        assert f"{c['retained_outputs']} / {c['nominal_time_outputs']}出力 / {c['guard_step_outputs']}個おき" in text
                        for name in ('ordinary','distinct'):
                            assert complex_text(c['methods'][name]['known_coloured_model_mean']) in text
                        assert complex_text(c['methods']['distinct']['ensemble_mean']) in text
                        assert ' / '.join(number(v) for v in c['methods']['distinct']['mean_standard_error']) in text
                    long=next(c for c in q['cases'] if c['model']=='long_average')
                    assert long['known_distinct_bias_above_six_mc_se']
                    guarded=next(c for c in q['cases'] if c['model']=='guarded_average')
                    assert guarded['retained_outputs']==15 and guarded['conditional_temporal_covariance_is_identity']
                    reference=next(c for c in q['cases'] if c['model']=='reference_fft')
                    assert not reference['known_distinct_bias_above_six_mc_se']
                    scientific={'trials_per_case':q['trials_per_case'],'cases':len(q['cases']),
                        'known_time_covariance_supplied':True,'actual_temporal_independence_verified':False,
                        'physical_raw_filter_convolution_performed':False,'physical_adc_vdif_processed':False,
                        'long_average_known_bias_resolved_in_model_validation':True,'guarded_average_retained_outputs':15,
                        'reference_fft_known_bias_unresolved':True,'production_rml_noise_model_changed':False,
                        'scope':'Known zero-source independent receiver Gaussian temporal covariance. Model-only residual bias and output thinning, no observed independence or hardware sensitivity recommendation.'}
                elif validation=='bispectrum_moments':
                    assert q['type']=='joint_bispectrum_moments_validation'
                    assert q['trials_per_case']==8192 and len(q['cases'])==5
                    assert not q['physical_adc_vdif_processed'] and not q['actual_temporal_independence_verified']
                    assert not q['production_rml_noise_model_changed'] and not q['gaussian_bispectrum_likelihood_assumed']
                    assert '天体信号と三角形間の誤差相関' in text
                    assert '観測から未知の共分散を推定した結果ではありません' in text
                    assert 'U₃の分布がGaussianであるとは判断できません' in text
                    assert page.locator('#bispectrum-moments-table tr').count()==6
                    assert '三基線積の分散比・実成分間の相関・全共分散の反復比較' in page.locator('#job-detail figcaption').inner_text()
                    assert '画像復元の比較' not in page.locator('#job-detail figcaption').inner_text()
                    for c in q['cases']:
                        assert c['all_means_and_real_covariances_within_6se']
                        assert len(c['real_covariance_model'])==8
                        lo,hi=c['exact_complex_to_null_variance_ratio_range']
                        assert f'{lo:.6f}〜{hi:.6f}' in text
                        for key in ('maximum_absolute_offdiagonal_real_correlation','maximum_normalized_covariance_difference'):
                            assert f'{c[key]:.6f}' in text
                        assert f"M={c['samples']} / {c['trials']:,}試行" in text
                    scientific={'cases':5,'trials_per_case':8192,'all_case_numbers_checked':True,
                        'generating_covariance_supplied':True,'joint_real_covariance_size':8,
                        'gaussian_bispectrum_likelihood_assumed':False,'actual_temporal_independence_verified':False,
                        'physical_adc_vdif_processed':False,'production_rml_noise_model_changed':False,
                        'scope':'Known iid Gaussian voltage U3 moments/UI. No empirical covariance, Gaussian bispectrum likelihood, hardware independence or image confidence.'}
                else:
                    assert q['type']=='bispectrum_sensitivity_validation'
                    assert len(q['null_variance_cases'])==5 and len(q['conditional_point_source_plans'])==32
                    assert not q['nonzero_source_variance_calculated'] and not q['actual_temporal_independence_verified']
                    assert not q['image_reconstructed'] and not q['physical_adc_vdif_processed']
                    assert '三基線積の雑音と短積分の仮定比較' in text
                    assert '目標尺度5は検出確率を意味しません' in text and '実FFTの独立数を測定した値ではありません' in text
                    assert page.locator('#bispectrum-null-table tr').count()==6
                    assert page.locator('#bispectrum-point-table tr').count()==9
                    def number(v):return f'{v:.4e}'.replace('e-0','e-').replace('e+0','e+')
                    for c in q['null_variance_cases']:
                        assert c['means_and_second_moments_within_6se']
                        assert number(c['null_complex_variance']) in text
                        assert f"{c['complex_variance_ratio']:.5f}" in text
                        assert f"{c['complex_variance_ratio_standard_error']:.5f}" in text
                    page.locator('#bispectrum-all-plans summary').click()
                    all_text=page.locator('#bispectrum-all-table').inner_text()
                    assert page.locator('#bispectrum-all-table tr').count()==33
                    for r in q['conditional_point_source_plans']:
                        assert f"M={r['independent_samples_assumed']}" in all_text
                        assert number(r['single_window_null_variance_snr']) in all_text
                        assert f"{r['required_identical_independent_windows']:,}窓" in all_text
                        assert f"{r['conditional_recorded_seconds']:.1f}秒（条件付き）" in all_text
                    page.locator('#bispectrum-all-plans summary').click()
                    scientific={'null_cases':5,'conditional_point_plans':32,'all_plan_numbers_checked':True,
                        'nonzero_source_variance_calculated':False,'actual_temporal_independence_verified':False,
                        'image_reconstructed':False,'physical_adc_vdif_processed':False,
                        'scope':'Exact iid null Gaussian variance and conditional fixed point-source scale. No observed independence, nonzero-source likelihood, Cas A flux prediction, hardware detectability or image guarantee.'}
                page.wait_for_function('() => Array.from(document.querySelectorAll("#job-detail img")).every(x=>x.complete&&x.naturalWidth>0)')
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
    parser.add_argument('--validation',choices=('uncertainty','covariance','closure_noise','filtered_noise','bispectrum','temporal_bispectrum','bispectrum_sensitivity','bispectrum_moments'),default='uncertainty')
    print(json.dumps(run(**vars(parser.parse_args())),indent=2))
