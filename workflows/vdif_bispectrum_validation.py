"""Actual synthetic VDIF -> aligned FX raw U3 sidecar; no image certification."""
import hashlib,json
from pathlib import Path
import numpy as np
from workflows.vdif_closure_validation import make_fixture
from vsora_correlator.aligned import correlate_aligned
from vsora_formats.spectral import load_spectral
from vsora_formats.bispectrum import load_bispectrum
from vsora_formats.vdif import read_vdif,write_vdif


def run(output):
    out=Path(output)
    if out.exists():raise FileExistsError('new output required')
    out.mkdir(parents=True)
    generating=make_fixture(out/'input',seed=64,frame_count=70,rates_hz=[0.,17.3,-11.7,26.1])
    manifest=out/'input/manifest.json';clock=out/'input/clock.json'
    c=json.loads(manifest.read_text());c['blocks_per_integration']=3200
    c['spectral_quality']['exclude_rf_ranges_hz'].append([1.42e9-.1,1.42e9+.1])
    manifest.write_text(json.dumps(c,indent=2)+'\n')
    for index,frame in [(0,7),(1,19)]:
        station=c['stations'][index];path=out/'input'/station['vdif']
        x,valid,_=read_vdif(path,c['sample_rate_hz'],station['station_numeric_id'],station['decoded_voltage_scale'])
        valid[frame*4096:(frame+1)*4096]=False
        path.unlink();path.with_suffix('.json').unlink()
        write_vdif(path,x,generating_epoch(c,out),c['sample_rate_hz'],station['station_numeric_id'],station['decoded_voltage_scale'],valid=valid,voltage_unit='ADC')
    obs=json.loads((out/'input/observation.json').read_text());ids=[s['id'] for s in obs['stations']]
    profile={'schema_version':1,'type':'station_rate_only','station_ids':ids,'station_indices':list(range(4)),
        'time_origin_utc':obs['observation']['start_utc'],'station_rates_hz':generating['true_rates_hz'],
        'valid_time_range_s':[0.,.14],'sample_cadence_s':.002,'time_reference_s':.07}
    rate=out/'supplied-rate.json';rate.write_text(json.dumps(profile,indent=2)+'\n')
    off=correlate_aligned(manifest,clock,out/'ordinary',2,rate_profile=rate)
    on=correlate_aligned(manifest,clock,out/'with-raw',2,rate_profile=rate,collect_bispectrum=True)
    a=load_spectral(out/'ordinary/shard-00000.npz');b=load_spectral(out/'with-raw/shard-00000.npz')
    arrays=[k for k,v in a.items() if isinstance(v,np.ndarray)]
    for k in arrays:np.testing.assert_array_equal(a[k],b[k])
    assert a['metadata']==b['metadata'] and 'raw_bispectrum' not in off
    assert not (out/'ordinary/raw-bispectrum.npz').exists()
    raw=load_bispectrum(out/'with-raw/raw-bispectrum.npz',out/'with-raw/shard-00000.npz')
    pair_index={tuple(p):n for n,p in enumerate(b['pairs'])};expected=np.zeros_like(raw['channel_triangle_usable'])
    for n,(i,j,k) in enumerate(raw['triangles']):
        indices=[pair_index[(i,j)],pair_index[(j,k)],pair_index[(i,k)]]
        expected[:,:,n]=(raw['common_fft_count'][:,n,None]>=3)&(b['weights'][:,:,indices]>0).all(axis=2)
    np.testing.assert_array_equal(raw['channel_triangle_usable'],expected)
    assert not raw['channel_triangle_usable'][:,abs(raw['frequencies_hz']-1.42e9)<.1,:].any()
    for key in ('input_sample_independence_verified','input_mask_independence_verified','production_rml_noise_model_changed'):
        assert raw['metadata'][key] is False
    inputs=[]
    for station in c['stations']:
        path=out/'input'/station['vdif']
        with path.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
        inputs.append({'station_id':station['id'],'vdif_sha256':sha,'bytes':path.stat().st_size,
                       'clipped_fraction':json.loads(path.with_suffix('.json').read_text())['clipped_fraction']})
    q={'type':'vdif_bispectrum_validation','state':'complete','seed':64,'generating':generating,
        'input_files':inputs,'invalid_frames_by_station':[[7],[19],[],[]],
        'integrations':2,'nominal_integration_s':.05,'recorded_span_s':on['recorded_span_s'],
        'ordinary_numeric_arrays_compared':len(arrays),'ordinary_arrays_bit_identical':True,'ordinary_metadata_identical':True,
        'default_has_no_raw_sidecar':True,'source_visibility_verified':raw['source_visibility_verified'],
        'common_fft_count':raw['common_fft_count'].tolist(),'source_baseline_fft_count':b['valid_fft_count'].tolist(),
        'raw_sidecar_bytes':on['raw_bispectrum']['bytes'],'source_visibility_bytes':(out/'with-raw/shard-00000.npz').stat().st_size,
        'raw_sidecar_uncompressed_numeric_bytes':sum(v.nbytes for v in raw.values() if isinstance(v,np.ndarray)),
        'usable_channel_triangles':int(expected.sum()),'total_channel_triangles':expected.size,
        'station_max_buffer_samples':on['station_max_buffer_samples'],'maximum_fx_chunk_samples':on['maximum_fx_chunk_samples'],
        'supplied_rate_profile_used':True,'automatic_rate_recovery_tested':False,
        'vdif_fir_interpolation_geometry_processed':True,'actual_temporal_independence_verified':False,
        'production_rml_noise_model_changed':False,'real_hardware_validation_performed':False,
        'scope':'Synthetic band-limited phase-center Gaussian source, known fixed gains and supplied clocks/rates, VDIF8bit -> FIR65/interpolation65/geometric and RF correction -> FX raw sums -> checked sidecar. Missing frames and RF masks. Not actual independence, weak-signal detection, closure likelihood or Cas A image fidelity.'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for index,row in enumerate(raw['common_fft_count']):axes[0].plot(np.arange(len(row)),row,'o-',label=f'Cell {index}')
    axes[0].set(title='Common FFT counts after VDIF alignment',xlabel='Canonical triangle',ylabel='Common blocks');axes[0].legend()
    image=axes[1].imshow(expected.sum(axis=2),aspect='auto',origin='lower',extent=[raw['frequencies_hz'][0]/1e6,raw['frequencies_hz'][-1]/1e6,0,2],vmin=0,vmax=4)
    axes[1].set_xticks([1419.,1420.,1421.]);axes[1].set_yticks([.5,1.5],['0','1'])
    fig.colorbar(image,ax=axes[1],ticks=[0,1,2,3,4],label='Usable triangles')
    axes[1].set(title='Usable triangles by RF and cell',xlabel='RF (MHz)',ylabel='Cell')
    fig.tight_layout();fig.savefig(out/'vdif-bispectrum.png',dpi=140);plt.close(fig)
    return q


def generating_epoch(c,out):
    return json.loads((out/'input'/c['observation_config']).read_text())['observation']['start_utc']


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    q=run(**vars(p.parse_args()));print(json.dumps({'state':q['state'],'source_verified':q['source_visibility_verified']}))
