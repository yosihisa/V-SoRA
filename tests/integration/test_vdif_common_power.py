"""Actual synthetic VDIF processing, captured FFT powers and 0.3s windows."""
import json
from pathlib import Path
import numpy as np
import pytest
from vsora_correlator import aligned
from vsora_correlator.stream_fx import FXAccumulator
from vsora_correlator.bispectrum_inspect import inspect_bispectrum_cell
from vsora_formats.bispectrum import load_bispectrum
from vsora_formats.spectral import load_spectral
from vsora_formats.vdif import read_vdif,write_vdif
from vsora_simulator.bispectrum_observed_power import observed_power_normalized_bispectrum

@pytest.mark.parametrize('missing',[False,True])
def test_actual_point_three_second_vdif_common_power(tmp_path,monkeypatch,missing):
    from workflows.vdif_closure_validation import make_fixture
    input=tmp_path/'input';generating=make_fixture(input,seed=9100,frame_count=180,pilot_blocks=19200,fft_length=32)
    manifest=input/'manifest.json';cfg=json.loads(manifest.read_text());obs=json.loads((input/'observation.json').read_text())
    if missing:
        for station,frame in [(0,7),(1,19)]:
            info=cfg['stations'][station];path=input/info['vdif']
            x,good,_=read_vdif(path,cfg['sample_rate_hz'],info['station_numeric_id'],info['decoded_voltage_scale'])
            good[frame*4096:(frame+1)*4096]=False;path.unlink();path.with_suffix('.json').unlink()
            write_vdif(path,x,obs['observation']['start_utc'],cfg['sample_rate_hz'],info['station_numeric_id'],
                info['decoded_voltage_scale'],valid=good,voltage_unit='ADC')
    profile={'schema_version':1,'type':'station_rate_only','station_ids':[s['id'] for s in obs['stations']],
        'station_indices':list(range(4)),'time_origin_utc':obs['observation']['start_utc'],
        'station_rates_hz':generating['true_rates_hz'],'valid_time_range_s':[0.,.36],
        'sample_cadence_s':.002,'time_reference_s':.15}
    rate=tmp_path/'rate.json';rate.write_text(json.dumps(profile))
    captured=[]
    class Recording(FXAccumulator):
        def __init__(self,*a,**kw):
            super().__init__(*a,**kw);self.captured_samples=[];self.masks=[]
            if self.bispectrum is not None:captured.append(self)
        def consume(self,x,valid=None):
            if self.bispectrum is not None:self.captured_samples.append(x.copy());self.masks.append(valid.copy())
            return super().consume(x,valid)
    monkeypatch.setattr(aligned,'FXAccumulator',Recording)
    off=aligned.correlate_aligned(manifest,input/'clock.json',tmp_path/'off',1,rate_profile=rate)
    on=aligned.correlate_aligned(manifest,input/'clock.json',tmp_path/'on',1,rate_profile=rate,collect_bispectrum=True)
    a=load_spectral(tmp_path/'off/shard-00000.npz');b=load_spectral(tmp_path/'on/shard-00000.npz')
    for key,value in a.items():
        if isinstance(value,np.ndarray):np.testing.assert_array_equal(value,b[key])
        else:assert value==b[key]
    assert 'raw_bispectrum' not in off and not (tmp_path/'off/raw-bispectrum.npz').exists()
    raw=load_bispectrum(tmp_path/'on/raw-bispectrum.npz',tmp_path/'on/shard-00000.npz')
    assert raw['schema_version']==2 and on['raw_bispectrum']['schema_version']==2
    assert on['raw_bispectrum']['common_station_power_saved'] and raw['source_visibility_verified']
    assert on['raw_bispectrum']['common_power_sum_unit']=='ADC^2'
    assert on['samples_per_integration']/cfg['sample_rate_hz']==.3 and len(captured)==1
    acc=captured[0];x=np.concatenate(acc.captured_samples,axis=1);valid=np.concatenate(acc.masks,axis=1)
    m=x.shape[1]//acc.nf;order=np.argsort(acc.frequency)
    fft=np.fft.fft(x.reshape(acc.stations,m,acc.nf).transpose(1,2,0),axis=1,norm='ortho')[:,order]
    good=valid.reshape(acc.stations,m,acc.nf).all(axis=2).T
    inspections=[inspect_bispectrum_cell(raw,0,fi) for fi in range(acc.nf)]
    for k,tri in enumerate(raw['triangles']):
        common=good[:,tri].all(axis=1)
        np.testing.assert_allclose(raw['common_station_power_sums'][0,:,k],
            (abs(fft[common][:,:,tri])**2).sum(axis=0),rtol=2e-12,atol=2e-8)
        expected=observed_power_normalized_bispectrum(fft[common][:,:,tri].transpose(1,0,2))
        assert raw['common_fft_count'][0,k]==common.sum()
        for fi,q in enumerate(inspections):
            row=q['triangles'][k];assert row['observed_power_normalized_u3_available']
            actual=complex(row['observed_power_normalized_u3_real'],row['observed_power_normalized_u3_imag'])
            np.testing.assert_allclose(actual,expected['observed_power_normalized_u3'][fi,0],rtol=2e-10,atol=2e-12)
    assert not raw['metadata']['input_sample_independence_verified']
    assert not raw['metadata']['production_rml_noise_model_changed']
