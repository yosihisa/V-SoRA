"""Short stationary Gaussian sky -> VDIF -> FX demonstration."""
import argparse
import json
from pathlib import Path
import numpy as np
from vsora_observation import load_config
from vsora_observation.geometry import observation_geometry
from vsora_simulator.sky import synthetic_sky
from vsora_simulator.iq import generate_iq
from vsora_correlator.fx import fx_correlate
from vsora_formats.vdif import write_vdif,read_vdif


def run(output):
    out=Path(output)
    if out.exists(): raise FileExistsError('use a new output directory')
    out.mkdir(parents=True)
    root=Path(__file__).resolve().parents[1]
    config=load_config(root/'configs/experiments/ideal-point.json')
    config['observation']['duration_s']=60.;config['observation']['integration_s']=60.
    config['source']['model']='double'
    sky=synthetic_sky(config);g=observation_geometry(config)
    n=len(config['stations']);fs=2048000;fc=1.42e9
    delays=np.zeros(n)
    for b,(i,j) in enumerate(g['pairs']):
        if i==0: delays[j]=g['uvw_lambda'][0,b,2]/fc
    x,expected=generate_iq(g['uvw_lambda'][0],g['pairs'],sky,16,np.zeros(n),fs,fc,64,4096,42,delays)
    decoded=[];valid=[];scales=[];quantization=[]
    for i in range(n):
        # Stated voltage normalization, not an unrecorded AGC operation.
        scale=np.sqrt(sky.sum()/2)/.6
        path=out/f'ST{i+1:02d}.vdif'
        meta=write_vdif(path,x[i],config['observation']['start_utc'],fs,i+1,scale)
        y,mask,_=read_vdif(path,fs,i+1,scale)
        decoded.append(y);valid.append(mask);scales.append(scale);quantization.append(meta)
    unquantized=fx_correlate(x,fs,64,fc,delays)
    result=fx_correlate(np.array(decoded),fs,64,fc,delays,np.array(valid))
    wrong=fx_correlate(np.array(decoded),fs,64,fc)
    summary={
        'model':'double source, source self-noise, no receiver noise',
        'sample_rate_hz':fs,'fft_length':64,'samples_per_station':x.shape[1],
        'actual_duration_s':x.shape[1]/fs,'station_delay_s':delays.tolist(),
        'sampling_relative_error':float(np.linalg.norm(unquantized['vis_jy']-expected)/np.linalg.norm(expected)),
        'quantized_relative_error':float(np.linalg.norm(result['vis_jy']-expected)/np.linalg.norm(expected)),
        'quantization_vs_float_error':float(np.linalg.norm(result['vis_jy']-unquantized['vis_jy'])/np.linalg.norm(unquantized['vis_jy'])),
        'without_delay_correction_relative_error':float(np.linalg.norm(wrong['vis_jy']-expected)/np.linalg.norm(expected)),
        'valid_fft_count':result['valid_fft_count'].tolist(),
        'clipped_fraction':[m['clipped_fraction'] for m in quantization],
        'assumptions':['static geometry; FFT-periodic snapshots, not a continuous delayed sky',
                       'known geometric delay; no clock/LO drift or phase solutions',
                       'no receiver noise; finite Gaussian sky self-noise remains']}
    np.savez_compressed(out/'comparison.npz',expected=expected,correlated=result['vis_jy'],
                        unquantized=unquantized['vis_jy'],frequency_hz=result['frequencies_hz'])
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2));return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    run(p.parse_args().output)
