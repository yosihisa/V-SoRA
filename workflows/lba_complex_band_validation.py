"""Finite USB complex-band operator and unchanged real LBA fragment study."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
from vsora_formats.lba import LBAFragmentRecording
from vsora_formats.lba_band import LBAComplexBandView, _mix_and_filter


WINDOWS = ((64,1),(65,7),(1027,4096),(1028,4097),(65539,16384),(2097075,13))
RTOL = 1e-11
ATOL = 1e-8


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def independent_coefficients():
    k=np.arange(-64,65,dtype=float)
    window=np.i0(8.6*np.sqrt(np.maximum(0,1-(k/64)**2)))/np.i0(8.6)
    h=(7/16)*np.sinc((7/16)*k)*window
    return h/h.sum()


def finite_reference(real,source_first):
    """Independent centered finite sum; no SciPy or product convolution call."""
    h=independent_coefficients();count=len(real)-128
    assert count>0
    n=(source_first+np.arange(len(real),dtype=np.int64))%4
    oscillator=np.cos(np.pi*n/2)-1j*np.sin(np.pi*n/2)
    output=np.zeros(count,dtype=complex)
    for tap in range(129):
        output+=2*h[tap]*real[tap:tap+count]*oscillator[tap:tap+count]
    return output


def operator_probes(coefficients):
    reference=independent_coefficients()
    np.testing.assert_allclose(coefficients,reference,rtol=1e-13,atol=5e-15)
    k=np.arange(-64,65,dtype=float)
    response=[];actual=[];expected=[];first=16777218;count=257
    full=first+np.arange(count+128,dtype=np.int64)
    centers=full[64:64+count]%16
    for integer in range(-3,4):
        mu=integer/16;image=(-8-integer)/16
        wanted=np.sum(reference*np.cos(2*np.pi*mu*k))
        mirror=np.sum(reference*np.cos(2*np.pi*image*k))
        assert abs(wanted-1)<=1e-3 and abs(mirror)<=1e-3
        response.append([mu,wanted,mirror])
        for phase in [0.,.3]:
            real=24576*np.cos(2*np.pi*(4+integer)*(full%16)/16+phase)
            got=_mix_and_filter(real,first)
            model=24576*(wanted*np.exp(1j*(2*np.pi*integer*centers/16+phase))
                         +mirror*np.exp(1j*(2*np.pi*(-8-integer)*centers/16-phase)))
            np.testing.assert_allclose(got,model,rtol=RTOL,atol=ATOL)
            actual.append(got);expected.append(model)
    return {'coefficients':coefficients,'independent_coefficients':reference,
            'tone_actual':np.array(actual),'tone_expected':np.array(expected),
            'response_grid':np.array(response)}


def run(inputs,baseline,output):
    inputs,baseline,output=map(Path,(inputs,baseline,output))
    if output.exists():raise FileExistsError('choose a new complex-band study directory')
    receipt_path=inputs/'receipt.json';receipt_sha=sha(receipt_path);receipt=json.loads(receipt_path.read_text())
    assert receipt['state']=='complete'
    def unchanged():
        assert sha(receipt_path)==receipt_sha
        for row in receipt['reads']:
            path=inputs/row['file'];assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256']
    unchanged();output.mkdir(parents=True);began=time.monotonic()
    before=int(Path('/proc/self/statm').read_text().split()[1])*resource.getpagesize()
    arrays={};identities={};streams={};diagnostics=[];max_error=0.;samples=0;probes=None
    for station in receipt['plan']['stations']:
        name=station['id'];folder=inputs/('station-'+name)
        rows={Path(x['file']).name:x for x in receipt['reads'] if x['file'].startswith('station-'+name+'/')}
        reader=LBAFragmentRecording(folder/'header.bin',folder/'payload.bin',station['payload_offset'],
            nominal_sample_rate_hz=8000000,recorded_pol_order=station['recorded_pol_order'],
            expected_header_sha256=rows['header.bin']['sha256'],expected_payload_sha256=rows['payload.bin']['sha256'])
        with np.load(baseline/('station-'+name+'.npz')) as archive:levels=archive['levels']
        identities[name]={}
        for pol in [0,1]:
            view=LBAComplexBandView(reader,recorded_pol_index=pol,sideband='U')
            assert view.actual_sample_rate_hz is None and view.station_id is None
            assert view.center_frequency_hz is None and view.nominal_start_utc==reader.nominal_start_utc
            assert view.nominal_sample_rate_hz==8000000 and view.valid_sample_count==2097024
            if probes is None:probes=operator_probes(view.filter_coefficients)
            digests=[]
            for size in [4096,16384]:
                stream=LBAComplexBandView(reader,recorded_pol_index=pol,sideband='U',chunk_samples=size)
                digest=hashlib.sha256();next_index=64
                for chunk in stream.iter_complex_chunks():
                    value=chunk['complex_samples'];assert value.dtype==np.complex128
                    assert chunk['sample_index']==next_index
                    assert chunk['polarization_label']==station['recorded_pol_order'][pol]
                    assert chunk['nominal_source_sample_index']==station['payload_offset']*2+next_index
                    assert chunk['nominal_offset_s']==next_index/8000000
                    assert 'data' not in chunk and 'time' not in chunk
                    digest.update(value.tobytes());next_index+=len(value)
                assert next_index==2097088;digests.append(digest.hexdigest())
            assert digests[0]==digests[1];streams[f'{name}-p{pol}']=digests[0];samples+=view.valid_sample_count
            for start,count in WINDOWS:
                got=view.read_complex_samples(start,count)
                real=levels[start-64:start+count+64,pol].astype(float)
                expected=finite_reference(real,station['payload_offset']*2+start-64)
                np.testing.assert_allclose(got,expected,rtol=RTOL,atol=ATOL)
                max_error=max(max_error,float(np.max(abs(got-expected))))
                arrays[f'{name}-p{pol}-s{start}-n{count}']=got
            identities[name][str(pol)]=view.processing_identity
        assert reader.payload_hash_reads==1 and reader.maximum_payload_read_bytes<=8258
        diagnostics.append({'id':name,'constructor_payload_hash_reads':reader.payload_hash_reads,
                            'constructor_payload_hash_bytes':reader.payload_hash_bytes,
                            'payload_read_calls':reader.payload_read_calls,
                            'payload_bytes_read':reader.payload_bytes_read,
                            'maximum_payload_read_bytes':reader.maximum_payload_read_bytes})
        unchanged()
    assert samples==16776192 and len(arrays)==48 and len(probes)==5
    np.savez_compressed(output/'bounded-band.npz',**arrays)
    np.savez_compressed(output/'operator-probes.npz',**probes)
    summary={'state':'complete','input_kind':'unchanged provider-described real stage178 LBA fragments',
             'new_operator':'supplied-USB real polarization, quarter-band mixing, centered finite FIR',
             'valid_complex_samples_per_streaming_selection':samples,'stream_chunk_sizes':[4096,16384],
             'fixed_real_seek_cases':len(arrays),'NPZ_fields':53,'stream_sha256':streams,
             'processing_identities':identities,'read_diagnostics':diagnostics,
             'constructor_full_data_hash_file_reads':4,'constructor_full_data_hash_bytes':4194304,
             'independent_real_window_max_abs_error':max_error,
             'synthetic_decoded_tone_cases':14,'synthetic_tone_output_count':257,
             'synthetic_tone_max_abs_error':float(np.max(abs(probes['tone_actual']-probes['tone_expected']))),
             'max_pass_error_on_seven_fixed_points':float(np.max(abs(probes['response_grid'][:,1]-1))),
             'max_image_gain_on_seven_fixed_points':float(np.max(abs(probes['response_grid'][:,2]))),
             'continuous_band_bound_proved':False,'RTOL':RTOL,'ATOL_code_unit':ATOL,'MCSE':None,
             'actual_clock_measured':False,'physical_voltage_calibrated':False,
             'new_acquisition_or_original_file_change':False,'new_correlation_Closure_image_or_MC':False,
             'hash_count_scope':'Constructor data hash only; workflow input rechecks and sample reads are additional I/O',
             'limits':'Finite sample-domain transform, no perfect analytic signal, sky detection, actual clock or session connection',
             'wall_s':time.monotonic()-began,'import_current_RSS_bytes':before,
             'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
             'conservative_additional_peak_bytes':max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024-before)}
    unchanged();write(output/'summary.json',summary)
    write(output/'environment.json',{'product_modules':{n:m.__file__ for n,m in sys.modules.items()
              if n.startswith('vsora_') and getattr(m,'__file__',None)}})
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['input','baseline','output']:p.add_argument('--'+name,required=True)
    a=p.parse_args();print(json.dumps(run(a.input,a.baseline,a.output)))
