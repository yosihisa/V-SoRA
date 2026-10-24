"""GUI dispatch checks use explicit stubs, not full Monte Carlo evidence."""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from vsora_ui import worker
from vsora_ui.models import ValidationRequest
from vsora_ui.jobs import LABELS,write_json
from vsora_ui.server import create_app

def job(tmp_path):
 p=tmp_path/'job';p.mkdir();write_json(p/'request.json',{'workspace':str(tmp_path),'request':{'kind':'validation','validation':'known_template'}})
 write_json(p/'status.json',{'state':'queued','total_steps':1});return p

def test_choice_label_and_native_capability(tmp_path):
 assert ValidationRequest(validation='known_template').validation=='known_template'
 assert LABELS['known_template']=='既知二モデルの独立評価'
 with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as c:
  env=c.get('/api/environment').json();assert env['available_validations']==['array_scale','casa_window_symmetry','known_template','independent_training']
  assert not env['checkout_validation_available']
  assert '9条件・数分' in c.get('/').text

@pytest.mark.parametrize('key,value',[('profile','smoke'),('trials',16),('seed',1)])
def test_scientific_plan_not_silently_overridden(key,value):
 with pytest.raises(ValueError):ValidationRequest(validation='known_template',**{key:value})

def test_native_dispatch_and_progress_without_checkout_runner(tmp_path,monkeypatch):
 from vsora_simulator import known_template_validation
 p=job(tmp_path);called=[]
 def stub(output,profile,progress):
  assert profile=='full';output.mkdir();progress(0,9,'stub');called.append(json.loads((p/'status.json').read_text())['phase'])
  return {'type':'known_template_holdout_discrimination','state':'complete','explicit_test_stub':True}
 monkeypatch.setattr(known_template_validation,'run',stub);worker.run(p)
 assert len(called)==1 and '1/9' in called[0]
 assert json.loads((p/'summary.json').read_text())['explicit_test_stub']
 origin=json.loads((p/'validation/execution-origin.json').read_text())
 assert origin['formal_profile_executed'] and origin['native_scientific_module_used'] and not origin['checkout_runner_used']
 assert origin['scientific_module_count']==8 and json.loads((p/'status.json').read_text())['state']=='complete'

def test_native_failure_not_reported_complete(tmp_path,monkeypatch):
 from vsora_simulator import known_template_validation
 p=job(tmp_path)
 def fail(*args,**kwargs):raise RuntimeError('explicit test failure')
 monkeypatch.setattr(known_template_validation,'run',fail)
 with pytest.raises(RuntimeError):worker.run(p)
 assert json.loads((p/'status.json').read_text())['state']=='failed' and not (p/'summary.json').exists()

def test_native_progress_cancellation_not_reported_complete(tmp_path,monkeypatch):
 from vsora_simulator import known_template_validation
 p=job(tmp_path);(p/'cancel').touch()
 def cancelled(output,profile,progress):progress(0,9,'stub')
 monkeypatch.setattr(known_template_validation,'run',cancelled)
 with pytest.raises(InterruptedError):worker.run(p)
 assert json.loads((p/'status.json').read_text())['state']=='cancelled' and not (p/'summary.json').exists()


@pytest.mark.parametrize('result',[{'state':'failed_validation'},{'state':'failed'},{'state':'cancelled'},{},None])
def test_scientific_failure_result_not_reported_complete(tmp_path,monkeypatch,result):
 from vsora_simulator import known_template_validation
 p=job(tmp_path)
 monkeypatch.setattr(known_template_validation,'run',lambda *a,**k:result)
 with pytest.raises(ValueError,match='scientific validation did not complete'):worker.run(p)
 status=json.loads((p/'status.json').read_text())
 assert status['state']=='failed' and '数値検証が成功しなかった' in status['error_message']
 assert not (p/'summary.json').exists()
