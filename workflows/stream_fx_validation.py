"""Compare bounded aligned FX against an identified previous spectral output."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import time
import numpy as np
from vsora_correlator.aligned import correlate_aligned
from vsora_formats.spectral import load_spectral


def sha(path):
    with open(path,'rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def run(manifest,clock,rate,reference,output,legacy=False):
    out=Path(output)
    if out.exists():raise FileExistsError('new output required')
    out.mkdir(parents=True)
    c=json.loads(Path(manifest).read_text());c['blocks_per_integration']=round(1.*c['sample_rate_hz']/c['fft_length'])
    root=Path(manifest).resolve().parent
    c['observation_config']=str((root/c['observation_config']).resolve())
    for station in c['stations']:station['vdif']=str((root/station['vdif']).resolve())
    local=out/'local-manifest.json';local.write_text(json.dumps(c,indent=2)+'\n')
    operation=correlate_aligned
    if legacy:
        import subprocess,types
        code=subprocess.check_output(['git','show','c7d6dcd:apps/correlator/src/vsora_correlator/aligned.py'],text=True)
        module=types.ModuleType('vsora_correlator.legacy_stage025')
        module.__package__='vsora_correlator'
        exec(compile(code,'stage025-aligned-reference','exec'),module.__dict__)
        operation=module.correlate_aligned
    start=time.perf_counter();result=operation(local,clock,out/'correlation',1,.002,rate)
    elapsed=time.perf_counter()-start
    actual=load_spectral(out/'correlation/shard-00000.npz');expected=load_spectral(reference)
    differences={}
    for key,value in expected.items():
        if key=='metadata':continue
        if not isinstance(value,np.ndarray):continue
        assert actual[key].shape==value.shape,key
        if np.issubdtype(value.dtype,np.inexact):
            scale=max(float(abs(value).max()),1.)
            relative=float(abs(actual[key]-value).max()/scale)
            assert relative<2e-12,(key,relative)
            differences[key]=relative
        else:assert np.array_equal(actual[key],value),key
    summary={'state':'complete','implementation':'stage025 whole integration' if legacy else 'stage026 bounded chunks','reference_spectral_sha256':sha(reference),'manifest_sha256':sha(manifest),
        'clock_sha256':sha(clock),'rate_profile_sha256':sha(rate),'maximum_normalized_differences':differences,
        'correlation':result,'wall_elapsed_s':elapsed,'process_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'scope':'One existing 8-station 1-second VDIF record, known reference output. Source workflow RSS includes Python/Astropy; one implementation per fresh Python process. No continuous long-observation throughput claim.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--clock-model',required=True)
    p.add_argument('--rate-profile',required=True);p.add_argument('--reference',required=True);p.add_argument('--output',required=True)
    p.add_argument('--legacy-stage025',action='store_true')
    a=p.parse_args();print(json.dumps(run(a.manifest,a.clock_model,a.rate_profile,a.reference,a.output,a.legacy_stage025),indent=2))
