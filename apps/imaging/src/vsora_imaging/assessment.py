"""画像処理の完了・数値収束・参照画像との差を独立に記録する。"""
import argparse
import json
import math
from pathlib import Path


def _number(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name}: finite number required')
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f'{name}: invalid range')
    return float(value)


def _count(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError('nonnegative integer closure count required')
    return value


def assess_rml_result(rml, *, processing_state='complete', reference_metrics=None,
                      max_registered_nrmse=None):
    """真値は評価にだけ用いる。収束を科学的成功や低SNR適用性へ換算しない。"""
    if processing_state not in ('complete', 'incomplete', 'failed', 'cancelled', 'running'):
        raise ValueError('unknown processing state')
    limit = None if max_registered_nrmse is None else _number(max_registered_nrmse, 'NRMSE limit')
    issues = [] if processing_state == 'complete' else ['processing_not_complete']
    numerical = {'state': 'not_run', 'selected_start': None, 'optimizer_success': None}
    constraints = {'phase': None, 'logamp': None, 'total': None}
    if rml is None:
        issues.append('image_not_run')
    else:
        if not isinstance(rml, dict):
            raise ValueError('RML summary object required')
        counts = rml.get('independent_closure_counts')
        if not isinstance(counts, dict) or set(counts) != {'phase', 'logamp'}:
            raise ValueError('phase/logamp closure counts required')
        constraints = {name: _count(counts[name]) for name in ('phase', 'logamp')}
        constraints['total'] = _count(rml.get('independent_closure_count'))
        if constraints['total'] != constraints['phase'] + constraints['logamp'] or not constraints['total']:
            raise ValueError('inconsistent or empty RML constraints')
        runs = rml.get('runs'); selected = rml.get('selected_start')
        if (not isinstance(runs, list) or not runs or isinstance(selected, bool)
                or not isinstance(selected, int) or not 0 <= selected < len(runs)):
            raise ValueError('valid selected optimizer run required')
        for run in runs:
            if not isinstance(run, dict) or type(run.get('optimizer_success')) is not bool:
                raise ValueError('optimizer_success bool required for every run')
        success = runs[selected]['optimizer_success']
        numerical = {'state': 'converged' if success else 'not_converged',
                     'selected_start': selected, 'optimizer_success': success}
        if not success: issues.append('optimizer_not_converged')
        for name in ('phase', 'logamp'):
            if not constraints[name]: issues.append(f'no_{name}_constraints')
    reference = {'state': 'not_evaluated', 'registered_nrmse': None,
                 'declared_max_registered_nrmse': limit, 'within_declared_limit': None}
    if reference_metrics is not None:
        if rml is None: raise ValueError('reference comparison requires an image')
        if not isinstance(reference_metrics, dict) or type(reference_metrics.get('comparison_version')) is not int or reference_metrics['comparison_version'] != 2:
            raise ValueError('full-support comparison version 2 required')
        error = _number(reference_metrics.get('registered_nrmse'), 'registered NRMSE')
        beam = _number(reference_metrics.get('common_beam_arcsec'), 'common beam', positive=True)
        retained = _number(reference_metrics.get('registered_flux_retained_fraction'), 'retained flux')
        boundary = reference_metrics.get('registration_boundary_reached')
        if type(boundary) is not bool: raise ValueError('registration boundary bool required')
        within = None if limit is None else error <= limit
        reference = {'state': 'evaluated', 'registered_nrmse': error,
                     'comparison_version': 2, 'common_beam_arcsec': beam,
                     'registered_flux_retained_fraction': retained,
                     'registration_boundary_reached': boundary,
                     'declared_max_registered_nrmse': limit, 'within_declared_limit': within}
        if within is False: issues.append('reference_error_exceeds_declared_limit')
        if boundary: issues.append('registration_boundary_reached')
        if abs(retained - 1.) > 1e-10: issues.append('comparison_flux_not_preserved')
    return {'schema_version': 1, 'type': 'image_path_assessment',
            'processing_state': processing_state, 'image_computed': rml is not None,
            'numerical': numerical, 'independent_constraints': constraints,
            'reference_fidelity': reference, 'recorded_issues': issues,
            'actual_observation_success_certified': False,
            'low_snr_likelihood_validated': False,
            'interpretation': 'Diagnostic record only. Optimizer convergence and reference-image similarity are separate; missing amplitude constraints do not prove imaging impossible. No absolute flux or astrometry certified.'}


def assess_pipeline_result(summary, **settings):
    """partial記録を含む既存pipeline JSONを、推定し直さず評価する。"""
    if not isinstance(summary, dict) or 'state' not in summary:
        raise ValueError('pipeline summary with explicit state required')
    steps = summary.get('completed_steps')
    if not isinstance(steps, list) or any(not isinstance(step, str) for step in steps):
        raise ValueError('completed_steps list required')
    if len(set(steps)) != len(steps): raise ValueError('duplicate completed steps')
    result = assess_rml_result(summary.get('rml'), processing_state=summary['state'], **settings)
    # パスや生の例外文は公開用評価へ転記しない。
    result['completed_steps'] = list(steps)
    closure = summary.get('closures')
    result['extracted_closures'] = None
    if closure is not None:
        if not isinstance(closure, dict): raise ValueError('closure summary object required')
        result['extracted_closures'] = {name: _count(closure.get(name)) for name in ('phase_valid', 'logamp_valid')}
    return result


def main():
    p = argparse.ArgumentParser(description='画像処理の完了・収束・真値比較を分離して記録')
    p.add_argument('--input', required=True); p.add_argument('--output', required=True)
    p.add_argument('--kind', choices=('pipeline', 'rml'), default='pipeline')
    p.add_argument('--reference-metrics'); p.add_argument('--max-registered-nrmse', type=float)
    args = p.parse_args()
    reference = None if args.reference_metrics is None else json.loads(Path(args.reference_metrics).read_text())
    function = assess_pipeline_result if args.kind == 'pipeline' else assess_rml_result
    result = function(json.loads(Path(args.input).read_text()), reference_metrics=reference,
                      max_registered_nrmse=args.max_registered_nrmse)
    with Path(args.output).open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps(result, allow_nan=False))


if __name__ == '__main__': main()
