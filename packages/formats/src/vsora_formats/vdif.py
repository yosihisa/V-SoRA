"""Strict single-thread 8-bit complex VDIF adapter using Baseband.

Missing frames are rejected; known invalid frames retain their time and mask.
"""
import json
from pathlib import Path
import numpy as np
import astropy.units as u
from astropy.time import Time
from baseband import vdif


def write_vdif(path, data, start_utc, sample_rate_hz, station_id, scale=1., samples_per_frame=4096, valid=None,
               voltage_unit='sqrt(Jy)'):
    x=np.asarray(data)
    if x.ndim!=1 or not np.iscomplexobj(x) or not np.isfinite(x).all() or not np.isfinite(scale) or scale<=0:
        raise ValueError('finite complex samples and positive scale required')
    if len(x)==0 or len(x)%samples_per_frame or sample_rate_hz%samples_per_frame:
        raise ValueError('whole frames and integer frames/second required')
    if not 0<=station_id<=65535: raise ValueError('invalid VDIF station ID')
    if sample_rate_hz<=0: raise ValueError('invalid sample rate')
    if voltage_unit not in ('sqrt(Jy)','ADC'): raise ValueError('explicit supported voltage unit required')
    validity=np.ones(len(x),bool) if valid is None else np.asarray(valid,dtype=bool)
    if validity.shape!=x.shape: raise ValueError('valid mask shape mismatch')
    frames=validity.reshape(-1,samples_per_frame)
    if np.any(frames.any(axis=1)!=frames.all(axis=1)):
        raise ValueError('VDIF invalid flag requires complete invalid frames')
    start=Time(start_utc,scale='utc')
    if abs((start.unix-round(start.unix)))>1e-7:
        raise ValueError('initial adapter requires UTC integer-second start')
    p=Path(path)
    if p.exists() or p.with_suffix('.json').exists(): raise FileExistsError(p.name)
    p.parent.mkdir(parents=True,exist_ok=True)
    normalized=x/scale
    clipped=((np.abs(normalized.real)>127.5/35.5)|(np.abs(normalized.imag)>127.5/35.5))
    with vdif.open(p,'ws',sample_rate=sample_rate_hz*u.Hz,samples_per_frame=samples_per_frame,
                   nchan=1,nthread=1,complex_data=True,bps=8,edv=0,station=station_id,time=start) as writer:
        for i in range(len(frames)):
            writer.write(normalized[i*samples_per_frame:(i+1)*samples_per_frame],valid=bool(frames[i,0]))
    metadata={'schema_version':1,'sample_rate_hz':sample_rate_hz,'start_utc':start.isot+'Z',
              'station_numeric_id':station_id,'sample_count':len(x),'samples_per_frame':samples_per_frame,
              'complex':True,'bits_per_component':8,'edv':0,'thread_id':0,
              'decoded_voltage_scale':scale,'decoded_voltage_unit':voltage_unit,
              'scale_unit':'simulated calibrated sqrt(Jy)' if voltage_unit=='sqrt(Jy)' else 'uncalibrated ADC counts',
              'quantization':'Baseband/mark5access offset binary; decoded=(byte-127.5)/35.5',
              'clipped_fraction':float(clipped.mean()),'invalid_frame_count':int((~frames[:,0]).sum())}
    p.with_suffix('.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return metadata


def iter_vdif_frames(path, sample_rate_hz, expected_station_id=None, scale=1.):
    """Yield validated frames with bounded memory; reject discontinuous headers."""
    if not np.isfinite(sample_rate_hz) or not np.isfinite(scale) or sample_rate_hz<=0 or scale<=0:
        raise ValueError('positive finite sample rate/scale required')
    first=None;expected=None;signature=None;sample_index=0
    # Inspect length separately to distinguish EOF from a truncated final frame.
    length=Path(path).stat().st_size
    with vdif.open(path,'rb') as reader:
        while reader.tell()<length:
            frame=reader.read_frame(verify=True)
            h=frame.header
            if not h.complex_data or h.bps!=8 or h.nchan!=1 or h['thread_id']!=0 or h.edv!=0:
                raise ValueError('only EDV0 8-bit complex single-channel/thread supported')
            if expected_station_id is not None and h['station_id']!=expected_station_id:
                raise ValueError('station ID mismatch')
            sig=(h['station_id'],h.samples_per_frame,h.frame_nbytes)
            if signature is not None and sig!=signature: raise ValueError('VDIF header changes midstream')
            signature=sig
            if sample_rate_hz%h.samples_per_frame: raise ValueError('noninteger frame rate')
            time=h.get_time(frame_rate=sample_rate_hz/h.samples_per_frame*u.Hz)
            if first is None: first=time;expected=time
            if abs((time-expected).to_value(u.s))>1e-7:
                raise ValueError('missing, duplicate or misordered VDIF frame')
            expected=expected+h.samples_per_frame/sample_rate_hz*u.s
            yield {'data':np.asarray(frame.data).reshape(-1).astype(complex)*scale,
                   'valid':np.full(h.samples_per_frame,frame.valid,dtype=bool),
                   'time':time,'sample_index':sample_index,'station_id':h['station_id']}
            sample_index+=h.samples_per_frame
    if first is None: raise ValueError('empty VDIF')


def read_vdif(path, sample_rate_hz, expected_station_id=None, scale=1.):
    """Convenience read for short datasets; long workflows use the iterator."""
    chunks=[];masks=[];metadata=None
    for frame in iter_vdif_frames(path,sample_rate_hz,expected_station_id,scale):
        if metadata is None: metadata={'start_utc':frame['time'].isot+'Z','station_id':frame['station_id']}
        chunks.append(frame['data']);masks.append(frame['valid'])
    return np.concatenate(chunks),np.concatenate(masks),metadata
