"""Bounded VDIF clock/geometric alignment for short reference chunks."""
import json
from pathlib import Path
import numpy as np
import astropy.units as u
from astropy.time import Time
from scipy.signal import firwin,lfilter
from vsora_formats.vdif import iter_vdif_frames
from vsora_formats.spectral import save_spectral
from vsora_observation.geometry import geometry_at_times
from .clock import interpolate_samples
from .fx import fx_correlate_series
from .session import load_session


class SampleBuffer:
    def __init__(self,path,nominal_rate,station_id,scale,actual_rate):
        self.reader=iter_vdif_frames(path,nominal_rate,station_id,scale)
        self.taps=firwin(65,.35*nominal_rate,fs=actual_rate,window=('kaiser',8.6))
        self.state=np.zeros(64,complex);self.history=np.zeros(64,bool)
        self.data=np.empty(0,complex);self.valid=np.empty(0,bool)
        self.first=0;self.next=0;self.maximum=0

    def query(self,positions):
        positions=np.asarray(positions)+32 # compensate linear-phase FIR delay
        minimum=int(np.floor(positions.min()))-32
        maximum=int(np.floor(positions.max()))+33
        if minimum<0 or minimum<self.first: raise ValueError('query before available guard samples')
        while self.first+len(self.data)<=maximum:
            try: frame=next(self.reader)
            except StopIteration: raise ValueError('input ends before requested aligned chunk') from None
            filtered,self.state=lfilter(self.taps,[1],frame['data'],zi=self.state)
            support=np.r_[self.history,frame['valid']]
            good=np.convolve(support.astype(int),np.ones(65,dtype=int),'valid')==65
            self.history=support[-64:]
            if len(self.data)==0: self.first=self.next
            self.data=np.r_[self.data,filtered];self.valid=np.r_[self.valid,good]
            self.next+=len(filtered);self.maximum=max(self.maximum,len(self.data))
            if self.first+len(self.data)<=minimum:
                self.data=np.empty(0,complex);self.valid=np.empty(0,bool);self.first=self.next
            elif minimum>self.first:
                discard=minimum-self.first
                self.data=self.data[discard:];self.valid=self.valid[discard:];self.first=minimum
        result,good=interpolate_samples(self.data,positions-self.first,self.valid)
        discard=max(0,int(np.floor(positions[-1]))-32-self.first)
        self.data=self.data[discard:];self.valid=self.valid[discard:];self.first+=discard
        return result,good

    def close(self): self.reader.close()


def correlate_aligned(manifest,clock_model,output,integrations,start_offset_s=.002):
    c=load_session(manifest);config=c['_config'];fs=c['sample_rate_hz']
    if not c['phase_center_correction']: raise ValueError('aligned mode requires explicit phase-center correction')
    ns=c['fft_length']*c['blocks_per_integration'];span=ns*integrations/fs
    if not isinstance(integrations,int) or not 8<=integrations<=256 or span>1:
        raise ValueError('aligned reference chunk requires 8..256 integrations and <=1 second')
    if not np.isfinite(start_offset_s) or start_offset_s<0: raise ValueError('nonnegative start offset required')
    clock=json.loads(Path(clock_model).read_text())
    if set(clock)!={'schema_version','max_abs_baseband_hz','stations'} or clock['schema_version']!=1:
        raise ValueError('unsupported clock model')
    stations=clock['stations'];band=clock['max_abs_baseband_hz']
    if len(stations)!=len(c['stations']) or not 0<band<=.3*fs: raise ValueError('invalid station count/band guard')
    buffers=[]
    for measured,station in zip(stations,c['stations']):
        if set(measured)!={'id','input_start_offset_s','actual_sample_rate_hz'} or measured['id']!=station['id']:
            raise ValueError('clock model station order differs')
        actual=measured['actual_sample_rate_hz'];offset=measured['input_start_offset_s']
        if not np.isfinite(actual) or not np.isfinite(offset) or abs(actual/fs-1)>.001:
            raise ValueError('clock model must be finite and within 1000 ppm')
        buffers.append(SampleBuffer(c['_root']/station['vdif'],fs,station['station_numeric_id'],station['decoded_voltage_scale'],actual))
    out=Path(output);partial=out.with_name(out.name+'.partial')
    if out.exists() or partial.exists(): raise FileExistsError('choose a new output directory')
    partial.mkdir(parents=True)
    origin=Time(config['observation']['start_utc']);offsets=start_offset_s+(np.arange(integrations)+.5)*ns/fs
    g=geometry_at_times(config,origin+offsets*u.s,filter_elevation=False)
    edges=np.array([start_offset_s,start_offset_s+span])
    endpoint=geometry_at_times(config,origin+edges*u.s,filter_elevation=False)['station_delay_s']
    positions=np.array([s['enu_m'] for s in config['stations']])
    if np.linalg.norm(positions[:,None]-positions[None,:],axis=-1).max()>600.001:
        raise ValueError('aligned reference geometry is limited to 600m')
    results=[]
    try:
        for index in range(integrations):
            t=start_offset_s+(index*ns+np.arange(ns))/fs;data=[];valid=[]
            for station,b in enumerate(buffers):
                delay=np.interp(t,edges,endpoint[:,station])
                measured=stations[station]
                queries=(t-delay-measured['input_start_offset_s'])*measured['actual_sample_rate_hz']
                x,ok=b.query(queries)
                data.append(x*np.exp(-2j*np.pi*config['observation']['frequency_hz']*delay));valid.append(ok)
            r=fx_correlate_series(np.array(data),fs,c['fft_length'],c['blocks_per_integration'],
                                  config['observation']['frequency_hz'],valid=np.array(valid),time_offset_s=t[0])
            r['weights'][:,abs(r['frequencies_hz']-config['observation']['frequency_hz'])>band]=0
            r['weights']*=g['elevation_valid'][index]
            results.append(r)
        f=results[0]['frequencies_hz']
        cube={'visibilities':np.array([r['vis_jy'][0] for r in results]),'weights':np.array([r['weights'][0] for r in results]),
              'pairs':g['pairs'],'times_s':offsets,'frequencies_hz':f,
              'uvw_lambda':g['uvw_lambda'][:,None,:,:]*(f[None,:,None,None]/config['observation']['frequency_hz']),
              'integration_s':np.array([r['integration_s'][0] for r in results])}
        meta={'config':config,'time_origin_utc':origin.isot+'Z','visibility_unit':'ADC^2' if c['voltage_unit']=='ADC' else 'Jy',
              'phase_center_corrected':True,'rate_applied_hz':[0.]*len(stations),'rate_applied_reference_s':0.,
              'clock_mapping_applied':True,'filter':'65-tap Kaiser lowpass; group delay compensated',
              'max_abs_baseband_hz':band,'eop_status':g['eop_status']}
        save_spectral(partial/'shard-00000.npz',cube,meta)
        summary={'state':'complete','integrations':integrations,'recorded_span_s':span,'start_offset_s':start_offset_s,
                 'station_max_buffer_samples':[b.maximum for b in buffers],'samples_per_integration':ns,
                 'clock_model':'Supplied linear ADC mapping; no automatic weak-source clock recovery',
                 'geometry':'Sample alignment and RF rephasing; linear delay over <=1s, <=600m',
                 'weight_note':'Total-power noise approximation; band-dependent noise not yet fully modeled'}
        (partial/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');partial.rename(out)
        return summary
    except Exception as exc:
        (partial/'failure.json').write_text(json.dumps({'state':'incomplete','error_type':type(exc).__name__})+'\n')
        raise
    finally:
        for b in buffers: b.close()
