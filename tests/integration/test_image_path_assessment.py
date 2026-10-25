"""固定画像経路ベンチが未知の事故を科学的失敗へ置換しないこと。"""
import pytest
from workflows.image_path_acceptance_validation import scientific_failure_code, EXPECTED_SCIENTIFIC_FAILURES


@pytest.mark.parametrize('message,code', list(EXPECTED_SCIENTIFIC_FAILURES.items()))
def test_documented_failures_only(message, code):
    assert scientific_failure_code(ValueError(message)) == code


@pytest.mark.parametrize('exc', [ValueError('invalid configuration'), TypeError('no high SNR independent closure measurements'),
    RuntimeError('detected rate graph is disconnected; use a longer/stronger pilot or fewer stations'),
    ValueError('no high SNR independent closure measurements extra')])
def test_unknown_failure_propagates(exc):
    with pytest.raises(type(exc)) as caught: scientific_failure_code(exc)
    assert caught.value is exc
