"""Exercise the actual correlator and imager commands on synthetic ADC VDIF."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import astropy.units as u
from astropy.time import Time
from vsora_observation import load_config
from vsora_observation.geometry import geometry_at_times
from vsora_simulator.iq import generate_iq
from vsora_formats.vdif import write_vdif
from vsora_formats.fitsidi import read_fitsidi


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];c=load_config(repo/'configs/experiments/ideal-point.json')
    c['noise']['enabled']=True;c['source']['model']='point'
    fs=2048000;fc=1.42e9;fft=128;groups=64;blocks=128;span=fft*groups*blocks/fs
    g=geometry_at_times(c,Time([Time(c['observation']['start_utc'])+span/2*u.s]))
    image=np.zeros((16,16));image[8,8]=1000
    delay=np.array([0,2.3e-6,-1.7e-6,.38e-6])+g['station_delay_s'][0]
    rate=np.array([0,17.3,-11.7,26.1]);phase=np.array([0,.4,-.7,1.4]);amp=np.array([1.2,.8,1.1,.9])*4
    x,_=generate_iq(np.zeros((6,3)),g['pairs'],image,16,np.full(4,1e4),fs,fc,fft,groups*blocks,92,delay)
    t=np.arange(x.shape[1])/fs;fref=fc-fs/(2*fft)
    x*=amp[:,None]*np.exp(1j*(phase[:,None]-2*np.pi*fref*(delay-g['station_delay_s'][0])[:,None]
                            +2*np.pi*rate[:,None]*(t[None,:]-span/2)))
    stations=[]
    for i,data in enumerate(x):
        scale=2*np.sqrt(np.mean(abs(data)**2)/2);path=out/f'station{i+1}.vdif'
        write_vdif(path,data,c['observation']['start_utc'],fs,i+1,scale,voltage_unit='ADC')
        stations.append({'id':c['stations'][i]['id'],'vdif':path.name,'station_numeric_id':i+1,'decoded_voltage_scale':scale})
    (out/'observation.json').write_text(json.dumps(c,indent=2)+'\n')
    manifest={'schema_version':1,'observation_config':'observation.json','sample_rate_hz':fs,'fft_length':fft,
              'blocks_per_integration':blocks,'integrations_per_shard':64,'voltage_unit':'ADC',
              'stations':stations,'phase_center_correction':True}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    def command(module,*arguments):
        result=subprocess.run([sys.executable,str(repo/'tools/run.py'),module,*map(str,arguments)],
                              cwd=repo,capture_output=True,text=True)
        if result.returncode: raise RuntimeError('CLI verification failed; inspect local output')
        return json.loads(result.stdout)
    first=command('vsora_correlator','correlate','--manifest',out/'manifest.json','--output',out/'pilot')
    command('vsora_correlator','calibrate','--input',out/'pilot/shard-00000.npz','--point-flux-jy','1000','--output',out/'initial.json')
    command('vsora_correlator','correlate','--manifest',out/'manifest.json','--rate-calibration',out/'initial.json','--output',out/'rephased')
    command('vsora_correlator','calibrate','--input',out/'rephased/shard-00000.npz','--point-flux-jy','1000','--output',out/'final.json')
    applied=command('vsora_correlator','apply','--input',out/'rephased/shard-00000.npz','--calibration',out/'final.json','--output',out/'corrected')
    imaged=command('vsora_imaging','--input',out/'corrected/visibility.fits','--output',out/'image','--clean-radius-arcsec','80')
    idi=read_fitsidi(out/'corrected/visibility.fits')
    error=float(np.linalg.norm(idi['vis_jy'].mean(axis=0)-1000)/np.sqrt(6)/1000)
    summary={'state':'complete','input_voltage_unit':'ADC','uncalibrated_visibility_unit':first['visibility_unit'],
             'output_visibility_unit':applied['visibility_unit'],'known_calibrator_flux_jy':1000,
             'recorded_span_s':first['recorded_span_s'],'calibrated_mean_relative_error':error,
             'image_peak_jy':imaged['image_peak_jy'],'model_flux_jy':imaged['model_flux_jy'],
             'imaging_converged':imaged['converged'],'shards':len(first['shards']),
             'limitations':['Synthetic stationary FFT-periodic point source with unknown ADC gains',
                            'Two pilot passes on the same recording; no target transfer in this smoke test',
                            'Common frame timestamps and sample rates; clock mapping API not integrated']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
    if error>.03 or abs(imaged['image_peak_jy']/1000-1)>.03 or not imaged['converged']:
        raise AssertionError('CLI pipeline validation failed')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(p.parse_args().output)
