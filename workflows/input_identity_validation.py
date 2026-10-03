"""Count full source-hash reads and compare fixed sequence science arrays."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import vsora_correlator.input_identity as identities
from vsora_correlator.sequence import process_sequence
from vsora_correlator.session import load_session
from vsora_formats.spectral import load_spectral


def run(manifest,clock,reference,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);c=load_session(manifest)
    paths=[(c['_root']/s['vdif']).resolve() for s in c['stations']]
    old_reads=0;old_bytes=0;old_hashes=[];begin=time.monotonic()
    # Reproduce only the old three full SHA passes, not old radio/RML execution.
    for index in range(3):
        digests=[]
        for path in paths:
            with path.open('rb') as stream:digests.append(hashlib.file_digest(stream,'sha256').hexdigest())
            old_reads+=1;old_bytes+=path.stat().st_size
        old_hashes.append(digests)
    old_elapsed=time.monotonic()-begin
    assert old_hashes[0]==old_hashes[1]==old_hashes[2]
    digest=identities.digest_file;reads=[]
    def observe(path):
        start=time.monotonic();value=digest(path)
        reads.append({'kind':'vdif' if path in paths else 'metadata','bytes':path.stat().st_size,
                      'elapsed_s':time.monotonic()-start});return value
    identities.digest_file=observe
    try:
        begin=time.monotonic()
        result=process_sequence(manifest,clock,out/'sequence',window_count=3,starts=1,max_iterations=100)
        elapsed=time.monotonic()-begin
    finally:identities.digest_file=digest
    expected=load_spectral(reference);observed=load_spectral(out/'sequence/synthesis/visibility.npz');differences={}
    for key,value in expected.items():
        if not isinstance(value,np.ndarray):continue
        np.testing.assert_array_equal(value,observed[key])
        if np.issubdtype(value.dtype,np.inexact):differences[key]=float(abs(value-observed[key]).max())
    vdif_reads=[x for x in reads if x['kind']=='vdif'];metadata_reads=[x for x in reads if x['kind']=='metadata']
    assert len(vdif_reads)==4 and sum(x['bytes'] for x in vdif_reads)==sum(p.stat().st_size for p in paths)
    assert [r['sha256'] for r in result['input_vdif']]==old_hashes[0]
    assert result['input_identity']['vdif_hash_file_reads']==4
    summary={'type':'shared_input_identity_validation',
        'legacy_hash_only':{'actual_vdif_full_reads':old_reads,'actual_vdif_hash_bytes':old_bytes,'elapsed_s':old_elapsed},
        'new_sequence':{'actual_vdif_full_hash_reads':len(vdif_reads),'actual_vdif_hash_bytes':sum(x['bytes'] for x in vdif_reads),
            'actual_metadata_hash_reads':len(metadata_reads),'actual_metadata_hash_bytes':sum(x['bytes'] for x in metadata_reads),
            'hash_only_elapsed_s':sum(x['elapsed_s'] for x in vdif_reads),'whole_sequence_elapsed_s':elapsed,
            'input_identity':result['input_identity'],'input_vdif':result['input_vdif'],'window_count':len(result['windows']),
            'exposure_s':result['nominal_image_exposure_per_station_s'],'rml':result['rml']},
        'maximum_absolute_reference_array_differences':differences,
        'limits':'Same archived four-station point-noise VDIF. Counts concern full original SHA reads, not all IQ reads. Legacy timing hashes only; new total includes radio/RML. Single sequential WSL run, page cache uncontrolled. Metadata rehashed every boundary. Stat-invisible VDIF mutation can be missed; closed archive required. No real hardware or hours-scale throughput claim.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--clock-model',required=True)
    p.add_argument('--reference',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    q=run(a.manifest,a.clock_model,a.reference,a.output)
    print(json.dumps({'old_hash_bytes':q['legacy_hash_only']['actual_vdif_hash_bytes'],
        'new_hash_bytes':q['new_sequence']['actual_vdif_hash_bytes'],
        'largest_array_difference':max(q['maximum_absolute_reference_array_differences'].values())},indent=2))
