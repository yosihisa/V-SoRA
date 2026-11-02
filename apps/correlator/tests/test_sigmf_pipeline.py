"""Synthetic SigMF pilot/rate/correlation connection; no image fitting."""
import json
from pathlib import Path

import pytest

from vsora_correlator.closure_pipeline import process_closure_session
from vsora_correlator.sequence import process_sequence
from vsora_correlator.input_identity import InputIdentity
from vsora_formats.spectral import load_spectral
from workflows.vdif_closure_validation import make_fixture
from workflows.sigmf_pipeline_validation import prepare


@pytest.fixture
def inputs(tmp_path):
    make_fixture(tmp_path/'stored',frame_count=70,seed=231)
    prepare(tmp_path/'stored',tmp_path/'input')
    return tmp_path/'input'


@pytest.mark.parametrize('model,exposure,raw',[
    ('constant',.100015625,True),('linear',.1,False)])
def test_actual_pipeline_preserves_pairs_units_and_hash_accounting(inputs,tmp_path,model,exposure,raw):
    result=process_closure_session(inputs/'manifest.json',inputs/'clock.json',tmp_path/'result',
        correlation_only=True,pilot_integrations=64,integration_s=exposure,rate_model=model,save_bispectrum=raw)
    assert result['completed_steps']==['aligned_pilot','model_free_rate','rate_corrected_short_correlation']
    assert result['input_format']=='sigmf_ci16_le' and len(result['input_sigmf'])==4
    assert result['closures'] is None and result['rml'] is None
    assert result['input_identity']['pipeline_data_full_sha_passes_per_station']==1
    assert result['input_identity']['pipeline_data_hash_file_reads']==4
    assert result['input_identity']['pipeline_data_hash_bytes']==4*70*4096*4
    assert all(s['sigmf_data_hash_file_reads']==0 for s in result['input_identity']['direct_subruns'])
    assert not result['absolute_flux_measured'] and not result['absolute_position_measured']
    assert load_spectral(tmp_path/'result/correlation/shard-00000.npz')['metadata']['visibility_unit']=='ADC^2'
    manifest=json.loads((tmp_path/'result/final-manifest.json').read_text())
    assert all(Path(s['sigmf']).is_absolute() for s in manifest['stations'])
    assert (tmp_path/'result/correlation/raw-bispectrum.npz').exists()==raw
    with pytest.raises(FileExistsError):
        process_closure_session(inputs/'manifest.json',inputs/'clock.json',tmp_path/'result',correlation_only=True)


def test_imaging_sequence_remains_unsupported(inputs,tmp_path):
    args=(inputs/'manifest.json',inputs/'clock.json',tmp_path/'result')
    with pytest.raises(ValueError,match='requires explicit correlation_only'):
        process_closure_session(*args)
    with pytest.raises(ValueError,match='requires correlate-aligned'):
        process_sequence(*args)
    assert not (tmp_path/'result').exists() and not (tmp_path/'result.partial').exists()


def test_changed_source_after_rate_stops_before_final_correlation(inputs,tmp_path):
    def mutate(step,done):
        if step=='model_free_rate':
            path=inputs/'station-1.sigmf-meta';path.write_text(path.read_text()+' ')
    with pytest.raises(ValueError,match='changed'):
        process_closure_session(inputs/'manifest.json',inputs/'clock.json',tmp_path/'result',
            correlation_only=True,pilot_integrations=64,integration_s=.1,progress=mutate)
    failure=json.loads((tmp_path/'result.partial/failure.json').read_text())
    assert failure['completed_steps']==['aligned_pilot','model_free_rate']
    assert not (tmp_path/'result.partial/correlation').exists()
    assert not (tmp_path/'result').exists()


def test_20MHz_fractional_epoch_FFT_grid_reaches_pilot_without_VDIF_grid(inputs,tmp_path,monkeypatch):
    from vsora_correlator import closure_pipeline as module
    p=inputs/'manifest.json';c=json.loads(p.read_text());c['sample_rate_hz']=20000000;p.write_text(json.dumps(c))
    epoch='2024-07-30T09:19:20.197123456Z'
    p=inputs/'observation.json';c=json.loads(p.read_text());c['observation']['start_utc']=epoch;p.write_text(json.dumps(c))
    for p in inputs.glob('*.sigmf-meta'):
        c=json.loads(p.read_text());c['global']['core:sample_rate']=20000000;c['captures'][0]['core:datetime']=epoch;p.write_text(json.dumps(c))
    p=inputs/'clock.json';c=json.loads(p.read_text());c['max_abs_baseband_hz']=4000000
    for station in c['stations']:station['actual_sample_rate_hz']=20000000
    p.write_text(json.dumps(c));seen=[]
    def probe(*args,**kwargs):
        seen.append(json.loads(Path(args[0]).read_text()))
        raise RuntimeError('dimension probe reached pilot')
    monkeypatch.setattr(module,'correlate_aligned',probe)
    with pytest.raises(RuntimeError,match='dimension probe'):
        process_closure_session(inputs/'manifest.json',inputs/'clock.json',tmp_path/'result',
            correlation_only=True,pilot_integrations=64,pilot_integration_s=.002,integration_s=.1)
    assert len(seen)==1 and seen[0]['blocks_per_integration']==1250
    assert seen[0]['sample_rate_hz']==20000000
    # Mocked numerical work: acceptance of dimensions is the only claim here.


def test_metadata_symlink_keeps_its_original_sibling_name(inputs,tmp_path,monkeypatch):
    from vsora_correlator import closure_pipeline as module
    original=inputs/'station-1.sigmf-meta';target=inputs/'stored-metadata.json';original.rename(target);original.symlink_to(target.name)
    seen=[]
    def probe(*args,**kwargs):
        seen.append(json.loads(Path(args[0]).read_text())['stations'][0]['sigmf'])
        raise RuntimeError('clone probe')
    monkeypatch.setattr(module,'correlate_aligned',probe)
    with pytest.raises(RuntimeError,match='clone probe'):
        process_closure_session(inputs/'manifest.json',inputs/'clock.json',tmp_path/'result',correlation_only=True)
    assert seen==[str(original.absolute())]
