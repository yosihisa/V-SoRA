"""Cas A IQ, unknown station responses, model-assisted self-calibration.

This uses the generating shape as a calibration prior; image agreement is a
software consistency test, not independent reconstruction of an unknown sky.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import astropy.units as u
from astropy.time import Time
from astropy.io import fits
from vsora_observation import load_config
from vsora_observation.geometry import geometry_at_times
from vsora_simulator.sky import synthetic_sky
from vsora_simulator.iq import generate_iq
from vsora_simulator.visibility import direct_visibility
from vsora_correlator.fx import fx_correlate_series,remove_fringe_rate
from vsora_correlator.fringe import solve_fringe,apply_calibration
from vsora_formats.vdif import write_vdif,read_vdif
from vsora_formats.fitsidi import write_fitsidi
from vsora_imaging.__main__ import image_visibility,compare_models
from workflows.compare_arrays import layout


def run(output,receiver_sefd_jy=1000.,snapshots=16,pilot_seconds=.128):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1];c=load_config(root/'configs/experiments/ideal-point.json')
    c['source']['model']='casa';c['noise']['enabled']=True
    c['observation']['duration_s']=14400;c['observation']['integration_s']=900
    c['stations']=[{'id':f'ST{i+1:02d}','enu_m':pos,'sefd_jy':receiver_sefd_jy} for i,pos in enumerate(layout(8,'spread'))]
    image=synthetic_sky(c);fs=2048000;fc=1.42e9;nf=128;blocks=64
    groups=round(pilot_seconds*fs/(nf*blocks));span=nf*blocks*groups/fs
    if groups<8 or abs(span-pilot_seconds)>1e-9: raise ValueError('pilot must be >=8 integrations and a multiple of 4ms')
    # Dense short pilot around each independent sparse synthesis snapshot.
    offsets=(np.arange(snapshots)+.5)*14400/snapshots
    times=Time(c['observation']['start_utc'])+(offsets+span/2)*u.s
    g=geometry_at_times(c,times);p=g['pairs'];ref=5
    de=np.array([0,2.3e-6,-1.7e-6,.38e-6,3.1e-6,-2.5e-6,.7e-6,-.9e-6])
    rate=np.array([0,17.3,-11.7,26.1,8.2,-.4,1.7,-3.1])
    amp=np.array([1,.8,1.2,.95,1.05,.9,1.1,.85])*4
    results=[];vis=[];weights=[];exposures=[];frequencies=None
    for index in range(snapshots):
        shot=out/f'shot-{index:02d}';shot.mkdir()
        x,_=generate_iq(g['uvw_lambda'][index],p,image,16,np.full(8,receiver_sefd_jy),fs,fc,nf,blocks*groups,400+index,
                       g['station_delay_s'][index]+de)
        samplet=np.arange(x.shape[1])/fs;fref=fc-fs/(2*nf)
        phase=np.random.default_rng(600+index).uniform(-np.pi,np.pi,8)
        x*=amp[:,None]*np.exp(1j*(phase[:,None]-2*np.pi*fref*de[:,None]+
                                2*np.pi*rate[:,None]*(samplet[None,:]-span/2)))
        decoded=[];masks=[]
        start=(times[index]-span/2*u.s).isot+'Z'
        for station in range(8):
            path=shot/f'station{station+1}.vdif';scale=2*np.sqrt(np.mean(abs(x[station])**2)/2)
            write_vdif(path,x[station],start,fs,station+1,scale,voltage_unit='ADC')
            data,ok,_=read_vdif(path,fs,station+1,scale);decoded.append(data);masks.append(ok)
        raw=np.array(decoded);ok=np.array(masks)
        def correlate(samples):
            r=fx_correlate_series(samples,fs,nf,blocks,fc,valid=ok)
            field=np.exp(-2j*np.pi*r['frequencies_hz'][:,None]*g['station_delay_s'][index][None,:])
            r['vis_jy']*=field[None,:,p[:,0]]*field[None,:,p[:,1]].conj()
            return r
        r=correlate(raw);frequency=r['frequencies_hz']
        model=direct_visibility(g['uvw_lambda'][index][None,:,:]*(frequency[:,None,None]/fc),image,16)
        model=np.broadcast_to(model,r['vis_jy'].shape)
        initial=solve_fringe(r['vis_jy'],model,r['weights'],p,r['times_s'],frequency,ref)
        rerun=correlate(remove_fringe_rate(raw,fs,initial['rate_hz'],time_reference_s=initial['time_reference_s']))
        final=solve_fringe(rerun['vis_jy'],model,rerun['weights'],p,rerun['times_s'],frequency,ref)
        corrected,w=apply_calibration(rerun['vis_jy'],rerun['weights'],p,final,rerun['times_s'],frequency)
        total=w.sum(axis=(0,1));mean=np.sum(corrected*w,axis=(0,1))/total
        expected=np.sum(model*w,axis=(0,1))/total
        relative=float(np.linalg.norm(mean-expected)/np.linalg.norm(expected))
        vis.append(mean);weights.append(total);exposures.append(span);frequencies=frequency
        results.append({'snapshot':index,'recorded_seconds':span,'mean_visibility_relative_error':relative,
                        'delay_max_error_s':float(np.max(abs(np.array(final['delay_s'])-(de-de[ref])))),
                        'rate_max_error_hz':float(np.max(abs(np.array(initial['rate_hz'])+np.array(final['rate_hz'])-(rate-rate[ref])))),
                        'min_initial_peak_snr':min(d['coarse_peak_snr'] for d in initial['reference_detections'])})
        print(f'Snapshot {index+1}/{snapshots}: visibility relative error {relative:.4f}',flush=True)
    effective=float(frequencies.mean());c['observation']['frequency_hz']=effective
    g['uvw_lambda']*=effective/fc
    write_fitsidi(out/'visibility.fits',g,np.array(vis),np.array(weights),c,
                  {'calibration':'Model-assisted Cas A self-calibration with generating shape',
                   'total_recorded_seconds':snapshots*span},integration_s=np.array(exposures)[:,None])
    restored=image_visibility(out/'visibility.fits',out/'imaging',220)
    metrics,truth,model=compare_models(image,fits.getdata(out/'imaging/model.fits'),16)
    summary={'snapshots':snapshots,'synthesis_span_s':14400,'total_recorded_seconds':snapshots*span,
             'receiver_sefd_jy':receiver_sefd_jy,'reference_station':ref,'calibration_kind':'Model-assisted self-calibration',
             'metrics':metrics,'imaging':restored,'snapshot_results':results,
             'limitations':['Generating Cas A shape/flux reused as calibration prior; no independent sky recovery claim',
                            'Stationary FFT-periodic IQ snapshots; gaps are not recorded integration',
                            'No ADC drift, RFI, primary beam or bandpass in this experiment']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(10,3))
    for ax,title,array in zip(axes,['Prior / truth, common beam','Recovered, common beam','Difference'],[truth,model,model-truth]):
        ax.imshow(array,origin='lower',cmap='inferno');ax.set_title(title)
    fig.tight_layout();fig.savefig(out/'comparison.png',dpi=140);plt.close(fig)
    print(json.dumps({'metrics':metrics,'total_recorded_seconds':snapshots*span},indent=2))
    if metrics['nrmse']>.15 or not restored['converged']: raise AssertionError('Cas A model-assisted consistency criterion failed')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--receiver-sefd-jy',type=float,default=1000)
    p.add_argument('--snapshots',type=int,default=16);p.add_argument('--pilot-seconds',type=float,default=.128)
    a=p.parse_args();run(a.output,a.receiver_sefd_jy,a.snapshots,a.pilot_seconds)
