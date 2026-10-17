"""Synthetic raw archive compatibility and same-sample normalization checks."""
import argparse,hashlib,json
from itertools import combinations
from pathlib import Path
import numpy as np
from vsora_correlator.bispectrum_accumulator import BispectrumAccumulator
from vsora_correlator.bispectrum_power import normalize_common_power_bispectrum
from vsora_correlator.bispectrum_inspect import inspect_bispectrum_cell,inspect_bispectrum_file
from vsora_formats.bispectrum import save_bispectrum,load_bispectrum
from vsora_formats.spectral import save_spectral

def _example(tmp_path, mode='complete', unit='ADC'):
    rng=np.random.default_rng(90)
    x=rng.normal(size=(11,4,4))+1j*rng.normal(size=(11,4,4))
    valid=np.ones((len(x),4),bool)
    if mode=='missing':valid[:3,0]=False;valid[4,1]=False
    elif mode=='two':valid[2:]=False
    elif mode=='zero_count':valid[:]=False
    elif mode=='zero_station':x[:,:,0]=0
    elif mode!='complete':raise ValueError(mode)
    acc=BispectrumAccumulator(4,4);acc.consume(x[:3],valid[:3]);acc.consume(x[3:],valid[3:]);raw=acc.finish()
    times=np.array([.01,.02]);frequencies=1.42e9+np.fft.fftshift(np.fft.fftfreq(4,1/2.048e6))
    usable=np.broadcast_to(raw['common_sample_count']>=3,(2,4,4)).copy();usable[:,0]=False
    data={'triangles':raw['triangles'],'times_s':times,'frequencies_hz':frequencies,
          'common_fft_count':np.stack([raw['common_sample_count']]*2),'nominal_fft_count':np.full(2,len(x)),
          'edge_sums':np.stack([raw['edge_sums']]*2),'paired_edge_sums':np.stack([raw['paired_edge_sums']]*2),
          'triple_edge_sum':np.stack([raw['triple_edge_sum']]*2),'channel_triangle_usable':usable,
          'common_station_power_sums':np.stack([raw['common_station_power_sums']]*2)}
    pairs=np.array(list(combinations(range(4),2)));values=[];counts=[]
    for i,j in pairs:
        good=valid[:,i]&valid[:,j];counts.append(int(good.sum()))
        values.append((x[good,:,i]*x[good,:,j].conj()).mean(axis=0) if good.any() else np.zeros(4,complex))
    count=np.asarray(counts);visibility=np.stack(values,axis=-1)
    original={'visibilities':np.stack([visibility]*2),'weights':np.broadcast_to((count>0)[None,None,:],(2,4,6)).astype(float),
              'uvw_lambda':np.zeros((2,4,6,3)),'pairs':pairs,'times_s':times,'frequencies_hz':frequencies,
              'valid_fft_count':np.stack([count]*2)}
    ids=['A0','A1','A2','A3'];epoch='2026-10-17T00:00:00Z';source=tmp_path/'visibility.npz'
    save_spectral(source,original,{'visibility_unit':'ADC^2' if unit=='ADC' else 'Jy','time_origin_utc':epoch,
        'config':{'stations':[{'id':v} for v in ids]},'fft_length':4,'fft_sample_rate_hz':2.048e6})
    meta={'station_ids':ids,'time_origin_utc':epoch,'voltage_unit':unit,'fft_length':4,'sample_rate_hz':2.048e6,
          'visibility_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
          'processing_notes':['Synthetic spectral coefficients; no hardware or sample-independence claim.']}
    return data,meta,source,raw


def case_plan():
    specifications=[('complete','ADC',2),('missing','ADC',2),('two','ADC',2),
        ('zero_count','ADC',2),('zero_station','ADC',2),('complete','sqrt(Jy)',2),
        ('complete','ADC',1),('missing','sqrt(Jy)',1)]
    return [{'case_id':f'c{i:02d}','mode':mode,'voltage_unit':unit,'schema_version':version}
            for i,(mode,unit,version) in enumerate(specifications)]


def experiment(case,output):
    plan={c['case_id']:c for c in case_plan()}
    if not isinstance(case,dict) or case.get('case_id') not in plan or case!=plan[case['case_id']]:
        raise ValueError('unmodified archive-validation case required')
    out=Path(output)
    if out.exists():raise FileExistsError('new archive case output required')
    out.mkdir(parents=True)
    d,meta,source,raw=_example(out,case['mode'],case['voltage_unit'])
    if case['schema_version']==1:d.pop('common_station_power_sums')
    path=out/'raw.npz';save_bispectrum(path,d,meta,schema_version=case['schema_version'])
    loaded=load_bispectrum(path,source)
    for key,value in d.items():np.testing.assert_array_equal(value,loaded[key])
    reference=normalize_common_power_bispectrum(raw);cells=[];max_error=0.
    for ti in range(2):
        for fi in range(4):
            q=inspect_bispectrum_file(path,source,out/f'inspect-t{ti}-f{fi}.json',fi,ti)
            assert q['source_visibility_verified']
            for k,row in enumerate(q['triangles']):
                if case['schema_version']==1:
                    assert row['observed_power_normalized_u3_real'] is None
                    assert row['observed_power_normalization_state']=='missing_common_power_v1'
                else:
                    np.testing.assert_array_equal(row['common_station_power_sums'],raw['common_station_power_sums'][fi,k])
                    for base,flag in [('observed_power_normalized_u3','u3_available'),
                                      ('observed_power_normalized_ordinary_product','ordinary_available')]:
                        assert row[base+'_available']==bool(reference[flag][fi,k])
                        if reference[flag][fi,k]:
                            value=complex(row[base+'_real'],row[base+'_imag']);expected=reference[base][fi,k]
                            np.testing.assert_allclose(value,expected,rtol=3e-14,atol=1e-14)
                            max_error=max(max_error,float(abs(value-expected)))
                        else:assert row[base+'_real'] is None and row[base+'_imag'] is None
            cells.append(q)
    states={}
    for cell in cells:
        for row in cell['triangles']:
            state=row['observed_power_normalization_state'];states[state]=states.get(state,0)+1
    return {**case,'state':'complete','all_arrays_roundtrip_exact':True,'all_source_links_verified':True,
            'inspection_cells':cells,'inspection_triangle_rows':32,'normalization_states':states,
            'maximum_normalization_difference_from_runtime':max_error,
            'raw_archive_bytes':path.stat().st_size,'source_archive_bytes':source.stat().st_size,
            'actual_iq_fft_processed':False,'synthetic_spectral_coefficients_used':True,
            'input_sample_independence_verified':False,'input_mask_independence_verified':False,
            'production_rml_noise_model_changed':False,'real_hardware_validation_performed':False}


def run(output):
    out=Path(output)
    if out.exists():raise FileExistsError('new archive validation output required')
    out.mkdir(parents=True);cases=[experiment(c,out/c['case_id']) for c in case_plan()]
    q={'type':'common_power_archive_validation','state':'complete','cases':cases,
       'archive_versions_checked':[1,2],'source_visibility_identity_checked':True,
       'legacy_missing_power_not_inferred':True,'normalization_numeric_availability_separate_from_quality_mask':True,
       'synthetic_spectral_coefficients_used':True,'actual_iq_fft_processed':False,
       'actual_temporal_independence_verified':False,'noise_covariance_estimated':False,
       'observed_power_ratio_unbiased_guarantee':False,'production_rml_noise_model_changed':False,
       'actual_hardware_data':False}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    states=['usable_normalized_value','masked_normalized_value','insufficient_samples','zero_common_power','missing_common_power_v1']
    fig,ax=plt.subplots(figsize=(9,4));bottom=np.zeros(len(cases))
    for state in states:
        values=np.array([c['normalization_states'].get(state,0) for c in cases])
        ax.bar([c['case_id'] for c in cases],values,bottom=bottom,label=state);bottom+=values
    ax.set_ylabel('Inspected triangle values');ax.set_xlabel('Synthetic archive case')
    ax.set_title('Stored common-power ratio availability, separate from quality')
    ax.legend(fontsize=7,loc='upper left',bbox_to_anchor=(1,1));fig.tight_layout()
    fig.savefig(out/'archive-availability.png',dpi=140);plt.close(fig)
    return q


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    q=run(**vars(parser.parse_args()));print(json.dumps({'state':q['state'],'conditions':len(q['cases'])}))


if __name__=='__main__':main()
