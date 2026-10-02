"""Continuous analytic waveform validates ADC mapping without FFT periods."""
import argparse
import json
from pathlib import Path
import numpy as np
from vsora_correlator.clock import resample_station,estimate_clock_mapping


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    fs=65536;n=32768;rng=np.random.default_rng(4)
    freq=rng.uniform(-.35*fs,.35*fs,32);coeff=(rng.normal(size=32)+1j*rng.normal(size=32))/8
    def signal(t): return np.exp(2j*np.pi*np.asarray(t)[:,None]*freq).dot(coeff)
    ref=signal(np.arange(n)/fs);cases=[]
    query=np.arange(200,n-200)/fs;expected=signal(query)
    for offset,ppm in [(3.25,80),(-2.4,-65),(.3,0)]:
        actual=fs*(1+ppm*1e-6);start=offset/fs
        x=signal(start+np.arange(n)/actual)*(.8+.3j)
        clock=estimate_clock_mapping(ref,x,fs)
        aligned,good=resample_station(x,clock['effective_start_s'],clock['actual_sample_rate_hz'],query,fs,.35*fs)
        gain=complex(*clock['constant_correction_gain']);aligned*=gain
        row={'injected_start_samples':offset,'injected_rate_ppm':ppm,
             'estimated_start_samples':clock['effective_start_s']*fs,
             'estimated_rate_ppm':clock['sample_rate_error_ppm'],
             'before_relative_error':float(np.linalg.norm(x[200:n-200]*gain-expected)/np.linalg.norm(expected)),
             'after_relative_error':float(np.linalg.norm(aligned-expected)/np.linalg.norm(expected)),
             'coherence':clock['coherence'],'valid_output_samples':int(good.sum())}
        if row['after_relative_error']>.001 or abs(row['estimated_rate_ppm']-ppm)>.03:
            raise AssertionError('clock mapping validation failed')
        cases.append(row)
    summary={'sample_rate_hz':fs,'duration_s':n/fs,'reference_waveform':'32 analytic continuous complex tones',
             'max_baseband_fraction':.35,'sinc_radius':32,'cases':cases,
             'limitations':['Strong shared deterministic waveform; astronomical low-SNR clock estimation unverified',
                            'Clock offset and geometry are degenerate without independent geometry',
                            'Time-invariant linear ADC drift, no LO rate in this clock test',
                            'Finite sinc needs band-edge guard and input sample margins']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(p.parse_args().output)
