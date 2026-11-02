"""Bounded real-polarization API against the unchanged saved stage178 decode.

This adds no acquisition, complex conversion, physical clock or correlation.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
from vsora_formats.lba import LBAFragmentRecording


WINDOWS=((0,1),(1,7),(3,4097),(1023,65536),(1,65536),(2097139,13))


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def run(inputs,baseline,output):
    inputs,baseline,output=map(Path,(inputs,baseline,output))
    if output.exists():raise FileExistsError('choose a new reader validation directory')
    receipt_path=inputs/'receipt.json';receipt_sha=sha(receipt_path);receipt=json.loads(receipt_path.read_text())
    assert receipt['state']=='complete'
    def unchanged():
        assert sha(receipt_path)==receipt_sha
        for row in receipt['reads']:
            p=inputs/row['file'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
    unchanged();output.mkdir(parents=True);began=time.monotonic()
    before=int(Path('/proc/self/statm').read_text().split()[1])*resource.getpagesize()
    identities={};digests={};arrays={};records=[];components=0
    nominal=dt.datetime.fromisoformat(receipt['plan']['selected_start_utc'].replace('Z','+00:00'))
    epoch=nominal.strftime('%Y-%m-%dT%H:%M:%S')+f'.{nominal.microsecond*1000:09d}Z'
    for station in receipt['plan']['stations']:
        name=station['id'];folder=inputs/('station-'+name)
        rows={Path(row['file']).name:row for row in receipt['reads'] if row['file'].startswith('station-'+name+'/')}
        reader=LBAFragmentRecording(folder/'header.bin',folder/'payload.bin',station['payload_offset'],
            nominal_sample_rate_hz=8000000,recorded_pol_order=station['recorded_pol_order'],chunk_samples=4096,
            expected_header_sha256=rows['header.bin']['sha256'],expected_payload_sha256=rows['payload.bin']['sha256'])
        assert reader.nominal_start_utc==epoch and reader.sample_count==2097152
        assert reader.actual_sample_rate_hz is None and not reader.is_complex and reader.station_id is None
        assert reader.band_edge_frequency_hz is None and not reader.clock_accuracy_measured
        assert reader.expected_pair_verified and reader.payload_hash_reads==1 and reader.payload_hash_bytes==1048576
        with np.load(baseline/('station-'+name+'.npz')) as stored:expected=stored['levels']
        for pol in [0,1]:
            digest=hashlib.sha256();next_index=0
            for chunk in reader.iter_real_chunks(recorded_pol_index=pol):
                values=chunk['real_samples'];index=chunk['sample_index'];assert index==next_index
                np.testing.assert_array_equal(values,expected[index:index+len(values),pol])
                assert values.dtype==np.int16 and chunk['read_ok'] and 'data' not in chunk and 'time' not in chunk
                assert chunk['polarization_label']==station['recorded_pol_order'][pol]
                assert chunk['nominal_source_sample_index']==station['payload_offset']*2+index
                digest.update(values.tobytes());next_index+=len(values);components+=len(values)
            assert next_index==reader.sample_count
            assert digest.hexdigest()==hashlib.sha256(expected[:,pol].tobytes()).hexdigest()
            digests[name+'-p'+str(pol)]=digest.hexdigest()
            for start,count in WINDOWS:
                values=reader.read_real_samples(start,count,recorded_pol_index=pol)
                np.testing.assert_array_equal(values,expected[start:start+count,pol])
                arrays[f'{name}-p{pol}-s{start}-n{count}']=values
        assert reader.maximum_payload_read_bytes==32770 and reader.payload_read_calls==1036
        identities[name]=reader.fragment_identity
        records.append({'id':name,'max_payload_read_bytes':reader.maximum_payload_read_bytes,
                        'payload_read_calls':reader.payload_read_calls,'payload_bytes_read':reader.payload_bytes_read,
                        'constructor_payload_hash_reads':reader.payload_hash_reads,'constructor_payload_hash_bytes':reader.payload_hash_bytes})
        unchanged()
    assert components==16777216 and len(arrays)==48
    np.savez_compressed(output/'bounded-reads.npz',**arrays)
    summary={'state':'complete','input_kind':'unchanged provider-described real stage178 LBA fragments',
             'exact_real_components':components,'seek_cases':len(arrays),'reader_chunk_samples':4096,
             'full_data_hash_file_reads':4,'full_data_hash_bytes':4194304,
             'fragment_identities':identities,'sequential_sha256':digests,'read_diagnostics':records,
             'nominal_start_utc':epoch,'actual_clock_measured':False,'complex_conversion':False,
             'new_acquisition_correlation_closure_image_or_MC':False,'MCSE':None,
             'limits':'Real code values only; supplied nominal grid and polarization context, no RF/station inference, file lock or producer authentication',
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
