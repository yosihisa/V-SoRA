"""実整列APIの幾何/RF-rate位相と有限probe平均を独立係数へ照合する。"""
import argparse
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import sys
import sysconfig
from unittest.mock import patch

import astropy.units as u
from astropy.time import Time
import numpy as np
from vsora_correlator import aligned
from vsora_correlator.stream_fx import FXAccumulator
from vsora_formats.spectral import load_spectral
from vsora_observation import load_config
from vsora_observation.geometry import geometry_at_times

spec=importlib.util.spec_from_file_location('existing_clock_reference',Path(__file__).with_name('clock_operator_validation.py'))
clock_reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(clock_reference)
FS, LENGTH, FFT, BLOCKS=2048000.,512,8,16
START=96/FS;SPAN=FFT*BLOCKS/FS
RTOL,ATOL=1e-9,1e-10


def direct_operator(queries,phase,taps):
    """既存146の独立tapと任意queryを、実補間を呼ばず直接合成する。"""
    m=np.arange(-32,33);positions=queries+32
    indices=np.floor(positions).astype(int)[:,None]+m
    distance=positions[:,None]-indices
    weights=np.sinc(distance)*np.where(abs(distance)<=32,(1+np.cos(np.pi*distance/32))/2,0.)
    weights/=weights.sum(axis=1)[:,None]
    operator=np.zeros((FFT*BLOCKS,LENGTH))
    rows=np.broadcast_to(np.arange(FFT*BLOCKS)[:,None],indices.shape)
    for lag,tap in enumerate(taps):
        raw_index=indices-lag
        assert raw_index.min()>=0 and raw_index.max()<LENGTH
        np.add.at(operator,(rows.ravel(),raw_index.ravel()),(weights*tap).ravel())
    sample=operator*phase[:,None]
    channels=(np.arange(FFT)+FFT//2)%FFT
    dft=np.exp(-2j*np.pi*channels[:,None]*np.arange(FFT)/FFT)/np.sqrt(FFT)
    return sample,np.einsum('cs,bsr->cbr',dft,sample.reshape(BLOCKS,FFT,LENGTH))


def modal_mean(h,modes):
    z=np.einsum('scbn,snr->scbr',h,modes)
    return np.stack([(z[i]*z[j].conj()).mean(axis=(1,2)) for i,j in [(0,1),(0,2),(1,2)]],axis=-1)


def run(raw_reference,output):
    out=Path(output).resolve()
    if out.exists():raise FileExistsError('choose a new aligned mean output')
    out.mkdir(parents=True)
    base=Path(raw_reference).resolve()/'high_a/input'
    obs=deepcopy(json.loads((base/'observation.json').read_text()));obs['stations']=obs['stations'][:3]
    obs['observation']['integration_s']=SPAN
    (out/'observation.json').write_text(json.dumps(obs,indent=2)+'\n')
    old=json.loads((base/'manifest.json').read_text());stations=deepcopy(old['stations'][:3])
    for row in stations:row['vdif']=str(base/row['vdif']);row['decoded_voltage_scale']=1.
    manifest={**old,'observation_config':'observation.json','fft_length':FFT,'blocks_per_integration':BLOCKS,'stations':stations}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    ids=[s['id'] for s in stations];numeric={s['station_numeric_id']:i for i,s in enumerate(stations)}
    clock={'schema_version':1,'max_abs_baseband_hz':.3*FS,'stations':[{'id':s,'input_start_offset_s':0.,'actual_sample_rate_hz':FS} for s in ids]}
    (out/'clock.json').write_text(json.dumps(clock,indent=2)+'\n')
    config=load_config(out/'observation.json');origin=Time(config['observation']['start_utc'])
    edges=np.array([START,START+SPAN]);g=geometry_at_times(config,origin+edges*u.s,filter_elevation=False)
    t=START+np.arange(FFT*BLOCKS)/FS
    fraction=(t-START)/SPAN
    delay=g['station_delay_s'][0,:,None]+(g['station_delay_s'][1]-g['station_delay_s'][0])[:,None]*fraction
    queries=(t[None,:]-delay)*FS
    _,_,taps=clock_reference.finite_operator(1.,0.)
    gains=np.array([1.,.8,1.1])*np.exp(1j*np.array([0.,.3,-.7]))
    frequencies=FS*np.array([.03125,.15625,-.21875])
    modes=gains[:,None,None]*np.exp(2j*np.pi*np.arange(LENGTH)[None,:,None]*frequencies[None,None,:]/FS)
    arrays={'modes':modes,'queries':queries,'delay_s':delay,'evaluation_time_s':t,'independent_taps':taps}
    records=[]
    for label,rates in [('geometry_only',np.zeros(3)),('supplied_rate',np.array([0.,700.,-1100.]))]:
        profile=None
        if label=='supplied_rate':
            profile=out/'rate.json'
            profile.write_text(json.dumps({'schema_version':1,'type':'station_rate_only','station_ids':ids,'station_indices':[0,1,2],'station_rates_hz':rates.tolist(),'time_origin_utc':obs['observation']['start_utc'],'valid_time_range_s':edges.tolist(),'sample_cadence_s':1/FS,'time_reference_s':START},indent=2)+'\n')
        phase=np.exp(-2j*np.pi*(obs['observation']['frequency_hz']*delay+rates[:,None]*(t[None,:]-delay-START)))
        sample=[];h=[];no_rf=[];opposite=[]
        for s in range(3):
            a,b=direct_operator(queries[s],phase[s],taps);sample.append(a);h.append(b)
            no_rf.append(direct_operator(queries[s],np.exp(-2j*np.pi*rates[s]*(t-delay[s]-START)),taps)[1])
            opposite.append(direct_operator(queries[s],np.exp(-2j*np.pi*(obs['observation']['frequency_hz']*delay[s]-rates[s]*(t-delay[s]-START))),taps)[1])
        sample=np.array(sample);h=np.array(h);expected=modal_mean(h,modes)
        captured=[];all_vis=[];maximum_voltage=0.;maximum_visibility=0.;summaries=[]
        class CaptureFX(FXAccumulator):
            def consume(self,data,valid):
                assert valid.all();captured.append(data.copy());return super().consume(data,valid)
        for mode in range(3):
            for sign in [-1,1]:
                raw=sign*modes[:,:,mode]
                def frames(path,nominal_rate,station_id,scale,*,start_sample=0):
                    assert start_sample==0 and nominal_rate==FS and scale==1.
                    values=raw[numeric[station_id]]
                    for first in range(0,LENGTH,64):yield {'sample_index':first,'data':values[first:first+64],'valid':np.ones(64,bool)}
                captured.clear();destination=out/f'{label}-{mode}-{sign}'
                with patch.object(aligned,'iter_vdif_frames',frames),patch.object(aligned,'FXAccumulator',CaptureFX):
                    summary=aligned.correlate_aligned(out/'manifest.json',out/'clock.json',destination,1,start_offset_s=START,rate_profile=profile,seek_input=False)
                assert len(captured)==1
                predicted=np.einsum('stn,sn->st',sample,raw)
                np.testing.assert_allclose(captured[0],predicted,rtol=RTOL,atol=ATOL)
                maximum_voltage=max(maximum_voltage,float(abs(captured[0]-predicted).max()))
                z=np.einsum('scbn,sn->scb',h,raw)
                visibility=np.stack([(z[i]*z[j].conj()).mean(axis=1) for i,j in [(0,1),(0,2),(1,2)]],axis=-1)
                actual=load_spectral(destination/'shard-00000.npz')
                np.testing.assert_allclose(actual['visibilities'][0],visibility,rtol=RTOL,atol=ATOL)
                np.testing.assert_allclose(actual['diagnostic_station_power'][0],np.mean(abs(z)**2,axis=2).T,rtol=RTOL,atol=ATOL)
                maximum_visibility=max(maximum_visibility,float(abs(actual['visibilities'][0]-visibility).max()))
                assert actual['metadata']['clock_mapping_applied'] and actual['metadata']['phase_center_corrected']
                assert np.all(actual['valid_fft_count']==BLOCKS)
                all_vis.append(actual['visibilities'][0]);summaries.append(summary)
        observed=np.mean(all_vis,axis=0);np.testing.assert_allclose(observed,expected,rtol=RTOL,atol=ATOL)
        no_rf_mean=modal_mean(np.array(no_rf),modes);flip_mean=modal_mean(np.array(opposite),modes)
        rf_difference=float(np.linalg.norm(no_rf_mean-expected)/np.linalg.norm(expected));flip_difference=float(np.linalg.norm(flip_mean-expected)/np.linalg.norm(expected))
        assert rf_difference>1e-4
        if label=='supplied_rate':assert flip_difference>1e-4
        arrays.update({label+'_sample_operator':sample,label+'_FFT_operator':h,label+'_actual_visibilities':np.array(all_vis),label+'_expected_mean':expected,label+'_observed_mean':observed,label+'_no_rf_mean':no_rf_mean,label+'_opposite_rate_mean':flip_mean})
        records.append({'condition':label,'API_calls':6,'station_rates_hz_supplied_not_estimated':rates.tolist(),'maximum_voltage_error':maximum_voltage,'maximum_visibility_error':maximum_visibility,'maximum_mean_error':float(abs(observed-expected).max()),'omitted_RF_phase_relative_mean_difference':rf_difference,'opposite_rate_sign_relative_mean_difference':flip_difference,'all_summaries':summaries})
    np.savez_compressed(out/'arrays.npz',**arrays)
    summary={'stage':152,'state':'complete','conditions':records,'station_count':3,'raw_samples_per_station':LENGTH,'fft':FFT,'blocks':BLOCKS,'span_s':SPAN,'input_ensemble':'three deterministic mode columns with plus/minus sign; zero finite mean, second moment A A* /3; not Gaussian/proper/IID sampling','MC_trials':0,'seed_MCSE_applicable':False,'rtol':RTOL,'atol':ATOL,'negative_control_threshold':1e-4,'actual_API_calls':12,'all_channels_and_pairs_checked':True,'physical_VDIF_payload_decoded':False,'real_clock_geometry_accuracy_or_noise_covariance_validated':False,'geometry_values_shared_with_reference_not_independently_verified':True,'source131_raw_payload_used_for_science':False,'product_code_changed':False,'limits':'Real JSON loader/clock/profile validation, real geometry/SampleBuffer/phase/FX/save with synthetic decoded frame reader. Known corrections and rank3 finite probes only. No quantization/inference/selection/Closure/RML/real observation calibration.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    modules={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('vsora_') and getattr(m,'__file__',None)}
    (out/'module-paths-private.json').write_text(json.dumps(modules,indent=2)+'\n')
    assert sum(n.stat().st_size for n in out.rglob('*') if n.is_file())<64*1024**2
    print(json.dumps({'state':'complete','API_calls':12,'conditions':[{k:v for k,v in row.items() if k!='all_summaries'} for row in records]}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--raw-reference',required=True);parser.add_argument('--output',required=True);args=parser.parse_args();run(args.raw_reference,args.output)
