import pytest
from vsora_correlator.aligned import validate_aligned_dimensions
from vsora_correlator.closure_pipeline import process_closure_session
from workflows.vdif_closure_validation import make_fixture


def test_dense_dimensions_and_spectral_memory_bound():
    c={'fft_length':8,'blocks_per_integration':64,'sample_rate_hz':2048000,'stations':[{}, {}, {}, {}]}
    assert validate_aligned_dimensions(c,4096)==(512,1.024,196608)
    with pytest.raises(ValueError,match='spectral cells'):
        validate_aligned_dimensions({**c,'fft_length':256,'blocks_per_integration':2},4096)
    with pytest.raises(ValueError,match='3 seconds'):validate_aligned_dimensions(c,16384)
    with pytest.raises(ValueError,match='16384'):validate_aligned_dimensions(c,True)


@pytest.mark.parametrize('kwargs,match',[
    ({'pilot_integration_s':.0003},'FFT blocks'),
    ({'pilot_integration_s':.00025,'max_rate_hz':2000},'Nyquist'),
    ({'pilot_integrations':True},'short integrations'),
    ({'pilot_integrations':16385},'short integrations'),
    ({'pilot_integrations':10000,'pilot_integration_s':.0005},'3 seconds'),
    ({'pilot_integrations':16384,'pilot_integration_s':.000125},'spectral cells'),
])
def test_pilot_preflight_rejects_before_output(tmp_path,kwargs,match):
    make_fixture(tmp_path/'input',seed=29,frame_count=16)
    with pytest.raises(ValueError,match=match):
        process_closure_session(tmp_path/'input/manifest.json',tmp_path/'input/clock.json',tmp_path/'result',**kwargs)
    assert not (tmp_path/'result').exists() and not (tmp_path/'result.partial').exists()
