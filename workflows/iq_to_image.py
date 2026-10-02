"""Time-separated short snapshots through IQ/VDIF/FX/IDI/imaging.

Exposure is the actual sample duration, never the large snapshot spacing.
"""
import argparse
import copy
import json
from pathlib import Path
import numpy as np
import astropy.units as u
from astropy.time import Time
from vsora_observation import load_config
from vsora_observation.geometry import observation_geometry
from vsora_simulator.sky import synthetic_sky
from vsora_simulator.iq import generate_iq
from vsora_correlator.fx import fx_correlate
from vsora_formats.vdif import write_vdif,read_vdif
from vsora_formats.fitsidi import write_fitsidi,read_fitsidi
from vsora_imaging.__main__ import image_visibility,compare_models
from astropy.io import fits
from workflows.compare_arrays import layout


def run(output,snapshots=16,blocks=4096,receiver_sefd_jy=10000):
    root=Path(__file__).resolve().parents[1]
    out=Path(output)
    if out.exists(): raise FileExistsError('use a new output directory')
    out.mkdir(parents=True)
    config=load_config(root/'configs/experiments/ideal-point.json')
    config['source']['model']='casa'
    config['observation']['duration_s']=14400.
    config['observation']['integration_s']=14400./snapshots
    config['noise']['enabled']=True
    config['stations']=[{'id':f'ST{i+1:02d}','enu_m':p,'sefd_jy':receiver_sefd_jy}
                        for i,p in enumerate(layout(8,'spread'))]
    sky=synthetic_sky(config);scheduled=observation_geometry(config)
    fs=2048000;fc=1.42e9;nfft=64;n=len(config['stations']);duration=nfft*blocks/fs
    if blocks%64: raise ValueError('whole 4096-sample frames required')
    values=[];weights=[];times=[];uvw=[];comparisons=[];expectations=[];eop=[]
    for k,mjd in enumerate(scheduled['times_mjd']):
        # Scheduled midpoints become short snapshot starts; recompute geometry
        # at the actual sample midpoint rather than label 900 seconds exposure.
        start=Time(mjd,format='mjd',scale='utc').isot[:19]+'Z'
        c=copy.deepcopy(config);c['observation'].update({'start_utc':start,'duration_s':duration,'integration_s':duration})
        g=observation_geometry(c)
        delay=np.zeros(n)
        for b,(i,j) in enumerate(g['pairs']):
            if i==0: delay[j]=g['uvw_lambda'][0,b,2]/fc
        samples,expected=generate_iq(g['uvw_lambda'][0],g['pairs'],sky,16,[receiver_sefd_jy]*n,
                                     fs,fc,nfft,blocks,42+k,delay)
        decoded=[];valid=[]
        for station in range(n):
            scale=np.sqrt((sky.sum()+receiver_sefd_jy)/2)/.6
            p=out/f'snapshot-{k:03d}'/f'ST{station+1:02d}.vdif'
            write_vdif(p,samples[station],start,fs,station+1,scale)
            x,mask,_=read_vdif(p,fs,station+1,scale)
            decoded.append(x);valid.append(mask)
        correlated=fx_correlate(np.array(decoded),fs,nfft,fc,delay,np.array(valid))
        # Narrow-band continuum approximation. Its effective frequency is the
        # arithmetic mean of the FFT bins, not exactly the configured RF center.
        v=correlated['vis_jy'].mean(axis=0)
        effective_frequency=float(correlated['frequencies_hz'].mean())
        sigma2=(sky.sum()+receiver_sefd_jy)**2/(2*fs*duration)
        values.append(v);weights.append(np.full(len(v),1/sigma2))
        expectations.append(expected.mean(axis=0))
        times.append(g['times_mjd'][0]);uvw.append(g['uvw_lambda'][0]*effective_frequency/fc)
        eop.append(g['eop_status'])
        comparisons.append(float(np.linalg.norm(v-expected.mean(axis=0))/np.linalg.norm(expected.mean(axis=0))))
        print(f'snapshot {k+1}/{snapshots}: exposure={duration:.3f}s, relative continuum error={comparisons[-1]:.4f}',flush=True)
    vis=np.array(values);weight=np.array(weights)
    geometry={'uvw_lambda':np.array(uvw),'pairs':scheduled['pairs'],'times_mjd':np.array(times),
              'station_ecef_m':scheduled['station_ecef_m']}
    config['observation']['frequency_hz']=effective_frequency
    metadata={'config':config,'frequency_hz':effective_frequency,'actual_exposure_per_snapshot_s':duration,
              'total_exposure_s':len(values)*duration,'eop_status':eop,
              'assumptions':['stationary FFT-periodic snapshots; known geometric delay',
                             'no clock/LO drift; primary beam unity',
                             'snapshot spacing is not integration time',
                             'weights approximate including sky power; no full self-noise covariance']}
    idi=out/'visibility.fits'
    write_fitsidi(idi,geometry,vis,weight,config,metadata,integration_s=duration)
    summary=image_visibility(idi,out/'imaging',clean_radius_arcsec=220)
    model=fits.getdata(out/'imaging/model.fits').astype(float)
    metrics,_,_=compare_models(sky,model,16)
    summary.update(metrics);summary.update(metadata)
    summary['mean_snapshot_visibility_error']=float(np.mean(comparisons))
    summary['idi_roundtrip_relative_error']=float(np.linalg.norm(read_fitsidi(idi)['vis_jy']-vis)/np.linalg.norm(vis))
    np.save(out/'truth.npy',sky)
    np.savez_compressed(out/'expected.npz',vis_jy=np.array(expectations),uvw_lambda=geometry['uvw_lambda'])
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:summary[k] for k in ['nrmse','correlation','model_flux_ratio','idi_roundtrip_relative_error','total_exposure_s']},indent=2))
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    p.add_argument('--snapshots',type=int,default=16);p.add_argument('--blocks',type=int,default=4096)
    a=p.parse_args();run(a.output,a.snapshots,a.blocks)
