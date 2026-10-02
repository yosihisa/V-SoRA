"""IQ with unknown LO/delay -> VDIF -> short FX -> fitted correction."""
import argparse
import json
from pathlib import Path
import numpy as np
from vsora_simulator.iq import generate_iq
from vsora_correlator.fx import fx_correlate_series,remove_fringe_rate
from vsora_correlator.fringe import solve_fringe,apply_calibration,save_calibration
from vsora_formats.vdif import write_vdif,read_vdif
from vsora_formats.spectral import save_spectral


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    fs=2048000;fc=1.42e9;nfft=128;groups=64;blocks=128;n=4
    p=np.array([(i,j) for i in range(n) for j in range(i+1,n)])
    image=np.zeros((16,16));image[8,8]=1000
    de=np.array([0,2.3e-6,-1.7e-6,.38e-6]);ra=np.array([0,17.3,-11.7,26.1])
    ph=np.array([0,.4,-.7,1.4]);amp=np.array([1.2,.8,1.1,.9])
    x,_=generate_iq(np.zeros((len(p),3)),p,image,16,np.full(n,1e4),fs,fc,nfft,groups*blocks,90,de)
    t=np.arange(x.shape[1])/fs;tm=x.shape[1]/(2*fs);fref=fc-fs/(2*nfft)
    x*=amp[:,None]*np.exp(1j*(ph[:,None]-2*np.pi*fref*de[:,None]+2*np.pi*ra[:,None]*(t[None,:]-tm)))
    decoded=[];masks=[];clipping=[]
    for station in range(n):
        path=out/f'station{station+1}.vdif';valid=np.ones(x.shape[1],bool)
        if station==1: valid[12*4096:13*4096]=False
        scale=2*np.sqrt(np.mean(abs(x[station])**2)/2)
        meta=write_vdif(path,x[station],'2026-10-01T08:00:00Z',fs,station+1,scale,valid=valid)
        data,ok,_=read_vdif(path,fs,station+1,scale);decoded.append(data);masks.append(ok);clipping.append(meta['clipped_fraction'])
    result=fx_correlate_series(np.array(decoded),fs,nfft,blocks,fc,valid=np.array(masks))
    model=np.ones(result['vis_jy'].shape)*1000
    cal=solve_fringe(result['vis_jy'],model,result['weights'],p,result['times_s'],result['frequencies_hz'])
    def mean(v,w): return np.sum(v*w,axis=(0,1))/np.sum(w,axis=(0,1))
    initial_corrected,initial_w=apply_calibration(result['vis_jy'],result['weights'],p,cal,result['times_s'],result['frequencies_hz'])
    # The initial estimate cannot recover rate loss inside 8 ms averages.
    # Rephase the recorded voltages and repeat FX, then refine residual gains.
    rephased=remove_fringe_rate(np.array(decoded),fs,cal['rate_hz'],time_reference_s=cal['time_reference_s'])
    refined=fx_correlate_series(rephased,fs,nfft,blocks,fc,valid=np.array(masks))
    residual_cal=solve_fringe(refined['vis_jy'],model,refined['weights'],p,refined['times_s'],refined['frequencies_hz'])
    corrected,w=apply_calibration(refined['vis_jy'],refined['weights'],p,residual_cal,refined['times_s'],refined['frequencies_hz'])
    total_cal={**residual_cal,'rate_hz':(np.array(cal['rate_hz'])+np.array(residual_cal['rate_hz'])).tolist()}
    before=mean(result['vis_jy'],result['weights']);after=mean(corrected,w)
    summary={'stations':n,'sample_rate_hz':fs,'fft_length':nfft,'short_integration_s':nfft*blocks/fs,
             'duration_s':x.shape[1]/fs,'channels':nfft,'time_samples':groups,'receiver_sefd_jy':1e4,
             'injected_delay_s':de.tolist(),'injected_rate_hz':ra.tolist(),
             'delay_max_error_s':float(np.max(abs(np.array(total_cal['delay_s'])-de))),
             'rate_max_error_hz':float(np.max(abs(np.array(total_cal['rate_hz'])-ra))),
             'amplitude_max_relative_error':float(np.max(abs(np.array(total_cal['amplitude'])/amp-1))),
             'before_mean_relative_error':float(np.linalg.norm(before-1000)/np.sqrt(len(p))/1000),
             'after_single_pass_relative_error':float(np.linalg.norm(mean(initial_corrected,initial_w)-1000)/np.sqrt(len(p))/1000),
             'after_mean_relative_error':float(np.linalg.norm(after-1000)/np.sqrt(len(p))/1000),
             'clipped_fraction':clipping,'missing_frame_policy':'known invalid frame remains in timeline with zero weights',
             'limitations':['FFT-periodic stationary sky generation, not a continuous propagation model',
                            'Measured total-power weights approximate; known 1000 Jy calibrator sets flux',
                            'Two-pass estimate and pre-FFT rephasing; within-FFT bin leakage remains']}
    cube={k:result[k] for k in ('vis_jy','weights','pairs','times_s','frequencies_hz')}
    cube['uvw_lambda']=np.zeros((*cube['vis_jy'].shape,3))
    save_spectral(out/'spectral.npz',cube,{'time_origin_utc':'2026-10-01T08:00:00Z','unit':'Jy','model':'phase-center point'})
    save_calibration(out/'calibration.json',total_cal)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
    if summary['delay_max_error_s']>2e-8 or summary['rate_max_error_hz']>.08 or summary['after_mean_relative_error']>.03:
        raise AssertionError('IQ fringe calibration failed')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(p.parse_args().output)
