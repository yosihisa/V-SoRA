"""実RML記録の収束・参照・不正値を、表示用評価で混同しない。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient
from vsora_ui.image_assessment import describe_image_job
from vsora_ui.server import create_app
from vsora_ui.jobs import write_json

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'validation/runs/stage119/reference.json').is_file())
CASES=json.loads((ROOT/'validation/runs/stage119/reference.json').read_text())['cases']


def summary(pixels=8):
    case=next(r for r in CASES if r['pixels']==pixels and r['branch']=='estimated_rate')
    return deepcopy({'rml':case['science']['rml_summary'],'metrics':case['science']['reference_metrics']})


@pytest.mark.parametrize('kind',['rml','analysis','sequence','synthesis'])
def test_real_converged_reference_record(kind):
    data=summary();before=deepcopy(data);result=describe_image_job(kind,'complete',data)
    assert result['state']=='available' and result['assessment']['numerical']['state']=='converged'
    assert result['assessment']['reference_fidelity']['registered_nrmse']==data['metrics']['registered_nrmse']
    assert not result['assessment']['actual_observation_success_certified'] and data==before


def test_real_nonconvergence_is_preserved():
    result=describe_image_job('analysis','complete',summary(32))
    assert result['assessment']['numerical']['state']=='not_converged'
    assert result['assessment']['processing_state']=='complete'


@pytest.mark.parametrize('state',['failed','cancelled','interrupted','queued','running'])
def test_missing_image_never_means_converged(state):
    result=describe_image_job('analysis',state,None)
    assert result['job_state']==state and result['assessment']['numerical']['state']=='not_run'
    assert result['assessment']['reference_fidelity']['registered_nrmse'] is None
    assert 'processing_not_complete' in result['assessment']['recorded_issues']


def test_no_reference_is_not_zero_error():
    data=summary();data.pop('metrics');result=describe_image_job('analysis','complete',data)
    assert result['assessment']['reference_fidelity']['state']=='not_evaluated'
    assert result['reference_note']=='not_provided'


def test_legacy_reference_keeps_valid_optimizer_but_not_current_metric():
    data=summary();data['metrics']['comparison_version']=1
    result=describe_image_job('rml','complete',data)
    assert result['assessment']['numerical']['state']=='converged'
    assert result['assessment']['reference_fidelity']['state']=='not_evaluated'
    assert result['reference_note']=='legacy_reference_record'


def test_invalid_reference_does_not_hide_convergence_record():
    data=summary();data['metrics']['registered_nrmse']=-1
    result=describe_image_job('rml','complete',data)
    assert result['assessment']['numerical']['state']=='converged'
    assert result['reference_note']=='invalid_reference_record'


@pytest.mark.parametrize('selected',[True,999,-1])
def test_bad_optimizer_record_is_invalid_without_private_exception(selected):
    data=summary();data['rml']['selected_start']=selected;data['private_path']='/private/not-public'
    result=describe_image_job('analysis','complete',data)
    assert result['state']=='invalid_record' and result['assessment'] is None
    assert '/private/' not in json.dumps(result)


def test_non_object_summary_is_invalid():
    assert describe_image_job('rml','complete',[])['state']=='invalid_record'


def test_inconsistent_completion_is_invalid():
    data=summary();data['state']='incomplete'
    assert describe_image_job('analysis','complete',data)['reason_code']=='inconsistent_completion_record'


def test_unknown_state_is_invalid():
    assert describe_image_job('rml','unknown',summary())['state']=='invalid_record'


def test_other_job_does_not_acquire_image_quality():
    assert describe_image_job('validation','complete',{'rml':summary()['rml']}) is None


def seed_job(workspace,kind='rml'):
    root=workspace/'outputs/gui/20261026T000000-abcde121';root.mkdir(parents=True)
    write_json(root/'status.json',{'id':root.name,'kind':kind,'state':'complete','label':'画像結果','phase':'処理完了','created_utc':'2026-10-26T00:00:00Z','completed_steps':1,'total_steps':1})
    write_json(root/'summary.json',summary());return root


def test_detail_download_exact_body_digest_and_original_bytes(tmp_path):
    root=seed_job(tmp_path);before=(root/'summary.json').read_bytes()
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as client:
        detail=client.get('/api/jobs/'+root.name).json();download=client.get('/api/jobs/'+root.name+'/image-assessment')
        assert download.status_code==200 and download.json()==detail['image_assessment']
        assert 'attachment;' in download.headers['content-disposition']
        assert detail['image_assessment']['source_summary_sha256']==hashlib.sha256(before).hexdigest()
        assert (root/'summary.json').read_bytes()==before
        assert client.get('/api/jobs/not-an-id/image-assessment').status_code==404


def test_non_image_job_download_is_unavailable(tmp_path):
    root=seed_job(tmp_path,'validation')
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as client:
        assert 'image_assessment' not in client.get('/api/jobs/'+root.name).json()
        assert client.get('/api/jobs/'+root.name+'/image-assessment').status_code==404
