"""Raw U3 sidecar linked to synthetic spectral visibility, no real VDIF."""
import hashlib
import json
from pathlib import Path
from itertools import combinations
import numpy as np
from vsora_correlator.bispectrum_accumulator import BispectrumAccumulator
from vsora_formats.bispectrum import save_bispectrum,load_bispectrum
from vsora_formats.spectral import save_spectral
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum


def run(output):
    out=Path(output)
    if out.exists():raise FileExistsError('new output required')
    out.mkdir(parents=True)
    rng=np.random.default_rng(62);nt=2;blocks=17;nf=8;stations=4;fs=1024.;chunk=4
    s=np.eye(stations)+.1*np.ones((stations,stations));root=np.linalg.cholesky(s)
    z=(rng.normal(size=(nt,blocks,nf,stations))+1j*rng.normal(size=(nt,blocks,nf,stations)))/np.sqrt(2)
    iq=z @ root.T;full=np.fft.fft(iq,axis=2,norm='ortho')
    frequency=1.42e9+np.fft.fftfreq(nf,1/fs);order=np.argsort(frequency);frequency=frequency[order]
    valid=np.ones((nt,blocks,stations),bool);valid[0,:2,0]=False;valid[0,7:9,1]=False;valid[1,-3:,2]=False;valid[1,:1,3]=False
    pairs=np.array(list(combinations(range(stations),2)));ids=[f'A{i}' for i in range(stations)];epoch='2026-10-04T00:00:00Z'
    times=(np.arange(nt)+.5)*blocks*nf/fs;states=[];visibility=[];counts=[];expected=[]
    for index in range(nt):
        accumulator=BispectrumAccumulator(stations,nf)
        for first in range(0,blocks,chunk):
            spectrum=np.fft.fft(iq[index,first:first+chunk],axis=1,norm='ortho')[:,order]
            accumulator.consume(spectrum,valid[index,first:first+chunk])
        q=accumulator.finish();states.append(q);v=[];m=[];target=[]
        for i,j in pairs:
            good=valid[index,:,i]&valid[index,:,j]
            v.append((full[index,good,:,i]*full[index,good,:,j].conj()).mean(axis=0)[order]);m.append(int(good.sum()))
        visibility.append(np.array(v).T);counts.append(m)
        for t in q['triangles']:
            good=valid[index][:,t].all(axis=1)
            ref=distinct_sample_bispectrum(full[index,good].transpose(1,0,2),[t])
            target.append(ref['distinct_sample_bispectrum'][:,0][order])
        expected.append(np.array(target).T)
    source=out/'spectral-visibility.npz'
    original={'visibilities':np.array(visibility),'weights':np.ones((nt,nf,len(pairs))),
        'pairs':pairs,'times_s':times,'frequencies_hz':frequency,'uvw_lambda':np.zeros((nt,nf,len(pairs),3)),
        'valid_fft_count':np.array(counts),'integration_s':np.array(counts)*nf/fs}
    meta={'visibility_unit':'ADC^2','time_origin_utc':epoch,'config':{'stations':[{'id':v} for v in ids]},
        'fft_length':nf,'fft_sample_rate_hz':fs,'validation_only':True,'geometric_delay_processed':False,
        'weights_note':'Arbitrary positive format-test weights, not a calibrated noise model.'}
    save_spectral(source,original,meta)
    with source.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    data={'triangles':states[0]['triangles'],'times_s':times,'frequencies_hz':frequency,
        'common_fft_count':np.array([q['common_sample_count'] for q in states]),'nominal_fft_count':np.full(nt,blocks),
        'edge_sums':np.array([q['edge_sums'] for q in states]),'paired_edge_sums':np.array([q['paired_edge_sums'] for q in states]),
        'triple_edge_sum':np.array([q['triple_edge_sum'] for q in states]),'channel_triangle_usable':np.ones((nt,nf,len(states[0]['triangles'])),bool)}
    sidecar=out/'raw-bispectrum.npz'
    metadata={'station_ids':ids,'time_origin_utc':epoch,'voltage_unit':'ADC','fft_length':nf,'sample_rate_hz':fs,
        'visibility_sha256':digest,'processing_notes':['Synthetic Gaussian IQ; unitary rectangular FFT in four-block chunks.',
        'Deterministic station block gaps; no observed signal selection.',
        'No ADC quantization, VDIF, FIR, clock mapping, LO correction or geometric delay.',
        'Arbitrary positive visibility weights and zero UVW for format validation only.']}
    save_bispectrum(sidecar,data,metadata);loaded=load_bispectrum(sidecar,source)
    for key,value in data.items():np.testing.assert_array_equal(loaded[key],value)
    expected=np.array(expected)
    np.testing.assert_allclose(loaded['distinct_sample_bispectrum'],expected,rtol=1e-12,atol=1e-12)
    q={'type':'bispectrum_sidecar_validation','state':'complete','seed':62,
        'times':nt,'channels':nf,'stations':stations,'triangles':len(states[0]['triangles']),
        'common_fft_count':data['common_fft_count'].tolist(),'source_baseline_fft_count':counts,
        'visibility_sha256':digest,'input_iq_complex128_le_sha256':hashlib.sha256(iq.astype('<c16').tobytes()).hexdigest(),
        'source_visibility_verified':loaded['source_visibility_verified'],'raw_arrays_roundtrip_exact':True,
        'maximum_absolute_batch_u3_difference':float(np.max(abs(loaded['distinct_sample_bispectrum']-expected))),
        'raw_sidecar_bytes':sidecar.stat().st_size,'source_visibility_bytes':source.stat().st_size,
        'actual_temporal_independence_verified':False,'physical_adc_vdif_processed':False,
        'real_hardware_validation_performed':False,'production_rml_noise_model_changed':False,
        'scope':'Synthetic IQ -> chunk FFT/raw sums -> version1 sidecar -> raw U3 reconstruction and source spectral hash/axes/stations/units/counts/same-count mean checks. Format-only weights/zero UVW; no actual independent FFT, empirical uncertainty, normalization or imaging.'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4));x=np.arange(len(states[0]['triangles']))
    for index,row in enumerate(data['common_fft_count']):axes[0].plot(x,row,'o-',label=f'Cell {index}')
    axes[0].set(title='Saved common FFT counts',xlabel='Canonical triangle',ylabel='Common blocks');axes[0].legend()
    axes[1].plot(frequency/1e6,np.max(abs(loaded['distinct_sample_bispectrum']-expected),axis=(0,2)),'o-')
    axes[1].set(title='Reloaded U3 vs batch',xlabel='RF (MHz)',ylabel='Maximum absolute difference')
    for ax in axes:ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(out/'bispectrum-sidecar.png',dpi=140);plt.close(fig)
    return q


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    q=run(**vars(p.parse_args()));print(json.dumps({'state':q['state'],'source_verified':q['source_visibility_verified']}))
