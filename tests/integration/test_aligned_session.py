import json
from pathlib import Path
import numpy as np
import pytest
import astropy.units as u
from astropy.time import Time
from vsora_observation import load_config
from vsora_observation.geometry import geometry_at_times
from vsora_formats.vdif import write_vdif
from vsora_formats.spectral import load_spectral
from vsora_correlator.aligned import correlate_aligned


def test_bounded_physical_clock_and_rf_alignment(tmp_path):
    repo=Path(__file__).resolve().parents[2];c=load_config(repo/'configs/experiments/ideal-point.json')
    fs=2048000;fc=1.42e9;n=65536
    end=.04;origin=Time(c['observation']['start_utc'])
    g=geometry_at_times(c,origin+np.array([0,end])*u.s,filter_elevation=False)
    frequency=np.array([-25,-17,-9,3,11,19,27])*fs/128
    def signal(t): return np.exp(2j*np.pi*t[:,None]*frequency+1j*np.arange(7)).sum(axis=1)/np.sqrt(7)
    starts=np.array([0,3.25,-2.4,.3])/fs;rates=fs*(1+np.array([0,80,-65,0])*1e-6)
    stations=[];clock=[]
    for i in range(4):
        t=starts[i]+np.arange(n)/rates[i];delay=np.interp(t,[0,end],g['station_delay_s'][:,i])
        x=signal(t+delay)*np.exp(2j*np.pi*fc*delay)
        scale=2*np.sqrt(np.mean(abs(x)**2)/2)
        write_vdif(tmp_path/f's{i}.vdif',x,c['observation']['start_utc'],fs,i+1,scale,voltage_unit='ADC')
        stations.append({'id':c['stations'][i]['id'],'vdif':f's{i}.vdif','station_numeric_id':i+1,'decoded_voltage_scale':scale})
        clock.append({'id':c['stations'][i]['id'],'input_start_offset_s':float(starts[i]),'actual_sample_rate_hz':float(rates[i])})
    (tmp_path/'obs.json').write_text(json.dumps(c))
    manifest={'schema_version':1,'observation_config':'obs.json','sample_rate_hz':fs,'fft_length':128,
              'blocks_per_integration':32,'integrations_per_shard':8,'voltage_unit':'ADC','phase_center_correction':True,'stations':stations}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    (tmp_path/'clock.json').write_text(json.dumps({'schema_version':1,'max_abs_baseband_hz':600000,'stations':clock}))
    result=correlate_aligned(tmp_path/'manifest.json',tmp_path/'clock.json',tmp_path/'aligned',8)
    d=load_spectral(tmp_path/'aligned/shard-00000.npz')
    active=abs(d['frequencies_hz']-fc)<500000
    averaged=d['visibilities'][:,active,:].mean(axis=1)
    # All stations see the same continuous wave after time/RF correction.
    spread=np.linalg.norm(averaged-averaged.mean(axis=1,keepdims=True))/np.linalg.norm(averaged)
    assert spread<.003
    assert max(result['station_max_buffer_samples'])<3*4096
    assert result['recorded_span_s']==.016 and d['metadata']['clock_mapping_applied']
    (tmp_path/'validation-summary.json').write_text(json.dumps({**result,'observed_relative_baseline_spread':float(spread),
           'input_clock_ppm':[0,80,-65,0],'input_offsets_samples':[0,3.25,-2.4,.3],
           'signal':'Strong continuous seven-tone wave; no receiver noise','rf_hz':fc,'sample_rate_hz':fs},indent=2)+'\n')
    with pytest.raises(ValueError,match='input ends'):
        correlate_aligned(tmp_path/'manifest.json',tmp_path/'clock.json',tmp_path/'too-long',128)
    assert not (tmp_path/'too-long').exists()
    assert json.loads((tmp_path/'too-long.partial/failure.json').read_text())['state']=='incomplete'
