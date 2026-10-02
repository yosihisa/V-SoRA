"""Sparse extended-sky continuous VDIF synthesis; all assumptions explicit."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import numpy as np
import astropy.units as u
from astropy.time import Time
from vsora_observation import load_config
from vsora_observation.geometry import geometry_at_times
from vsora_simulator.sky import synthetic_sky
from vsora_simulator.visibility import direct_visibility
from vsora_formats.vdif import write_vdif
from vsora_correlator.closure_pipeline import process_closure_session
from vsora_imaging.synthesis import image_synthesis
from vsora_imaging.experiment import compare_relative
from workflows.compare_arrays import layout


def extended_fixture(output,start_utc,seed=24,model='casa',sefd_jy=10000.):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    c=load_config(Path(__file__).resolve().parents[1]/'configs/experiments/ideal-point.json')
    c['source']['model']=model;c['image']['pixels']=32;c['observation'].update(start_utc=start_utc,duration_s=1.04,integration_s=.004)
    c['stations']=[{'id':f'ST{i+1:02d}','enu_m':p,'sefd_jy':sefd_jy} for i,p in enumerate(layout(8,'spread'))]
    from vsora_observation import validate_config
    c=validate_config(c)
    sky_image=synthetic_sky(c);fs=2048000;fc=1.42e9;ns=520*4096;span=ns/fs
    origin=Time(start_utc);g=geometry_at_times(c,origin+np.array([0,.5,span])*u.s,filter_elevation=False)
    p=g['pairs'];visibility=direct_visibility(g['uvw_lambda'][1],sky_image,16)
    covariance=np.eye(8,dtype=complex)*(1000+sefd_jy)
    covariance[p[:,0],p[:,1]]=visibility;covariance[p[:,1],p[:,0]]=visibility.conj()
    factor=np.linalg.cholesky(covariance)
    frequency=np.fft.fftfreq(ns,1/fs);active=abs(frequency)<=.25*fs
    rng=np.random.default_rng(seed)
    white=(rng.normal(size=(8,ns))+1j*rng.normal(size=(8,ns)))/np.sqrt(2)
    spectrum=factor @ np.fft.fft(white,axis=1)
    del white
    spectrum*=active[None]/np.sqrt(active.mean())
    rates=np.array([0,17.3,-11.7,26.1,8.2,-.4,1.7,-3.1])+rng.normal(0,.05,8)
    rates-=rates[0]
    gains=np.exp(rng.uniform(-1.4,1.4,8)+1j*rng.uniform(-np.pi,np.pi,8))
    t=np.arange(ns)/fs;stations=[];clocks=[]
    for i in range(8):
        delay=np.interp(t,[0,span],g['station_delay_s'][[0,2],i])
        x=np.fft.ifft(spectrum[i]*np.exp(2j*np.pi*frequency*g['station_delay_s'][1,i]))
        x*=gains[i]*np.exp(2j*np.pi*(fc*delay+rates[i]*t))
        scale=2*np.sqrt(np.mean(abs(x)**2)/2);name=f'station-{i+1}.vdif'
        write_vdif(out/name,x,start_utc,fs,i+1,scale,voltage_unit='ADC')
        stations.append({'id':c['stations'][i]['id'],'vdif':name,'station_numeric_id':i+1,'decoded_voltage_scale':scale})
        clocks.append({'id':c['stations'][i]['id'],'input_start_offset_s':0.,'actual_sample_rate_hz':float(fs)})
    del spectrum
    observed=deepcopy(c);observed['source']['model']='unknown';observed['source'].pop('total_flux_jy')
    (out/'observation.json').write_text(json.dumps(observed,indent=2)+'\n')
    manifest={'schema_version':1,'observation_config':'observation.json','sample_rate_hz':fs,'fft_length':8,
         'blocks_per_integration':1024,'integrations_per_shard':250,'voltage_unit':'ADC','phase_center_correction':True,
         'stations':stations,'spectral_quality':{'channel_weights':True,'min_sk_blocks':128,'sk_bounds':[.3,3.],
          'exclude_rf_ranges_hz':[[fc-fs,fc-.2*fs],[fc+.2*fs,fc+fs]]}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'clock.json').write_text(json.dumps({'schema_version':1,'max_abs_baseband_hz':.2*fs,'stations':clocks},indent=2)+'\n')
    return sky_image,rates,{'model':model,'assumed_flux_jy':1000.,'assumed_sefd_jy':sefd_jy,'input_span_s':span,
        'station_rates_hz':rates.tolist(),'seed':seed,'fft_length':8,'useful_rf_channel_centers':3,
        'narrowband_phase_bound_rad':float(2*np.pi*np.linalg.norm(g['uvw_lambda'][1],axis=1).max()*200*np.pi/(180*3600)*(.25*fs/fc)),
        'limits':'Continuous periodic colored Gaussian with midpoint sky covariance at center RF; supplied exact nominal clocks; fixed broadband station delay, linear RF geometry and LO rate; no real antenna or RFI'}


def run(output,snapshots=8,model='casa',sefd_jy=10000.):
    if not isinstance(snapshots,int) or not 4<=snapshots<=16:raise ValueError('reference synthesis requires 4..16 snapshots')
    out=Path(output)
    if out.exists():raise FileExistsError('new output required')
    out.mkdir(parents=True);paths=[];shots=[];truth=None
    origin=Time('2026-10-02T08:00:00Z');offsets=(np.arange(snapshots)+.5)*14400/snapshots
    for i,offset in enumerate(offsets):
        shot=out/f'shot-{i:02d}';shot.mkdir()
        start=(origin+offset*u.s).isot+'Z'
        truth,rates,generating=extended_fixture(shot/'input',start,24+i,model,sefd_jy)
        try:
            result=process_closure_session(shot/'input/manifest.json',shot/'input/clock.json',shot/'pipeline',
                        pilot_integrations=250,integration_s=1.,starts=1,max_iterations=100)
        except Exception as exc:
            (out/'failure.json').write_text(json.dumps({'state':'incomplete','failed_snapshot':i,
                'completed_snapshots':len(shots),'error_type':type(exc).__name__,
                'generating':generating,'limits':'Failed data are not image validation success'},indent=2)+'\n')
            raise
        error=float(abs(np.array(result['rate_estimate']['station_rates_hz'])-rates).max())
        shots.append({'snapshot':i,'start_utc':start,'maximum_rate_error_hz':error,'generating':generating,
                      'closures':result['closures'],'accepted_rate_baselines':result['rate_estimate']['accepted_baselines']})
        paths.append(shot/'pipeline/correlation/shard-00000.npz')
        print(json.dumps({'snapshot_complete':i+1,'total':snapshots,'maximum_rate_error_hz':error,
                          'phase_closures':result['closures']['phase_valid'],'logamp_closures':result['closures']['logamp_valid']}),flush=True)
        (out/'progress.json').write_text(json.dumps(shots,indent=2)+'\n')
    result=image_synthesis(paths,out/'synthesis',starts=3,max_iterations=2000,min_snr=10.,prior_fwhm_arcsec=240.)
    recovered=np.load(out/'synthesis/rml/relative-model.npy')
    metrics,a,b,registered=compare_relative(truth,recovered,16)
    summary={'type':'vdif_closure_synthesis_validation','snapshots':snapshots,'observation_span_s':14400,
          'coherent_integration_s':1.,'recorded_exposure_per_station_s':float(snapshots),
          'shots':shots,'synthesis':result,'metrics':metrics,
          'limits':'Sparse short VDIF records, not continuous 4h exposure; assumed SEFD; midpoint narrowband sky; Gaussian closure/filtered-noise approximation; truth absent from prior; no real RTL-SDR/Cas A observation'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    np.save(out/'truth-relative.npy',truth/truth.sum())
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(10,3.4))
    for ax,title,image in zip(axes,['Truth: 110 arcsec','VDIF RML: 110 arcsec','VDIF RML: translated'],[a,b,registered]):
        ax.imshow(image,origin='lower',cmap='inferno');ax.set_title(title)
    fig.tight_layout();fig.savefig(out/'comparison.png',dpi=140);plt.close(fig)
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--snapshots',type=int,default=8)
    p.add_argument('--model',choices=['casa','shell'],default='casa');p.add_argument('--sefd-jy',type=float,default=10000.)
    a=p.parse_args();s=run(a.output,a.snapshots,a.model,a.sefd_jy)
    print(json.dumps({'metrics':s['metrics'],'closure_chisq_per_measurement':s['synthesis']['rml']['closure_chisq_per_measurement']},indent=2))
