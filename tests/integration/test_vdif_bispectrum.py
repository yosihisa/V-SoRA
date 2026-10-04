"""VDIF aligned raw U3 sidecar opt-in; shared processed FFT and legacy arrays."""
import json
from pathlib import Path
import numpy as np
import pytest
from vsora_correlator import aligned
from vsora_correlator.stream_fx import FXAccumulator
from vsora_formats.bispectrum import load_bispectrum
from vsora_formats.spectral import load_spectral
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum


def test_actual_vdif_sidecar_matches_captured_processed_fft(tmp_path,monkeypatch):
    from workflows.vdif_bispectrum_validation import run
    captured=[]
    class RecordingFX(FXAccumulator):
        def __init__(self,*a,**kw):
            super().__init__(*a,**kw);self.captured=[];self.validity=[]
            if self.bispectrum is not None:captured.append(self)
        def consume(self,x,valid=None):
            if self.bispectrum is not None:
                self.captured.append(x.copy());self.validity.append(valid.copy())
            return super().consume(x,valid)
    monkeypatch.setattr(aligned,'FXAccumulator',RecordingFX)
    out=tmp_path/'vdif';q=run(out)
    assert q['ordinary_numeric_arrays_compared']==13 and q['ordinary_arrays_bit_identical']
    assert q['source_visibility_verified'] and len(captured)==2
    raw=load_bispectrum(out/'with-raw/raw-bispectrum.npz',out/'with-raw/shard-00000.npz')
    assert raw['metadata']['bispectrum_unit']=='ADC^6'
    for cell,a in enumerate(captured):
        x=np.concatenate(a.captured,axis=1);valid=np.concatenate(a.validity,axis=1)
        n=x.shape[1]//a.nf;order=np.argsort(a.frequency)
        fft=np.fft.fft(x.reshape(a.stations,n,a.nf).transpose(1,2,0),axis=1,norm='ortho')[:,order]
        good=valid.reshape(a.stations,n,a.nf).all(axis=2).T
        for t,tri in enumerate(raw['triangles']):
            common=good[:,tri].all(axis=1)
            batch=distinct_sample_bispectrum(fft[common].transpose(1,0,2),[tri])
            np.testing.assert_allclose(raw['distinct_sample_bispectrum'][cell,:,t],batch['distinct_sample_bispectrum'][:,0],rtol=1e-10,atol=1e-6)
            assert raw['common_fft_count'][cell,t]==common.sum()
    assert all(not raw['metadata'][key] for key in ('input_sample_independence_verified','input_mask_independence_verified','production_rml_noise_model_changed'))
    assert (out/'vdif-bispectrum.png').exists()
    with pytest.raises(FileExistsError):run(out)


@pytest.mark.parametrize('bad',[1,'true',None])
def test_invalid_option_rejected_before_input(tmp_path,bad):
    with pytest.raises(ValueError,match='bool'):
        aligned.correlate_aligned('absent','absent',tmp_path/'out',1,collect_bispectrum=bad)
    assert not (tmp_path/'out').exists() and not (tmp_path/'out.partial').exists()


@pytest.mark.parametrize('n,nf,m,integrations',[(2,32,4,1),(9,32,4,1),(4,8192,4,1),(8,4096,1,2)])
def test_unsupported_raw_dimensions_rejected_before_clock_or_output(tmp_path,monkeypatch,n,nf,m,integrations):
    c={'_config':{},'sample_rate_hz':2048000.,'phase_center_correction':True,
       'stations':[{} for _ in range(n)],'fft_length':nf,'blocks_per_integration':m}
    monkeypatch.setattr(aligned,'load_session',lambda _:c)
    with pytest.raises(ValueError,match='raw bispectrum'):
        aligned.correlate_aligned('not-read','absent-clock',tmp_path/'out',integrations,collect_bispectrum=True)
    assert not (tmp_path/'out').exists() and not (tmp_path/'out.partial').exists()


def test_elevation_flags_mark_every_triangle_unusable(tmp_path,monkeypatch):
    from workflows.vdif_closure_validation import make_fixture
    make_fixture(tmp_path/'input',seed=6402,frame_count=12,rates_hz=[0.,0.,0.,0.])
    original=aligned.geometry_at_times
    def below(*a,**kw):
        result=original(*a,**kw);result['elevation_valid']=np.zeros_like(result['elevation_valid'],bool);return result
    monkeypatch.setattr(aligned,'geometry_at_times',below)
    aligned.correlate_aligned(tmp_path/'input/manifest.json',tmp_path/'input/clock.json',tmp_path/'out',2,collect_bispectrum=True)
    raw=load_bispectrum(tmp_path/'out/raw-bispectrum.npz',tmp_path/'out/shard-00000.npz')
    assert not raw['channel_triangle_usable'].any() and np.all(raw['common_fft_count']>=3)


def test_sidecar_save_failure_keeps_output_incomplete(tmp_path,monkeypatch):
    from workflows.vdif_closure_validation import make_fixture
    make_fixture(tmp_path/'input',seed=6403,frame_count=12,rates_hz=[0.,0.,0.,0.])
    def failed(*a,**kw):raise OSError('injected raw sidecar write failure')
    monkeypatch.setattr(aligned,'save_bispectrum',failed)
    with pytest.raises(OSError):
        aligned.correlate_aligned(tmp_path/'input/manifest.json',tmp_path/'input/clock.json',tmp_path/'out',2,collect_bispectrum=True)
    assert not (tmp_path/'out').exists()
    assert json.loads((tmp_path/'out.partial/failure.json').read_text())['state']=='incomplete'


def test_jy_declared_unit_preserved(tmp_path):
    from workflows.vdif_closure_validation import make_fixture
    make_fixture(tmp_path/'input',seed=6404,frame_count=12,rates_hz=[0.,0.,0.,0.])
    p=tmp_path/'input/manifest.json';c=json.loads(p.read_text());c['voltage_unit']='sqrt(Jy)';p.write_text(json.dumps(c))
    aligned.correlate_aligned(p,tmp_path/'input/clock.json',tmp_path/'out',2,collect_bispectrum=True)
    raw=load_bispectrum(tmp_path/'out/raw-bispectrum.npz',tmp_path/'out/shard-00000.npz')
    assert raw['metadata']['bispectrum_unit']=='Jy^3' and raw['metadata']['voltage_unit']=='sqrt(Jy)'


@pytest.mark.parametrize('bad',[True,0,-1,1.5])
def test_raw_dimension_helper_rejects_invalid_integration_count(bad):
    c={'sample_rate_hz':2048000.,'stations':[{}]*4,'fft_length':32,'blocks_per_integration':128}
    with pytest.raises(ValueError):aligned.validate_bispectrum_dimensions(c,bad)


def test_raw_dimension_helper_rejects_more_than_million_blocks():
    c={'sample_rate_hz':10000000.,'stations':[{}]*4,'fft_length':8,'blocks_per_integration':1000001}
    with pytest.raises(ValueError,match='raw bispectrum'):aligned.validate_bispectrum_dimensions(c,1)
