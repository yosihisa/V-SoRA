"""Stored synthetic stations through the SigMF correlation-only pipeline.

Keep every derived voltage, numerical result and environment record in ignored
outputs/. No real receiver or new image reconstruction is validated here.
"""
import argparse
import json
from pathlib import Path
import resource
import sys
import time

import astropy.units as u
from astropy.time import Time
import numpy as np

from vsora_correlator.closure_pipeline import process_closure_session
from vsora_formats.spectral import load_spectral
from vsora_observation import load_config
from vsora_observation.geometry import geometry_at_times


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def prepare(saved, output, *, frame_count=70):
    if isinstance(frame_count,bool) or not isinstance(frame_count,int) or frame_count<1:
        raise ValueError('positive integer frame_count required')
    saved=Path(saved).resolve(); output=Path(output)
    if output.exists():raise FileExistsError('choose a new fixture directory')
    c=json.loads((saved/'manifest.json').read_text())
    obs=json.loads((saved/'observation.json').read_text())
    clock=json.loads((saved/'clock.json').read_text())
    output.mkdir(parents=True)
    write_json(output/'observation.json',obs);write_json(output/'clock.json',clock)
    c.update(fft_length=32,blocks_per_integration=128)
    legacy=json.loads(json.dumps(c));stations=[]
    for index,station in enumerate(c['stations']):
        path=saved/station['vdif'];payloads=[]
        with path.open('rb') as stream:
            for _ in range(frame_count):
                header=stream.read(32)
                if len(header)!=32:raise ValueError('insufficient stored frames')
                w=np.frombuffer(header,'<u4')
                if int(w[2]&0xffffff)*8!=8224 or w[0]>>30 or w[3]>>26!=39 or w[4]>>24:
                    raise ValueError('stored frame profile or validity differs')
                payload=stream.read(8192)
                if len(payload)!=8192:raise ValueError('short stored payload')
                payloads.append(np.frombuffer(payload,np.uint8).astype(np.int16)*2-255)
        stem=f'station-{index+1}'
        np.concatenate(payloads).astype('<i2').tofile(output/(stem+'.sigmf-data'))
        metadata={'global':{'core:version':'1.2.0','core:datatype':'ci16_le','core:sample_rate':c['sample_rate_hz']},
                  'captures':[{'core:sample_start':0,'core:frequency':obs['observation']['frequency_hz'],
                               'core:datetime':obs['observation']['start_utc']}],'annotations':[]}
        write_json(output/(stem+'.sigmf-meta'),metadata)
        stations.append({'id':station['id'],'sigmf':stem+'.sigmf-meta'})
        legacy['stations'][index].update(vdif=str(path),decoded_voltage_scale=71.)
    c.update(input_format='sigmf_ci16_le',stations=stations)
    write_json(output/'manifest.json',c);write_json(output/'legacy.json',legacy)


def independent_final(manifest, clock, rate_profile, *, start_offset_s=.002):
    """Independent finite signal operations; geometry and fitted rate are supplied."""
    root=Path(manifest).parent;c=json.loads(Path(manifest).read_text())
    config=load_config(root/c['observation_config']);k=json.loads(Path(clock).read_text())
    rate=json.loads(Path(rate_profile).read_text())
    assert rate['type']=='station_rate_only'
    assert rate['station_ids']==[s['id'] for s in c['stations']]
    fs=c['sample_rate_hz'];nf=c['fft_length'];fc=config['observation']['frequency_hz']
    start=start_offset_s;ns=round(.1*fs);assert ns%nf==0
    edges=np.array([start,start+ns/fs])
    delays=geometry_at_times(config,Time(config['observation']['start_utc'])+edges*u.s,
                             filter_elevation=False)['station_delay_s']
    spectra=[];n=np.arange(-32,33)
    for index,(station,measured) in enumerate(zip(c['stations'],k['stations'])):
        words=np.fromfile((root/station['sigmf']).with_suffix('.sigmf-data'),'<i2').reshape(-1,2)
        raw=words[:,0].astype(float)+1j*words[:,1]
        ratio=fs/measured['actual_sample_rate_hz']
        h=.7*ratio*np.sinc(.7*ratio*n)*np.kaiser(65,8.6);h/=h.sum()
        filtered=np.convolve(raw,h)[:len(raw)]
        corrected=np.empty(ns,complex)
        for first in range(0,ns,2048):
            count=min(2048,ns-first);t=start+(first+np.arange(count))/fs
            delay=np.interp(t,edges,delays[:,index])
            q=(t-delay-measured['input_start_offset_s'])*measured['actual_sample_rate_hz']+32
            indices=np.floor(q).astype(int)[:,None]+n
            assert indices.min()>=64 and indices.max()<len(raw)
            d=q[:,None]-indices
            coeff=np.sinc(d)*np.where(abs(d)<=32,.5*(1+np.cos(np.pi*d/32)),0)
            coeff/=coeff.sum(axis=1)[:,None]
            x=(filtered[indices]*coeff).sum(axis=1)
            phase=-2*np.pi*(fc*delay+rate['station_rates_hz'][index]*(t-delay-rate['time_reference_s']))
            corrected[first:first+count]=x*np.exp(1j*phase)
        spectra.append(np.fft.fft(corrected.reshape(-1,nf),axis=1)/np.sqrt(nf))
    order=np.argsort(fc+np.fft.fftfreq(nf,1/fs))
    pairs=[(i,j) for i in range(len(spectra)) for j in range(i+1,len(spectra))]
    return np.array([np.mean(spectra[i]*spectra[j].conj(),axis=0)[order] for i,j in pairs]).T[None]


def run(inputs, output):
    inputs=Path(inputs).resolve();output=Path(output)
    if output.exists():raise FileExistsError('choose a new output directory')
    before=int(Path('/proc/self/statm').read_text().split()[1])*resource.getpagesize()
    began=time.monotonic();output.mkdir(parents=True)
    options=dict(pilot_integrations=64,integration_s=.1,max_rate_hz=100.,correlation_only=True,save_bispectrum=True)
    result=process_closure_session(inputs/'manifest.json',inputs/'clock.json',output/'sigmf',**options)
    process_closure_session(inputs/'legacy.json',inputs/'clock.json',output/'legacy',**options)
    actual=load_spectral(output/'sigmf/correlation/shard-00000.npz')
    reference=independent_final(output/'sigmf/final-manifest.json',inputs/'clock.json',output/'sigmf/rate-only.json')
    np.testing.assert_allclose(actual['visibilities'],reference,rtol=1e-10,atol=1e-7)
    assert result['closures'] is None and result['rml'] is None
    assert result['input_identity']['pipeline_data_full_sha_passes_per_station']==3
    assert result['input_identity']['pipeline_data_hash_file_reads']==12
    assert actual['metadata']['visibility_unit']=='ADC^2' and np.all(actual['valid_fft_count']==6400)
    np.savez(output/'independent.npz',visibilities=reference)
    summary={'state':'complete','input_kind':'distinct stored simulated station code units',
             'real_baselines':0,'new_image_fits':0,'rtol':1e-10,'atol_ADC2':1e-7,
             'independent_visibility_max_abs_error':float(abs(actual['visibilities']-reference).max()),
             'shared_reference':'supplied geometry and saved fitted rates; not independent EOP or statistical calibration',
             'wall_s':time.monotonic()-began,'import_current_RSS_bytes':before,
             'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
             'conservative_additional_peak_bytes':max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024-before)}
    write_json(output/'summary.json',summary)
    write_json(output/'environment.json',{'product_modules':{n:m.__file__ for n,m in sys.modules.items()
        if n.startswith('vsora_') and getattr(m,'__file__',None)}})
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    p.add_argument('--prepare',action='store_true');a=p.parse_args()
    if a.prepare:prepare(a.input,a.output)
    else:print(json.dumps(run(a.input,a.output)))
