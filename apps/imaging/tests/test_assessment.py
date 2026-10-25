"""処理完了・最適化収束・参照適合の混同を防ぐ契約試験。"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import pytest
from vsora_imaging.assessment import assess_rml_result, assess_pipeline_result


def rml(success=True, phase=9, logamp=8):
    return {'selected_start': 1, 'runs': [{'optimizer_success': not success}, {'optimizer_success': success}],
            'independent_closure_counts': {'phase': phase, 'logamp': logamp},
            'independent_closure_count': phase + logamp}


def metrics(error=.2):
    return {'comparison_version': 2, 'registered_nrmse': error, 'common_beam_arcsec': 110.,
            'registered_flux_retained_fraction': 1., 'registration_boundary_reached': False}


@pytest.mark.parametrize('state', ['complete', 'incomplete', 'failed', 'cancelled', 'running'])
@pytest.mark.parametrize('success', [True, False])
def test_processing_and_convergence_are_independent(state, success):
    summary = {'state': state, 'completed_steps': ['relative_rml'], 'rml': rml(success)}
    before = deepcopy(summary)
    result = assess_pipeline_result(summary, reference_metrics=metrics(), max_registered_nrmse=.1)
    assert summary == before
    assert result['processing_state'] == state
    assert result['numerical']['optimizer_success'] == success
    assert result['reference_fidelity']['within_declared_limit'] is False
    assert not result['actual_observation_success_certified']
    assert not result['low_snr_likelihood_validated']
    assert ('processing_not_complete' in result['recorded_issues']) == (state != 'complete')


@pytest.mark.parametrize('success,error,within', [(True, .2, False), (False, .02, True), (True, .1, True)])
def test_reference_does_not_override_optimizer(success, error, within):
    result = assess_rml_result(rml(success), reference_metrics=metrics(error), max_registered_nrmse=.1)
    assert result['numerical']['optimizer_success'] == success
    assert result['reference_fidelity']['within_declared_limit'] is within


@pytest.mark.parametrize('phase,logamp,issue', [(9, 0, 'no_logamp_constraints'), (0, 8, 'no_phase_constraints')])
def test_one_constraint_type_is_diagnostic(phase, logamp, issue):
    result = assess_rml_result(rml(phase=phase, logamp=logamp))
    assert issue in result['recorded_issues']
    assert 'impossible' not in result['recorded_issues']


def test_missing_image_and_missing_truth_are_not_passes():
    result = assess_pipeline_result({'state': 'incomplete', 'completed_steps': ['aligned_pilot']}, max_registered_nrmse=.1)
    assert not result['image_computed']
    assert result['numerical']['state'] == 'not_run'
    assert result['reference_fidelity']['within_declared_limit'] is None
    assert result['independent_constraints']['total'] is None
    with pytest.raises(ValueError): assess_rml_result(None, reference_metrics=metrics())
    assert assess_rml_result(rml(), reference_metrics=metrics())['reference_fidelity']['within_declared_limit'] is None


def test_registration_caveats_survive_good_error():
    m = metrics(.001); m.update(registered_flux_retained_fraction=.9, registration_boundary_reached=True)
    result = assess_rml_result(rml(), reference_metrics=m, max_registered_nrmse=.1)
    assert result['reference_fidelity']['within_declared_limit']
    assert {'registration_boundary_reached', 'comparison_flux_not_preserved'} <= set(result['recorded_issues'])


@pytest.mark.parametrize('field,value', [('selected_start', True), ('selected_start', -1), ('selected_start', 2),
    ('runs', []), ('runs', [{'optimizer_success': 1}, {'optimizer_success': True}]),
    ('independent_closure_count', 18), ('independent_closure_count', True),
    ('independent_closure_counts', {'phase': 9., 'logamp': 8}),
    ('independent_closure_counts', {'phase': -1, 'logamp': 18}),
    ('independent_closure_counts', {'phase': 9, 'logamp': 8, 'extra': 0})])
def test_invalid_optimizer_and_constraints(field, value):
    summary = rml(); summary[field] = value
    with pytest.raises(ValueError): assess_rml_result(summary)


@pytest.mark.parametrize('field,value', [('comparison_version', True), ('comparison_version', 1),
    ('registered_nrmse', float('nan')), ('registered_nrmse', float('inf')), ('registered_nrmse', -1),
    ('common_beam_arcsec', 0), ('registered_flux_retained_fraction', True),
    ('registration_boundary_reached', 0)])
def test_invalid_comparison(field, value):
    m = metrics(); m[field] = value
    with pytest.raises(ValueError): assess_rml_result(rml(), reference_metrics=m)


@pytest.mark.parametrize('limit', [-1, True, float('inf'), float('nan')])
def test_invalid_limit(limit):
    with pytest.raises(ValueError): assess_rml_result(rml(), max_registered_nrmse=limit)


@pytest.mark.parametrize('summary', [{}, {'state': 'other', 'completed_steps': []},
    {'state': 'complete', 'completed_steps': ['same', 'same']},
    {'state': 'complete', 'completed_steps': [], 'rml': {}},
    {'state': 'complete', 'completed_steps': [], 'closures': {'phase_valid': True, 'logamp_valid': 0}}])
def test_malformed_pipeline_rejected(summary):
    with pytest.raises(ValueError): assess_pipeline_result(summary)


def test_extracted_and_independent_counts_remain_distinct():
    result = assess_pipeline_result({'state': 'complete', 'completed_steps': [], 'rml': rml(),
                                    'closures': {'phase_valid': 200, 'logamp_valid': 300}})
    assert result['extracted_closures'] == {'phase_valid': 200, 'logamp_valid': 300}
    assert result['independent_constraints']['total'] == 17


@pytest.mark.parametrize('kind', ['pipeline', 'rml'])
def test_cli_exclusive_output_and_whole_json(tmp_path, kind):
    summary = rml() if kind == 'rml' else {'state': 'complete', 'completed_steps': [], 'rml': rml()}
    source = tmp_path/'input.json'; source.write_text(json.dumps(summary))
    reference = tmp_path/'reference.json'; reference.write_text(json.dumps(metrics()))
    output = tmp_path/'assessment.json'
    # source/導入済みの両全回帰で、その実行環境の同じmoduleを使う。
    root = Path(__file__).resolve().parents[3]
    runner = [str(root/'tools/run.py')] if '/apps/imaging/src/' in __import__('vsora_imaging.assessment', fromlist=['']).__file__ else ['-m']
    command = [sys.executable, *runner, 'vsora_imaging.assessment', '--input', str(source), '--output', str(output),
               '--kind', kind, '--reference-metrics', str(reference), '--max-registered-nrmse', '.1']
    completed = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=True)
    expected = (assess_rml_result if kind == 'rml' else assess_pipeline_result)(summary, reference_metrics=metrics(), max_registered_nrmse=.1)
    assert json.loads(output.read_text()) == json.loads(completed.stdout) == expected
    old = output.read_bytes()
    assert subprocess.run(command, cwd=tmp_path, capture_output=True).returncode != 0
    assert output.read_bytes() == old


def test_invalid_cli_does_not_create_output(tmp_path):
    # API同様、書込み前に入力を検証する。
    source = tmp_path/'invalid.json'; source.write_text('{}')
    output = tmp_path/'out.json'
    import vsora_imaging.assessment as module
    root = Path(__file__).resolve().parents[3]
    runner = [str(root/'tools/run.py')] if '/apps/imaging/src/' in module.__file__ else ['-m']
    result = subprocess.run([sys.executable, *runner, 'vsora_imaging.assessment', '--input', str(source), '--output', str(output)], capture_output=True)
    assert result.returncode != 0 and not output.exists()
