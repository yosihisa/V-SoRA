import json
from pathlib import Path
import numpy as np
import pytest
import astropy.units as u
from astropy.time import Time
from vsora_observation import load_config
from vsora_observation.geometry import geometry_at_times
from vsora_simulator.iq import generate_iq
from vsora_formats.vdif import write_vdif
from vsora_formats.spectral import load_spectral,save_spectral
from vsora_formats.fitsidi import read_fitsidi
from vsora_correlator.session import correlate_session,calibrate_shard,apply_shard,load_session


def prepare(root):
    repo=Path(__file__).resolve().parents[2]
    c=load_config(repo/'configs/experiments/ideal-point.json')
    for i,s in enumerate(c['stations']): s['enu_m']=[i*.01,i%2*.01,0]
    (root/'observation.json').write_text(json.dumps(c))
    t=Time(c['observation']['start_utc'])+.032*u.s;g=geometry_at_times(c,Time([t]))
    sky=np.zeros((16,16));sky[8,8]=1000
    x,_=generate_iq(np.zeros((6,3)),g['pairs'],sky,16,np.zeros(4),2048000,1.42e9,128,1024,9,g['station_delay_s'][0])
    amplitudes=np.array([1.2,.8,1.1,.9]);x*=4*amplitudes[:,None] # unknown ADC/sqrt(Jy) gain
    stations=[]
    for i,data in enumerate(x):
        scale=2*np.sqrt(np.mean(abs(data)**2)/2)
        write_vdif(root/f's{i}.vdif',data,c['observation']['start_utc'],2048000,i+1,scale,voltage_unit='ADC')
        stations.append({'id':c['stations'][i]['id'],'vdif':f's{i}.vdif','station_numeric_id':i+1,'decoded_voltage_scale':scale})
    manifest={'schema_version':1,'observation_config':'observation.json','sample_rate_hz':2048000,
              'fft_length':128,'blocks_per_integration':32,'integrations_per_shard':32,
              'voltage_unit':'ADC','stations':stations,'phase_center_correction':True}
    (root/'session.json').write_text(json.dumps(manifest));return manifest


def test_raw_session_to_calibrated_idi(tmp_path):
    prepare(tmp_path);r=correlate_session(tmp_path/'session.json',tmp_path/'raw')
    assert r['state']=='complete' and r['integrations']==32 and r['recorded_span_s']==.064
    path=tmp_path/'raw/shard-00000.npz';raw=load_spectral(path)
    assert raw['metadata']['visibility_unit']=='ADC^2' and 'vis_jy' not in raw
    cal=calibrate_shard(path,tmp_path/'cal.json',1000)
    np.testing.assert_allclose(cal['amplitude'],4*np.array([1.2,.8,1.1,.9]),rtol=.01)
    apply_shard(path,tmp_path/'cal.json',tmp_path/'corrected')
    idi=read_fitsidi(tmp_path/'corrected/visibility.fits')
    np.testing.assert_allclose(idi['vis_jy'].mean(axis=0),1000,rtol=.002)
    assert load_spectral(tmp_path/'corrected/calibrated.npz')['metadata']['visibility_unit']=='Jy'


def test_session_failure_is_not_success_and_units_checked(tmp_path):
    m=prepare(tmp_path);m['stations'][1]['station_numeric_id']=99
    (tmp_path/'bad.json').write_text(json.dumps(m))
    with pytest.raises(ValueError,match='station ID'): correlate_session(tmp_path/'bad.json',tmp_path/'failed')
    assert not (tmp_path/'failed').exists()
    assert json.loads((tmp_path/'failed.partial/failure.json').read_text())['state']=='incomplete'
    m['voltage_unit']='guess';(tmp_path/'bad.json').write_text(json.dumps(m))
    with pytest.raises(ValueError,match='unit'): load_session(tmp_path/'bad.json')


def test_sharding_and_overwrite_rejection(tmp_path):
    m=prepare(tmp_path);m['integrations_per_shard']=8
    (tmp_path/'session.json').write_text(json.dumps(m))
    result=correlate_session(tmp_path/'session.json',tmp_path/'raw')
    assert len(result['shards'])==4
    assert result['voltage_buffer_samples_per_station']==4096
    for i in range(4): assert load_spectral(tmp_path/f'raw/shard-{i:05d}.npz')['visibilities'].shape[0]==8
    with pytest.raises(FileExistsError): correlate_session(tmp_path/'session.json',tmp_path/'raw')


def test_rate_composition_with_different_phase_reference(tmp_path):
    prepare(tmp_path);correlate_session(tmp_path/'session.json',tmp_path/'raw')
    path=tmp_path/'raw/shard-00000.npz';d=load_spectral(path)
    base=calibrate_shard(path,tmp_path/'base.json',1000)
    removed=np.array([0.,2.,3.,-1.]);rref=.3;p=d['pairs']
    field=np.exp(-2j*np.pi*(d['times_s'][:,None,None]-rref)*removed[None,None,:])
    values=d['visibilities']*(field[...,p[:,0]]*field[...,p[:,1]].conj())
    values=np.broadcast_to(values,d['visibilities'].shape)
    cube={k:d[k] for k in ('weights','pairs','times_s','frequencies_hz','uvw_lambda','integration_s')}
    cube['visibilities']=values
    meta={**d['metadata'],'rate_applied_hz':removed.tolist(),'rate_applied_reference_s':rref}
    save_spectral(tmp_path/'shifted.npz',cube,meta)
    combined=calibrate_shard(tmp_path/'shifted.npz',tmp_path/'combined.json',1000)
    np.testing.assert_allclose(combined['rate_hz'],base['rate_hz'],atol=1e-6)
    np.testing.assert_allclose(np.exp(1j*np.array(combined['phase_rad'])),np.exp(1j*np.array(base['phase_rad'])),atol=1e-6)
    apply_shard(tmp_path/'shifted.npz',tmp_path/'combined.json',tmp_path/'applied')
    np.testing.assert_allclose(read_fitsidi(tmp_path/'applied/visibility.fits')['vis_jy'].mean(axis=0),1000,rtol=.002)


def test_subframe_one_millisecond_integrations(tmp_path):
    m=prepare(tmp_path);m['blocks_per_integration']=16;m['integrations_per_shard']=64
    (tmp_path/'session.json').write_text(json.dumps(m))
    result=correlate_session(tmp_path/'session.json',tmp_path/'short')
    d=load_spectral(tmp_path/'short/shard-00000.npz')
    assert result['integrations']==64 and result['integration_s']==.001
    np.testing.assert_allclose(np.diff(d['times_s']),.001,rtol=0,atol=1e-15)
    assert result['voltage_buffer_samples_per_station']==4096
    assert np.all(d['integration_s']==.001)


def test_session_keeps_channel_diagnostics_and_manual_flags(tmp_path):
    m=prepare(tmp_path)
    m['spectral_quality']={'channel_weights':True,'min_sk_blocks':128,'sk_bounds':[.3,3.],
                           'exclude_rf_ranges_hz':[[1.42e9-1,1.42e9+1]]}
    (tmp_path/'session.json').write_text(json.dumps(m))
    correlate_session(tmp_path/'session.json',tmp_path/'quality')
    d=load_spectral(tmp_path/'quality/shard-00000.npz')
    assert d['diagnostic_station_power'].shape==(32,128,4)
    index=np.argmin(abs(d['frequencies_hz']-1.42e9))
    assert np.all(d['weights'][:,index,:]==0)
    assert np.all(d['diagnostic_station_flags'][:,index,:]&8)
    assert not d['diagnostic_station_sk_eligible'].any()
    assert d['metadata']['diagnostic_power_unit']=='ADC^2'
