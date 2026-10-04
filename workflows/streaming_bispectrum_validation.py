"""Known synthetic IQ -> FFT -> bounded raw U3 sums, no physical VDIF."""
import hashlib
import json
from pathlib import Path
import numpy as np
from vsora_correlator.bispectrum_accumulator import BispectrumAccumulator
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum


def run(output):
    out=Path(output)
    if out.exists():raise FileExistsError('new output required')
    out.mkdir(parents=True)
    rng=np.random.default_rng(61);blocks=257;channels=32;stations=4;chunk=7
    source=np.eye(stations)+.1*np.ones((stations,stations));root=np.linalg.cholesky(source)
    z=(rng.normal(size=(blocks,channels,stations))+1j*rng.normal(size=(blocks,channels,stations)))/np.sqrt(2)
    iq=z @ root.T
    spectrum=np.fft.fft(iq,axis=1,norm='ortho')
    input_sha=hashlib.sha256(iq.astype('<c16').tobytes()).hexdigest()
    rows=[]
    for label in ('all','deterministic_gaps'):
        valid=np.ones((blocks,stations),bool)
        if label=='deterministic_gaps':
            valid[:3,0]=False;valid[20:24,1]=False;valid[-5:,2]=False
        accumulator=BispectrumAccumulator(stations,channels)
        state_bytes=sum(v.nbytes for v in (accumulator._a,accumulator._h,accumulator._j,accumulator._counts))
        for start in range(0,blocks,chunk):
            chunk_spectrum=np.fft.fft(iq[start:start+chunk],axis=1,norm='ortho')
            accumulator.consume(chunk_spectrum,valid[start:start+chunk])
        q=accumulator.finish();expected=np.empty_like(q['distinct_sample_bispectrum']);ordinary=np.empty_like(expected)
        for n,t in enumerate(q['triangles']):
            good=valid[:,t].all(axis=1)
            ref=distinct_sample_bispectrum(spectrum[good].transpose(1,0,2),[t])
            expected[:,n]=ref['distinct_sample_bispectrum'][:,0];ordinary[:,n]=ref['ordinary_visibility_product'][:,0]
        np.testing.assert_allclose(q['distinct_sample_bispectrum'],expected,rtol=1e-12,atol=1e-12)
        np.testing.assert_allclose(q['ordinary_common_sample_product'],ordinary,rtol=1e-12,atol=1e-12)
        arrays={k:v for k,v in q.items() if isinstance(v,np.ndarray)}
        np.savez_compressed(out/(label+'-raw-sums.npz'),**arrays)
        with np.load(out/(label+'-raw-sums.npz'),allow_pickle=False) as saved:
            for k,v in arrays.items():np.testing.assert_array_equal(saved[k],v)
        rows.append({'case':label,'common_sample_count':q['common_sample_count'].tolist(),
            'distinct_sample_available':q['distinct_sample_available'].tolist(),
            'nominal_fft_blocks':blocks,'channels':channels,'stations':stations,'triangles':len(q['triangles']),
            'maximum_chunk_blocks':q['maximum_chunk_blocks'],'persistent_numeric_state_bytes':state_bytes,
            'maximum_absolute_distinct_batch_difference':float(np.max(abs(q['distinct_sample_bispectrum']-expected))),
            'maximum_absolute_ordinary_batch_difference':float(np.max(abs(q['ordinary_common_sample_product']-ordinary))),
            'saved_raw_sums_roundtrip_exact':True,'input_sample_independence_verified':False,
            'input_mask_independence_verified':False,'generating_truth_used':False})
    summary={'type':'streaming_bispectrum_validation','state':'complete','seed':61,
        'input_iq_complex128_le_sha256':input_sha,'cases':rows,
        'synthetic_gaussian_iq_fft_processed':True,'chunked_fft_processed':True,'full_batch_reference_retained_for_validation':True,'physical_adc_vdif_processed':False,
        'production_visibility_statistics_changed':False,'production_rml_noise_model_changed':False,
        'real_hardware_validation_performed':False,
        'scope':'Synthetic iid Gaussian IQ, unitary rectangular FFT, deterministic supplied block gaps, bounded incremental common-sample raw U3 sums. Algebra/roundtrip, no actual independence, signal-dependent flag selection, empirical uncertainty, calibration or image confidence.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for r in rows:axes[0].plot(np.arange(r['triangles']),r['common_sample_count'],'o-',label=r['case'])
    axes[0].set(title='Common FFT blocks per triangle',xlabel='Canonical triangle',ylabel='Retained blocks');axes[0].legend()
    axes[1].bar([r['case'] for r in rows],[r['maximum_absolute_distinct_batch_difference'] for r in rows])
    axes[1].set(title='Streaming vs full batch U3',ylabel='Maximum absolute difference')
    for ax in axes:ax.grid(axis='y',alpha=.2)
    fig.tight_layout();fig.savefig(out/'streaming-bispectrum.png',dpi=140);plt.close(fig)
    return summary


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    q=run(**vars(p.parse_args()));print(json.dumps({'state':q['state'],'cases':len(q['cases'])}))
