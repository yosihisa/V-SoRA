"""Continuous band-limited Gaussian sky through actual VDIF and sample alignment."""
import argparse
import json
from pathlib import Path
import numpy as np
import astropy.units as u
from astropy.time import Time
from vsora_observation import load_config
from vsora_observation.geometry import geometry_at_times
from vsora_formats.vdif import write_vdif
from vsora_correlator.closure_pipeline import process_closure_session
from vsora_formats.spectral import load_spectral


def make_fixture(output,seed=23,frame_count=270,pilot_blocks=128):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1];c=load_config(root/'configs/experiments/ideal-point.json')
    # The observing pipeline receives no generating sky type or absolute flux.
    c['source']['model']='unknown';c['source'].pop('total_flux_jy')
    c['image']['pixels']=32
    fs=2048000;fc=1.42e9;ns=frame_count*4096;span=ns/fs;origin=Time(c['observation']['start_utc'])
    edges=np.linspace(0,span,max(1,int(np.ceil(span)))+1)
    geometry=geometry_at_times(c,origin+edges*u.s,filter_elevation=False)
    delay=geometry['station_delay_s'];frequency=np.fft.fftfreq(ns,1/fs)
    active=abs(frequency)<=.25*fs;power_fraction=active.mean()
    rng=np.random.default_rng(seed)
    def gaussian(n):return (rng.normal(size=n)+1j*rng.normal(size=n))/np.sqrt(2)
    sky=np.fft.fft(gaussian(ns))*active*np.sqrt(1000/power_fraction)
    rates=np.array([0.,17.3,-11.7,26.1]);gain=np.array([.4,3,1.5,.75])*np.exp(1j*np.array([0.,.7,-1.1,2.]))
    t=np.arange(ns)/fs;stations=[];clocks=[]
    for i in range(4):
        noise=np.fft.fft(gaussian(ns))*active*np.sqrt(10000/power_fraction)
        d=np.interp(t,edges,delay[:,i]);mid=float(np.interp(span/2,edges,delay[:,i]))
        x=np.fft.ifft((sky+noise)*np.exp(2j*np.pi*frequency*mid))
        x*=gain[i]*np.exp(2j*np.pi*(fc*d+rates[i]*t))
        scale=2*np.sqrt(np.mean(abs(x)**2)/2)
        name=f'station-{i+1}.vdif'
        write_vdif(out/name,x,c['observation']['start_utc'],fs,i+1,scale,voltage_unit='ADC')
        stations.append({'id':c['stations'][i]['id'],'vdif':name,'station_numeric_id':i+1,'decoded_voltage_scale':scale})
        clocks.append({'id':c['stations'][i]['id'],'input_start_offset_s':0.,'actual_sample_rate_hz':float(fs)})
    manifest={'schema_version':1,'observation_config':'observation.json','sample_rate_hz':fs,'fft_length':32,
        'blocks_per_integration':pilot_blocks,'integrations_per_shard':256,'voltage_unit':'ADC','phase_center_correction':True,'stations':stations,
        'spectral_quality':{'channel_weights':True,'min_sk_blocks':128,'sk_bounds':[.3,3.],
                           'exclude_rf_ranges_hz':[[fc-fs,fc-.2*fs],[fc+.2*fs,fc+fs]]}}
    (out/'observation.json').write_text(json.dumps(c,indent=2)+'\n')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'clock.json').write_text(json.dumps({'schema_version':1,'max_abs_baseband_hz':.2*fs,'stations':clocks},indent=2)+'\n')
    return {'seed':seed,'generating_sky':'Common continuous band-limited Gaussian point at phase center, 1000Jy',
        'generating_sefd_jy':10000,'true_rates_hz':rates.tolist(),'input_samples_per_station':ns,'recorded_span_s':span,
        'max_broadband_delay_phase_approximation_rad':float(2*np.pi*.25*fs*np.max(abs(delay[-1]-delay[0]))/2),
        'clock':'Supplied exact nominal clocks; zero sample offsets',
        'band':'Continuous periodic Fourier realization, |f| <= 0.25 Fs; accepted |f| <= 0.2 Fs',
        'limits':'No extended sky, nonlinear clock/LO, RFI or real receiver; RF delay is piecewise linear over <=1s, broadband delay fixed at midpoint'}


def run(output,seed=23):
    out=Path(output)
    if out.exists():raise FileExistsError('new output required')
    out.mkdir(parents=True)
    generating=make_fixture(out/'input',seed)
    result=process_closure_session(out/'input/manifest.json',out/'input/clock.json',out/'pipeline',
                    pilot_integrations=256,integration_s=.3,starts=3,max_iterations=800)
    estimated=np.array(result['rate_estimate']['station_rates_hz']);true=np.array(generating['true_rates_hz'])
    d=load_spectral(out/'pipeline/correlation/shard-00000.npz')
    image=np.load(out/'pipeline/rml/relative-model.npy')
    summary={'type':'vdif_closure_validation','generating':generating,'pipeline':result,
        'maximum_rate_error_hz':float(abs(estimated-true).max()),'final_unit':d['metadata']['visibility_unit'],
        'image_sum':float(image.sum()),'finite_nonnegative_image':bool(np.isfinite(image).all() and np.all(image>=0)),
        'image_peak_yx':list(map(int,np.unravel_index(np.argmax(image),image.shape))),
        'valid_closure_counts':result['closures'],
        'limits':'One short pointing; checks data/clock/rate/unit pipeline, not Cas A imaging fidelity'}
    assert summary['maximum_rate_error_hz']<.05
    assert summary['final_unit']=='ADC^2' and summary['finite_nonnegative_image'] and abs(summary['image_sum']-1)<1e-12
    assert result['closures']['phase_valid']>0 and result['closures']['logamp_valid']>0
    assert not result['absolute_flux_measured'] and not result['absolute_position_measured']
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--seed',type=int,default=23)
    a=p.parse_args();s=run(a.output,a.seed)
    print(json.dumps({k:v for k,v in s.items() if k not in ('pipeline',)},indent=2))
