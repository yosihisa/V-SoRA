"""保存済みRML結果の処理・収束・参照差を、画像を推定し直さず区別する。"""
from vsora_imaging.assessment import assess_rml_result


IMAGE_KINDS = {'rml', 'analysis', 'sequence', 'synthesis'}
PROCESSING_STATES = {'queued': 'running', 'running': 'running', 'complete': 'complete',
                     'failed': 'failed', 'cancelled': 'cancelled', 'interrupted': 'incomplete'}


def describe_image_job(kind, job_state, summary, *, summary_sha256=None):
    """生の例外やpathを転記せず、旧参照形式と壊れたRMLを区別する。"""
    if kind not in IMAGE_KINDS:
        return None
    result = {'schema_version': 1, 'type': 'gui_image_assessment', 'job_state': job_state,
              'source_summary_sha256': summary_sha256, 'state': 'invalid_record',
              'reason_code': None, 'assessment': None, 'reference_note': 'not_provided'}
    if job_state not in PROCESSING_STATES:
        return {**result, 'reason_code': 'unknown_processing_state'}
    if summary is not None and not isinstance(summary, dict):
        return {**result, 'reason_code': 'invalid_summary_record'}
    if job_state == 'complete' and isinstance(summary, dict) and summary.get('state', 'complete') != 'complete':
        return {**result, 'reason_code': 'inconsistent_completion_record'}
    rml = (summary or {}).get('rml')
    try:
        assessment = assess_rml_result(rml, processing_state=PROCESSING_STATES[job_state])
    except (ValueError, TypeError):
        return {**result, 'reason_code': 'invalid_rml_record'}
    metrics = (summary or {}).get('metrics')
    note = 'not_provided'
    if isinstance(metrics, dict) and 'registered_nrmse' in metrics:
        if type(metrics.get('comparison_version')) is not int or metrics['comparison_version'] != 2:
            note = 'legacy_reference_record'
        else:
            try:
                assessment = assess_rml_result(rml, processing_state=PROCESSING_STATES[job_state], reference_metrics=metrics)
                note = 'evaluated_full_support_v2'
            except (ValueError, TypeError):
                note = 'invalid_reference_record'
    return {**result, 'state': 'available', 'assessment': assessment, 'reference_note': note}
