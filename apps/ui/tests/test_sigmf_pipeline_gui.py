"""The existing image GUI must not implicitly enable SigMF correlation-only."""
import time
import pytest

from fastapi.testclient import TestClient
from vsora_ui.server import create_app
from workflows.vdif_closure_validation import make_fixture
from workflows.sigmf_pipeline_validation import prepare


@pytest.mark.parametrize('kind',['analysis','sequence'])
def test_existing_image_GUI_rejects_SigMF_before_pipeline_output(tmp_path,kind):
    make_fixture(tmp_path/'stored',frame_count=70,seed=231)
    prepare(tmp_path/'stored',tmp_path/'input')
    with TestClient(create_app(tmp_path),base_url='http://127.0.0.1') as client:
        response=client.post('/api/jobs',json={'kind':kind,'manifest':'input/manifest.json',
            'clock_model':'input/clock.json'},headers={'X-VSoRA-Request':'1','Origin':'http://127.0.0.1'})
        assert response.status_code==202
        identity=response.json()['id'];deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            result=client.get('/api/jobs/'+identity).json()
            if result['state'] not in ('queued','running'):break
            time.sleep(.05)
        assert result['state']=='failed'
        assert not (tmp_path/'outputs/gui'/identity/kind).exists()
        assert not (tmp_path/'outputs/gui'/identity/(kind+'.partial')).exists()
