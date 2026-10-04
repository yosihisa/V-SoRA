"""Opt-in FX raw U3 sums on0.1s synthetic IQ, preserving main arrays."""
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from vsora_correlator.stream_fx import FXAccumulator
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum


def run(output):
    out=Path(output)
    if out.exists():raise FileExistsError('new output required')
    out.mkdir(parents=True)
    rng=np.random.default_rng(63);stations=4;nf=32;blocks=6400;fs=2048000.;center=1.42e9;chunk_samples=8192
    covariance=np.eye(stations)+.1*np.ones((stations,stations));root=np.linalg.cholesky(covariance)
    z=(rng.normal(size=(nf*blocks,stations))+1j*rng.normal(size=(nf*blocks,stations)))/np.sqrt(2)
    gain=np.array([1,.8,1.2,2])*np.exp(1j*np.array([0,.2,-.7,1.1]));x=(z @ root.T*gain).T.copy()
    frequency=center+np.fft.fftfreq(nf,1/fs);order=np.argsort(frequency)
    reference=np.fft.fft(x.reshape(stations,blocks,nf).transpose(1,2,0),axis=1,norm='ortho')[:,order]
    rows=[]
    for label in ('all','quality_and_gaps'):
        valid=np.ones(x.shape,bool);quality=None
        if label=='quality_and_gaps':
            valid[0,np.arange(0,blocks,101)*nf]=False;valid[1,np.arange(55,blocks,127)*nf+3]=False
            excluded=center+4*fs/nf
            quality={'channel_weights':True,'min_sk_blocks':24,'sk_bounds':[.5,1.5],
                'exclude_rf_ranges_hz':[[excluded-.1,excluded+.1]]}
        results=[];elapsed=[]
        for enabled in (False,True):
            start=time.perf_counter();a=FXAccumulator(stations,fs,nf,center,quality,collect_bispectrum=enabled)
            for first in range(0,x.shape[1],chunk_samples):a.consume(x[:,first:first+chunk_samples],valid[:,first:first+chunk_samples])
            results.append(a.finish(.002));elapsed.append(time.perf_counter()-start)
        baseline,combined=results;raw=combined['raw_bispectrum'];changed=[];numeric=0
        for key,value in baseline.items():
            if isinstance(value,np.ndarray):
                numeric+=1
                if not np.array_equal(value,combined[key]):changed.append(key)
            elif value!=combined[key]:changed.append(key)
        if changed:raise RuntimeError('ordinary FX outputs changed with raw bispectrum opt-in')
        block_ok=valid.reshape(stations,blocks,nf).all(axis=2).T;expected=[]
        for t in raw['triangles']:
            good=block_ok[:,t].all(axis=1)
            q=distinct_sample_bispectrum(reference[good].transpose(1,0,2),[t]);expected.append(q['distinct_sample_bispectrum'][:,0])
        expected=np.array(expected).T
        np.testing.assert_allclose(raw['distinct_sample_bispectrum'],expected,rtol=1e-12,atol=1e-12)
        np.savez_compressed(out/(label+'-raw-sums.npz'),**{k:v for k,v in raw.items() if isinstance(v,np.ndarray)})
        rows.append({'case':label,'nominal_seconds':nf*blocks/fs,'ordinary_numeric_arrays_compared':numeric,
            'ordinary_changed_fields':changed,'ordinary_arrays_bit_identical':True,
            'common_fft_count':raw['common_sample_count'].tolist(),'source_baseline_fft_count':baseline['valid_fft_count'][0].tolist(),
            'channels':nf,'triangles':len(raw['triangles']),'available_channel_triangles':int(raw['channel_triangle_usable'].sum()),
            'total_channel_triangles':raw['channel_triangle_usable'].size,'maximum_chunk_blocks':raw['maximum_chunk_blocks'],
            'maximum_absolute_batch_u3_difference':float(np.max(abs(raw['distinct_sample_bispectrum']-expected))),
            'fx_seconds_without_raw_sums':elapsed[0],'fx_seconds_with_raw_sums':elapsed[1],
            'input_sample_independence_verified':False,'input_mask_independence_verified':False})
    q={'type':'fx_bispectrum_validation','state':'complete','seed':63,'cases':rows,
        'input_iq_complex128_le_sha256':hashlib.sha256(x.astype('<c16').tobytes()).hexdigest(),
        'synthetic_iq_fft_processed':True,'physical_adc_vdif_processed':False,
        'production_rml_noise_model_changed':False,'real_hardware_validation_performed':False,
        'scope':'Opt-in reference FX common-sample raw U3 sums on0.1s synthetic Gaussian IQ with constant gains. Ordinary arrays bit-identical, external missing samples/quality masks preserved. No VDIF/FIR/clock/rate/geometry, actual FFT independence, empirical likelihood or imaging.'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for r in rows:axes[0].plot(np.arange(r['triangles']),r['common_fft_count'],'o-',label=r['case'])
    axes[0].set(title='Common FFT counts in opt-in FX',xlabel='Canonical triangle',ylabel='Common blocks');axes[0].legend()
    axes[1].bar([r['case'] for r in rows],[r['maximum_absolute_batch_u3_difference'] for r in rows])
    axes[1].set(title='FX U3 vs independent batch',ylabel='Maximum absolute difference')
    for ax in axes:ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(out/'fx-bispectrum.png',dpi=140);plt.close(fig)
    return q


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    q=run(**vars(p.parse_args()));print(json.dumps({'state':q['state'],'cases':len(q['cases'])}))
