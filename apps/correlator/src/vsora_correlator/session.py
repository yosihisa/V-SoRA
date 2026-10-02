"""Bounded-frame session correlation with explicit raw/calibrated units."""
import json
from itertools import zip_longest
from pathlib import Path
import numpy as np
import astropy.units as u
from astropy.time import Time
from vsora_observation import load_config
from vsora_observation.geometry import geometry_at_times
from vsora_formats.vdif import iter_vdif_frames
from vsora_formats.spectral import save_spectral,load_spectral
from vsora_formats.fitsidi import write_fitsidi
from .fx import fx_correlate_series,remove_fringe_rate
from .fringe import solve_fringe,apply_calibration,save_calibration


def load_session(path):
    p=Path(path);c=json.loads(p.read_text())
    required={'schema_version','observation_config','sample_rate_hz','fft_length',
              'blocks_per_integration','integrations_per_shard','voltage_unit','stations','phase_center_correction'}
    if set(c)!=required or c['schema_version']!=1: raise ValueError('unsupported session keys/version')
    for k in ('sample_rate_hz','fft_length','blocks_per_integration','integrations_per_shard'):
        if not isinstance(c[k],int) or isinstance(c[k],bool) or c[k]<=0: raise ValueError('positive session integers required')
    if c['fft_length']<8 or c['integrations_per_shard']>256: raise ValueError('unsupported FFT/shard dimensions')
    if c['sample_rate_hz']%4096 or (c['fft_length']*c['blocks_per_integration'])%4096:
        raise ValueError('session requires 4096-sample EDV0 frames and whole-frame integrations')
    if c['voltage_unit'] not in ('ADC','sqrt(Jy)') or not isinstance(c['phase_center_correction'],bool):
        raise ValueError('explicit voltage unit and phase-center bool required')
    config=load_config(p.parent/c['observation_config'])
    stations=c['stations']
    if not isinstance(stations,list) or len(stations)!=len(config['stations']): raise ValueError('station count differs')
    seen=set()
    for a,b in zip(stations,config['stations']):
        if set(a)!={'id','vdif','station_numeric_id','decoded_voltage_scale'} or a['id']!=b['id']:
            raise ValueError('station order/keys differ')
        number=a['station_numeric_id'];scale=a['decoded_voltage_scale']
        if not isinstance(number,int) or isinstance(number,bool) or not 0<=number<=65535 or number in seen:
            raise ValueError('invalid or duplicate numeric station ID')
        seen.add(number)
        if not isinstance(scale,(int,float)) or isinstance(scale,bool) or not np.isfinite(scale) or scale<=0:
            raise ValueError('positive station decoded scale required')
        if not isinstance(a['vdif'],str): raise ValueError('VDIF path string required')
        if not (p.parent/a['vdif']).is_file(): raise FileNotFoundError('session VDIF file unavailable')
    c['_config']=config;c['_root']=p.parent
    return c


def correlate_session(manifest,output,rate_calibration=None,allow_extrapolation=False):
    c=load_session(manifest);config=c['_config'];out=Path(output);partial=out.with_name(out.name+'.partial')
    if out.exists() or partial.exists(): raise FileExistsError('choose a new output directory')
    fs=c['sample_rate_hz'];ns=c['fft_length']*c['blocks_per_integration']
    cal=json.loads(Path(rate_calibration).read_text()) if rate_calibration else None
    if cal and ('time_origin_utc' not in cal or abs((Time(cal['time_origin_utc'])-Time(config['observation']['start_utc'])).to_value(u.s))>1e-7):
        raise ValueError('rate calibration time origin differs')
    partial.mkdir(parents=True)
    readers=[iter_vdif_frames(c['_root']/s['vdif'],fs,s['station_numeric_id'],s['decoded_voltage_scale']) for s in c['stations']]
    buffers=[[] for _ in readers];masks=[[] for _ in readers];pending=[];processed=0;first=None;shards=[]
    rate_applied=[0.]*len(readers) if cal is None else cal['rate_hz']
    def flush():
        if not pending: return
        indexes=np.arange(processed-len(pending),processed)
        offsets=(indexes+.5)*ns/fs
        times=first+offsets*u.s;g=geometry_at_times(config,times,filter_elevation=False)
        values=np.array([r['vis_jy'][0] for r in pending]);weights=np.array([r['weights'][0] for r in pending])
        frequency=pending[0]['frequencies_hz'];pairs=g['pairs']
        if c['phase_center_correction']:
            factor=np.exp(-2j*np.pi*frequency[None,:,None]*g['station_delay_s'][:,None,:])
            values*=factor[...,pairs[:,0]]*factor[...,pairs[:,1]].conj()
        weights[~g['elevation_valid']]=0
        cube={'visibilities':values,'weights':weights,'pairs':pairs,'times_s':offsets,'frequencies_hz':frequency,
              'uvw_lambda':g['uvw_lambda'][:,None,:,:]*(frequency[None,:,None,None]/config['observation']['frequency_hz']),
              'integration_s':np.array([r['integration_s'][0] for r in pending])}
        name=f'shard-{len(shards):05d}.npz'
        metadata={'visibility_unit':'Jy' if c['voltage_unit']=='sqrt(Jy)' else 'ADC^2',
                  'time_origin_utc':first.isot+'Z','config':config,'phase_center_corrected':c['phase_center_correction'],
                  'rate_applied_hz':rate_applied,'rate_applied_reference_s':0. if cal is None else cal['time_reference_s'],
                  'eop_status':g['eop_status'],
                  'geometry_model':g['model'],'noise_weight_assumption':pending[0]['noise_weight_assumption']}
        save_spectral(partial/name,cube,metadata)
        shards.append({'file':name,'integrations':len(pending),'first_time_s':float(offsets[0]),'last_time_s':float(offsets[-1])})
        pending.clear()
    try:
        for frames in zip_longest(*readers):
            if any(f is None for f in frames): raise ValueError('station files have unequal frame counts')
            if any(len(f['data'])!=4096 for f in frames): raise ValueError('session profile requires 4096 samples/frame')
            stamp=frames[0]['time']
            if any(abs((f['time']-stamp).to_value(u.s))>1e-7 for f in frames):
                raise ValueError('station frames are not synchronized; align timestamps first')
            if first is None:
                first=stamp
                if abs((first-Time(config['observation']['start_utc'])).to_value(u.s))>1e-7:
                    raise ValueError('configured UTC start and VDIF start differ')
            for i,f in enumerate(frames): buffers[i].append(f['data']);masks[i].append(f['valid'])
            if len(buffers[0])*4096==ns:
                x=np.array([np.concatenate(b) for b in buffers]);ok=np.array([np.concatenate(b) for b in masks])
                offset=processed*ns/fs
                if cal:
                    if not allow_extrapolation and (offset<cal['time_range_s'][0]-ns/fs or offset+ns/fs>cal['time_range_s'][1]+ns/fs):
                        raise ValueError('rate calibration extrapolation requires explicit permission')
                    x=remove_fringe_rate(x,fs,cal['rate_hz'],offset,cal['time_reference_s'])
                pending.append(fx_correlate_series(x,fs,c['fft_length'],c['blocks_per_integration'],
                               config['observation']['frequency_hz'],valid=ok,time_offset_s=offset))
                processed+=1
                for b in buffers+masks: b.clear()
                if len(pending)==c['integrations_per_shard']: flush()
        if buffers[0]: raise ValueError('trailing partial integration; change integration size')
        flush()
        if processed==0: raise ValueError('no complete integration')
        summary={'schema_version':1,'state':'complete','stations':len(readers),'integrations':processed,
                 'sample_count_per_station':processed*ns,'recorded_span_s':processed*ns/fs,'shards':shards,
                 'sample_rate_hz':fs,'fft_length':c['fft_length'],'integration_s':ns/fs,
                 'visibility_unit':'Jy' if c['voltage_unit']=='sqrt(Jy)' else 'ADC^2',
                 'voltage_buffer_samples_per_station':ns,'spectral_buffer_integrations':c['integrations_per_shard'],
                 'limitations':['Strict matching frame timestamps; no automatic gap filling or clock resampling',
                                'Midpoint phase-only geometric correction; finite-FFT delay loss not removed',
                                'Approximate total-power noise weights, no RFI or bandpass calibration']}
        (partial/'session.json').write_text(json.dumps(summary,indent=2)+'\n');partial.rename(out)
        return summary
    except Exception as exc:
        (partial/'failure.json').write_text(json.dumps({'state':'incomplete','completed_integrations':processed,
                                                       'error_type':type(exc).__name__})+'\n')
        raise
    finally:
        for reader in readers: reader.close()


def calibrate_shard(input_path,output,point_flux_jy,reference_station=0):
    if not np.isfinite(point_flux_jy) or point_flux_jy<=0: raise ValueError('known positive point flux required')
    d=load_spectral(input_path);m=d['metadata']
    if not m.get('phase_center_corrected'): raise ValueError('point calibrator requires phase-center correction')
    c=solve_fringe(d['visibilities'],np.ones(d['visibilities'].shape)*point_flux_jy,d['weights'],d['pairs'],
                   d['times_s'],d['frequencies_hz'],reference_station)
    # A second pilot may already have the first estimate removed from IQ.
    removed=np.array(m.get('rate_applied_hz',np.zeros(len(c['amplitude']))))
    c['phase_rad']=np.angle(np.exp(1j*(np.array(c['phase_rad'])+2*np.pi*removed*(c['time_reference_s']-m.get('rate_applied_reference_s',0.))))).tolist()
    c['rate_hz']=(np.array(c['rate_hz'])+removed).tolist()
    c.update({'time_origin_utc':m['time_origin_utc'],'input_visibility_unit':m['visibility_unit'],
              'output_visibility_unit':'Jy','known_point_flux_jy':point_flux_jy,
              'station_ids':[s['id'] for s in m['config']['stations']]})
    save_calibration(output,c)
    return c


def apply_shard(input_path,calibration_path,output,allow_extrapolation=False):
    d=load_spectral(input_path);meta=d['metadata'];c=json.loads(Path(calibration_path).read_text())
    if meta['time_origin_utc']!=c.get('time_origin_utc') or meta['visibility_unit']!=c.get('input_visibility_unit'):
        raise ValueError('calibration origin or input unit differs')
    if [s['id'] for s in meta['config']['stations']]!=c.get('station_ids'): raise ValueError('calibration station order differs')
    out=Path(output)
    partial=out.with_name(out.name+'.partial')
    if out.exists() or partial.exists(): raise FileExistsError('choose a new output directory')
    removed=np.array(meta['rate_applied_hz'])
    residual={**c,'rate_hz':(np.array(c['rate_hz'])-removed).tolist(),
              'phase_rad':np.angle(np.exp(1j*(np.array(c['phase_rad'])-2*np.pi*removed*(c['time_reference_s']-meta.get('rate_applied_reference_s',0.))))).tolist()}
    v,w=apply_calibration(d['visibilities'],d['weights'],d['pairs'],residual,d['times_s'],d['frequencies_hz'],allow_extrapolation)
    cube={k:d[k] for k in ('pairs','times_s','frequencies_hz','uvw_lambda','integration_s')}
    cube.update({'visibilities':v,'weights':w})
    total=w.sum(axis=1);continuum=np.divide((v*w).sum(axis=1),total,out=np.zeros(total.shape,complex),where=total>0)
    # Current weights are channel-independent; reject other profiles for now.
    if not np.allclose(w,w[:,0:1,:],rtol=1e-6,atol=0): raise ValueError('continuum export needs channel-independent weights')
    config=json.loads(json.dumps(meta['config']));center=float(d['frequencies_hz'].mean())
    config['observation']['frequency_hz']=center
    times=Time(meta['time_origin_utc'])+d['times_s']*u.s
    g=geometry_at_times(config,times,filter_elevation=False)
    partial.mkdir(parents=True)
    try:
        save_spectral(partial/'calibrated.npz',cube,{**meta,'visibility_unit':'Jy','calibration_applied':True})
        write_fitsidi(partial/'visibility.fits',g,continuum,total,config,
                      {'calibration':'Known point calibrator, constant station response'},integration_s=d['integration_s'])
        summary={'state':'complete','visibility_unit':'Jy','rows':int(continuum.size)}
        (partial/'summary.json').write_text(json.dumps(summary)+'\n');partial.rename(out)
        return summary
    except Exception as exc:
        (partial/'failure.json').write_text(json.dumps({'state':'incomplete','error_type':type(exc).__name__})+'\n')
        raise
