"""Finite synthetic IQ/FFT checks of matching common-sample power ratios."""
import argparse,json
from pathlib import Path
import numpy as np
from vsora_correlator.stream_fx import FXAccumulator
from vsora_correlator.bispectrum_power import normalize_common_power_bispectrum
from .bispectrum_observed_power import observed_power_normalized_bispectrum


def case_plan():
    return [{'case_id':f'c{i:02d}-{mode}','mode':mode,'stations':n,'fft_length':nf,'blocks':m,'chunk_blocks':257 if mode=='short_window_0p3s' else 7,'seed':8900+i,
             'sample_rate_hz':2048000.,'center_frequency_hz':1.42e9}
            for i,(mode,n,nf,m) in enumerate([
                ('complete',3,8,31),('complete',4,16,257),('missing',4,16,257),
                ('complete',8,32,73),('missing',8,32,73),('zero_station',4,16,31),
                ('two_retained_blocks',4,16,31),('data_dependent_mask',4,16,31),
                ('short_window_0p3s',4,32,19200)])]


def experiment(case):
    plan={c['case_id']:c for c in case_plan()}
    if not isinstance(case,dict) or case.get('case_id') not in plan or case!=plan[case['case_id']]:
        raise ValueError('unmodified fixed synthetic IQ/FFT case required')
    n=case['stations'];nf=case['fft_length'];m=case['blocks'];rng=np.random.default_rng(case['seed'])
    shape=(n,nf*m);shared=(rng.normal(size=(1,nf*m))+1j*rng.normal(size=(1,nf*m)))/np.sqrt(2)
    x=.8*shared+(rng.normal(size=shape)+1j*rng.normal(size=shape))/np.sqrt(2)
    g=np.exp(np.linspace(-.6,.7,n)+1j*np.linspace(-1.7,2.4,n));x=x*g[:,None]
    valid=np.ones(x.shape,bool)
    if case['mode']=='missing':
        for s in range(n):valid[s,((np.arange(m)+s)%13==0).repeat(nf)]=False
    elif case['mode']=='zero_station':x[0]=0
    elif case['mode']=='two_retained_blocks':valid[:,2*nf:]=False
    elif case['mode']=='data_dependent_mask':
        power=(abs(x.reshape(n,m,nf))**2).mean(axis=-1)
        valid=(power<=np.quantile(power,.7,axis=1)[:,None]).repeat(nf,axis=1)
    quality={'channel_weights':True,'min_sk_blocks':24,'sk_bounds':[.1,3.],
             'exclude_rf_ranges_hz':[[case['center_frequency_hz']-.1,case['center_frequency_hz']+.1]]}
    def process(samples,collect):
        a=FXAccumulator(n,case['sample_rate_hz'],nf,case['center_frequency_hz'],quality,collect_bispectrum=collect)
        for start in range(0,nf*m,nf*case['chunk_blocks']):a.consume(samples[:,start:start+nf*case['chunk_blocks']],valid[:,start:start+nf*case['chunk_blocks']])
        return a.finish()
    raw_result=process(x,True);ordinary=process(x,False)
    for key,value in ordinary.items():
        if isinstance(value,np.ndarray):np.testing.assert_array_equal(raw_result[key],value)
        else:assert raw_result[key]==value
    raw=raw_result['raw_bispectrum'];r=normalize_common_power_bispectrum(raw)
    assert raw['maximum_chunk_blocks']==min(m,case['chunk_blocks'])
    order=np.argsort(case['center_frequency_hz']+np.fft.fftfreq(nf,1/case['sample_rate_hz']))
    spectrum=np.fft.fft(x.reshape(n,m,nf).transpose(1,2,0),axis=1,norm='ortho')[:,order]
    block_valid=valid.reshape(n,m,nf).all(axis=-1).T
    max_power_difference=0.;max_ratio_difference=0.;station_only_difference=0.;checked=0
    for index,t in enumerate(raw['triangles']):
        good=block_valid[:,t].all(axis=1);count=int(good.sum());assert raw['common_sample_count'][index]==count
        power_sum=(abs(spectrum[good][:,:,t])**2).sum(axis=0)
        np.testing.assert_allclose(raw['common_station_power_sums'][:,index],power_sum,rtol=2e-12,atol=2e-12)
        max_power_difference=max(max_power_difference,float(np.max(abs(raw['common_station_power_sums'][:,index]-power_sum))))
        positive=(power_sum>0).all(axis=-1)
        np.testing.assert_array_equal(r['u3_available'][:,index],positive&(count>=3))
        if count:
            common=power_sum/count
            for position,station in enumerate(t):
                own=(abs(spectrum[block_valid[:,station],:,station])**2).mean(axis=0)
                denominator=np.maximum(common[:,position],np.finfo(float).tiny)
                station_only_difference=max(station_only_difference,float(np.max(abs(own-common[:,position])/denominator)))
        if count>=3 and positive.any():
            selected=spectrum[good][:,positive][:,:,t].transpose(1,0,2)
            reference=observed_power_normalized_bispectrum(selected)
            for key in ('observed_power_normalized_u3','observed_power_normalized_ordinary_product'):
                value=r[key][positive,index];expected=reference[key][:,0]
                np.testing.assert_allclose(value,expected,rtol=2e-10,atol=2e-12)
                max_ratio_difference=max(max_ratio_difference,float(np.max(abs(value-expected))))
            checked+=int(positive.sum())
    fixed_gain=np.exp(np.linspace(.3,-.4,n)+1j*np.linspace(2.1,-.9,n))
    changed=normalize_common_power_bispectrum(process(x*fixed_gain[:,None],True)['raw_bispectrum'])
    gain_error=0.
    for key in ('observed_power_normalized_u3','observed_power_normalized_ordinary_product'):
        np.testing.assert_allclose(r[key],changed[key],rtol=2e-10,atol=2e-12)
        gain_error=max(gain_error,float(np.max(abs(r[key]-changed[key]))))
    np.testing.assert_array_equal(r['channel_triangle_usable'],raw['channel_triangle_usable'])
    return {**case,'state':'complete','nominal_iq_duration_s':nf*m/case['sample_rate_hz'],'station_gain_constant_within_window_assumed':True,'synthetic_gaussian_iq_fft_processed':True,'common_sample_count':raw['common_sample_count'].tolist(),
            'maximum_chunk_blocks_seen':raw['maximum_chunk_blocks'],'additional_common_power_storage_bytes':raw['common_station_power_sums'].nbytes,
            'available_u3_cells':int(r['u3_available'].sum()),'unavailable_u3_cells':int((~r['u3_available']).sum()),
            'existing_quality_usable_normalized_u3_cells':int(r['normalized_u3_existing_quality_usable'].sum()),
            'direct_voltage_reference_cells_checked':checked,'maximum_common_power_sum_abs_difference':max_power_difference,
            'maximum_dimensionless_ratio_abs_difference_from_voltage_api':max_ratio_difference,
            'maximum_relative_power_difference_from_station_only_samples':station_only_difference,
            'maximum_fixed_gain_ratio_abs_difference':gain_error,
            'ordinary_visibility_arrays_bit_identical':True,'channel_order_and_existing_quality_mask_checked':True,
            'same_materialized_mask_used_under_gain_change':True,'mask_generated_from_data':case['mode']=='data_dependent_mask',
            'input_sample_independence_verified':False,'input_mask_independence_verified':False,
            'physical_adc_quantization_vdif_processed':False,'normalized_power_persisted_in_raw_profile_v1':False,
            'production_rml_noise_model_changed':False,'real_hardware_validation_performed':False}


def run(output):
    out=Path(output)
    if out.exists():raise FileExistsError('new common-power validation output required')
    out.mkdir(parents=True);cases=[experiment(c) for c in case_plan()]
    q={'type':'common_sample_power_validation','state':'complete','cases':cases,
       'synthetic_iq_fft_processed':True,'common_power_sample_sets_matched':True,
       'ordinary_visibility_arrays_bit_identical':True,'raw_profile_v1_format_changed':False,
       'physical_adc_quantization_vdif_processed':False,'baseline_delay_and_lo_offsets_simulated':False,'unknown_lo_estimated':False,
       'input_sample_independence_verified':False,'input_mask_independence_verified':False,
       'phase_or_image_likelihood_constructed':False,'real_hardware_validation_performed':False,
       'production_rml_noise_model_changed':False,
       'scope':'Finite synthetic IQ and actual orthonormal FFT arithmetic only. Each triangle uses its common valid blocks for U3 and three powers; numerical availability and existing quality flags remain distinct. Data-dependent masks are held fixed for algebraic gain comparison. No IID/mask or image confidence guarantee; no physical ADC, quantization or VDIF; raw profile v1 does not store the new power sums.'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');plot(q,out/'common-power.png');return q


def plot(q,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(12,3.5));indices=np.arange(len(q['cases']))
    axes[0].bar(indices,[max(c['maximum_dimensionless_ratio_abs_difference_from_voltage_api'],1e-18) for c in q['cases']]);axes[0].set_yscale('log')
    axes[0].set(title='Ratio vs direct voltage API',ylabel='Maximum absolute difference (floor for plot)')
    axes[1].bar(indices,[c['maximum_relative_power_difference_from_station_only_samples'] for c in q['cases']]);axes[1].set(title='Common vs station-only samples',ylabel='Maximum relative power difference')
    axes[2].bar(indices,[c['available_u3_cells'] for c in q['cases']],label='numerically available');axes[2].bar(indices,[c['unavailable_u3_cells'] for c in q['cases']],bottom=[c['available_u3_cells'] for c in q['cases']],label='unavailable');axes[2].set(title='Explicit numerical availability',ylabel='Channel-triangle cells');axes[2].legend(fontsize=7)
    for ax in axes:ax.set_xlabel('Fixed synthetic condition index');ax.grid(alpha=.2)
    fig.suptitle('Finite arithmetic only; no independent-mode, detector or image confidence claim',fontsize=10);fig.tight_layout();fig.savefig(path,dpi=140);plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    q=run(a.output);print(json.dumps({'state':q['state'],'conditions':len(q['cases'])}))


if __name__=='__main__':main()
