"""Fixed transport fixtures, not Monte Carlo calibration or image validation."""
import hashlib,json
from itertools import combinations
from pathlib import Path
import numpy as np
from vsora_correlator.bispectrum_accumulator import BispectrumAccumulator
from vsora_formats.bispectrum import save_bispectrum,load_bispectrum
from vsora_formats.spectral import save_spectral
from vsora_simulator.bispectrum_observed_power import observed_power_normalized_bispectrum

def _write(path,q):
    path.write_text(json.dumps(q,indent=2,allow_nan=False)+'\n')


def fixture(out,windows=8,modes=128,copied=False,version=2,zero=False,masked=False):
    out.mkdir(parents=True)
    rng=np.random.default_rng(9380);draw=1 if copied else windows
    z=(rng.normal(size=(draw,modes,4,4))+1j*rng.normal(size=(draw,modes,4,4)))/np.sqrt(2)
    root=np.linalg.cholesky(np.ones((4,4))+np.eye(4)*2)
    base=z@root.T
    if copied:base=np.repeat(base,windows,axis=0)
    gains=np.exp(rng.uniform(-.8,.8,size=(windows,1,1,4))+1j*rng.uniform(-np.pi,np.pi,size=(windows,1,1,4)))
    x=base*gains
    if zero:x[:,:,:,0]=0
    results=[]
    for window in x:
        acc=BispectrumAccumulator(4,4);acc.consume(window,np.ones((modes,4),bool));results.append(acc.finish())
    times=(np.arange(windows,dtype=float)+.5)*modes*4/2048
    frequencies=1.42e9+np.fft.fftshift(np.fft.fftfreq(4,1/2048))
    pairs=np.array(list(combinations(range(4),2)))
    vis=np.stack([(x[:,:,:,i]*x[:,:,:,j].conj()).mean(axis=1) for i,j in pairs],axis=-1)
    source=out/'visibility.npz';raw=out/'raw.npz';ids=['A0','A1','A2','A3'];epoch='2026-10-17T00:00:00Z'
    save_spectral(source,{'visibilities':vis,'weights':np.ones_like(vis.real),
        'uvw_lambda':np.zeros(vis.shape+(3,)),'pairs':pairs,'times_s':times,'frequencies_hz':frequencies,
        'valid_fft_count':np.full((windows,6),modes)}, {'visibility_unit':'ADC^2','time_origin_utc':epoch,
        'config':{'stations':[{'id':v} for v in ids]},'fft_length':4,'fft_sample_rate_hz':2048.})
    data={'triangles':results[0]['triangles'],'times_s':times,'frequencies_hz':frequencies,
          'common_fft_count':np.stack([r['common_sample_count'] for r in results]),
          'nominal_fft_count':np.full(windows,modes),
          'channel_triangle_usable':np.full((windows,4,4),modes>=3)}
    for key in ('edge_sums','paired_edge_sums','triple_edge_sum','common_station_power_sums'):
        data[key]=np.stack([r[key] for r in results])
    if masked:data['channel_triangle_usable'][-1,1,0]=False
    if version==1:data.pop('common_station_power_sums')
    save_bispectrum(raw,data,{'station_ids':ids,'time_origin_utc':epoch,'voltage_unit':'ADC',
        'fft_length':4,'sample_rate_hz':2048.,'visibility_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'processing_notes':['Synthetic spectral transport fixture. Copied windows are dependent counterexample.']},schema_version=version)
    direct=None;gain_error=None
    if modes>=3 and not zero:
        direct=observed_power_normalized_bispectrum(x.transpose(0,2,1,3))['observed_power_normalized_u3'][:,1].imag
        unscaled=observed_power_normalized_bispectrum(base.transpose(0,2,1,3))['observed_power_normalized_u3'][:,1].imag
        gain_error=float(np.max(abs(direct-unscaled)));assert gain_error<=2e-12
    return raw,source,direct,gain_error


def run(output,real_raw,real_source):
    from vsora_correlator.bispectrum_window_symmetry import inspect_bispectrum_window_file
    out=Path(output);out.mkdir(parents=True,exist_ok=False);cases=[]
    specifications=[('independent',{}),('copied',{'copied':True}),('single',{'windows':1}),
                    ('legacy',{'version':1}),('m2',{'modes':2}),('masked',{'masked':True}),('zero',{'zero':True})]
    # Copy the genuine producer result so installed CLI needs only external inputs.
    import shutil
    directory=out/'vdif';directory.mkdir()
    shutil.copyfile(real_raw,directory/'raw.npz');shutil.copyfile(real_source,directory/'visibility.npz')
    fixtures=[('vdif',directory/'raw.npz',directory/'visibility.npz',None,None)]
    for name,options in specifications:
        fixtures.append((name,*fixture(out/name,**options)))
    for name,raw,source,direct,gain_error in fixtures:
        success=name in ('vdif','independent','copied','single')
        try:q=inspect_bispectrum_window_file(raw,source,out/name/'window-test.json',10 if name=='vdif' else 1)
        except ValueError:
            assert not success and not (out/name/'window-test.json').exists()
            q=None
        else:
            assert success
        maximum=None
        if q is not None and direct is not None:
            difference=np.asarray(q['imaginary_normalized_u3'])-direct
            maximum=float(np.max(abs(difference)));assert maximum<=2e-12
        if name=='copied':
            assert q['conditional_test']['upper_tail_p_value']==2/256
            assert not q['window_independence_verified']
        cases.append({'case_id':name,'expected_success':success,'channel_index':10 if name=='vdif' else 1,
            'result':q,'maximum_difference_from_voltage_api':maximum,
            'maximum_fixed_window_gain_difference':gain_error,
            'synthetic_modes_independent_by_generation':name=='independent',
            'copied_windows_dependent_control':name=='copied'})
    result={'state':'complete','cases':cases,'case_count':len(cases),
        'array_feature_transport_checked':True,'new_monte_carlo_performed':False,
        'actual_iq_fft_processed_in_this_stage':False,'frozen_vdif_result_from_stage091':True,
        'null_invariance_verified_from_saved_data':False,'production_rml_noise_model_changed':False,
        'real_hardware_validation_performed':False}
    _write(out/'summary.json',result);return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--real-raw',required=True)
    p.add_argument('--real-source',required=True)
    q=run(**vars(p.parse_args()));print(json.dumps({'state':q['state'],'cases':q['case_count']}))
