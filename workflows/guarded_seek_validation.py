"""Compare identical late VDIF chunks and a sparse 30-second buffer benchmark."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import time
import numpy as np
import astropy.units as u
from baseband import vdif
from vsora_correlator.aligned import correlate_aligned,SampleBuffer
from vsora_formats.spectral import load_spectral
from vsora_formats.vdif import write_vdif


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def correlate_late(manifest,clock,rate,output,sequential=False):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);root=Path(manifest).resolve().parent
    c=json.loads(Path(manifest).read_text());c['blocks_per_integration']=round(.3*c['sample_rate_hz']/c['fft_length'])
    c['observation_config']=str((root/c['observation_config']).resolve())
    input_hashes=[]
    for station in c['stations']:
        station['vdif']=str((root/station['vdif']).resolve());input_hashes.append(sha(station['vdif']))
    local=out/'local-manifest.json';local.write_text(json.dumps(c,indent=2)+'\n')
    begin=time.perf_counter();result=correlate_aligned(local,clock,out/'correlation',1,2.502,rate,seek_input=not sequential)
    summary={'state':'complete','mode':'sequential' if sequential else 'seek','input_vdif_sha256':input_hashes,
        'input_manifest_sha256':sha(manifest),'input_clock_sha256':sha(clock),'input_rate_sha256':sha(rate),
        'wall_elapsed_s':time.perf_counter()-begin,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'correlation':result}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


def sparse_input(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);seed=out/'frame.vdif'
    write_vdif(seed,np.ones(4096,complex),'2026-10-02T08:00:00Z',2048000,1)
    with vdif.open(seed,'rb') as reader:header=reader.read_header().copy()
    seconds=header['seconds'];path=out/'thirty-seconds.vdif';frames=15000
    with path.open('wb') as stream:
        for index in range(frames):
            header['seconds']=seconds+index//500;header['frame_nr']=index%500
            header.tofile(stream);stream.seek(header.payload_nbytes,1)
        stream.truncate(frames*header.frame_nbytes)
    summary={'frames':frames,'logical_bytes':path.stat().st_size,'allocated_bytes':path.stat().st_blocks*512,
        'decoded_payload':'Sparse holes are encoded zero bytes, a constant decoded complex ADC value. Not receiver noise or sky.',
        'sample_rate_hz':2048000,'duration_s':30.,'sha256':sha(path)}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


def buffer_benchmark(path,output,sequential=False):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);fs=2048000
    buffer=SampleBuffer(path,fs,1,1.,fs,seek_input=not sequential)
    try:
        begin=time.perf_counter();values,mask=buffer.query(29.5*fs+np.arange(8192)+.35)
        elapsed=time.perf_counter()-begin
        np.savez(out/'values.npz',values=values,mask=mask)
        summary={'mode':'sequential' if sequential else 'seek','elapsed_s':elapsed,'frames_decoded':buffer.frames_read,
            'read_start_sample':buffer.initial_sample_index,'maximum_buffer_samples':buffer.maximum,
            'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'scope':'Single station, sparse constant payload, 30s logical VDIF; late query at 29.5s. Algorithm/count benchmark, not storage-device throughput or scientific sensitivity.'}
        (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary
    finally:buffer.close()


def run(manifest,clock,rate,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    runner=str(Path(__file__).resolve().parents[1]/'tools/run.py')
    for mode in ['sequential','seek']:
        command=[sys.executable,runner,'workflows.guarded_seek_validation','correlation','--manifest',manifest,
                 '--clock-model',clock,'--rate-profile',rate,'--output',str(out/mode)]
        if mode=='sequential':command.append('--sequential')
        with (out/(mode+'.log')).open('w') as log:
            subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
    actual=load_spectral(out/'seek/correlation/shard-00000.npz');reference=load_spectral(out/'sequential/correlation/shard-00000.npz')
    differences={}
    for key,expected in reference.items():
        if not isinstance(expected,np.ndarray):continue
        observed=actual[key];assert observed.shape==expected.shape
        if np.issubdtype(expected.dtype,np.inexact):
            normalized=float(abs(observed-expected).max()/max(float(abs(expected).max()),1.))
            assert normalized<1e-13,(key,normalized);differences[key]=normalized
        else:assert np.array_equal(observed,expected),key
    sparse=sparse_input(out/'sparse-input')
    for mode in ['sequential','seek']:
        command=[sys.executable,runner,'workflows.guarded_seek_validation','buffer','--input',str(out/'sparse-input/thirty-seconds.vdif'),'--output',str(out/f'buffer-{mode}')]
        if mode=='sequential':command.append('--sequential')
        with (out/('buffer-'+mode+'.log')).open('w') as log:
            subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
    with np.load(out/'buffer-sequential/values.npz') as a,np.load(out/'buffer-seek/values.npz') as b:
        np.testing.assert_array_equal(a['mask'],b['mask']);np.testing.assert_allclose(a['values'],b['values'],atol=1e-14,rtol=1e-14)
    summaries={mode:json.loads((out/mode/'summary.json').read_text()) for mode in ['sequential','seek','buffer-sequential','buffer-seek']}
    summary={'type':'guarded_vdif_seek','runs':summaries,'maximum_normalized_spectral_differences':differences,'sparse_generating':sparse,
        'scope':'One four-station 3.04s point-noise VDIF, same 0.3s late interval and existing rate profile; independent process benchmarks. No continuous hours, real receiver, storage throughput or nonlinear clock validation.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();commands=p.add_subparsers(dest='command',required=True)
    for name in ['run','correlation']:
        c=commands.add_parser(name);c.add_argument('--manifest',required=True);c.add_argument('--clock-model',required=True)
        c.add_argument('--rate-profile',required=True);c.add_argument('--output',required=True)
        if name=='correlation':c.add_argument('--sequential',action='store_true')
    c=commands.add_parser('buffer');c.add_argument('--input',required=True);c.add_argument('--output',required=True);c.add_argument('--sequential',action='store_true')
    a=p.parse_args()
    if a.command=='run':s=run(a.manifest,a.clock_model,a.rate_profile,a.output)
    elif a.command=='correlation':s=correlate_late(a.manifest,a.clock_model,a.rate_profile,a.output,a.sequential)
    else:s=buffer_benchmark(a.input,a.output,a.sequential)
    print(json.dumps(s,indent=2))
