"""Reuse the fixed stage172 sample: identify once, compare every science field."""
import argparse
import json
from pathlib import Path
import resource
import sys
import time

if __package__ in (None,''):
    # The installed study uses the retained 172 reference helper. Product API
    # probes do not need this checkout bootstrap; product origins are checked.
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import numpy as np
from vsora_correlator.closure_pipeline import process_closure_session
from vsora_correlator import input_identity
from vsora_formats.spectral import load_spectral
from workflows.sigmf_pipeline_validation import independent_final


def write_json(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def science_metadata(value,context=None):
    """Only the provenance changes explicitly fixed before this validation."""
    omitted={'input_identity','input_identity_diagnostics','input_sha256',
             'rate_only_profile_sha256','visibility_sha256'}
    if context=='raw_bispectrum':omitted=omitted|{'bytes'}
    if isinstance(value,dict):return {k:science_metadata(v,k) for k,v in value.items() if k not in omitted}
    if isinstance(value,list):return [science_metadata(v) for v in value]
    if isinstance(value,str) and value.startswith('rate_profile_sha256='):return 'rate_profile_sha256=PROVENANCE'
    return value


def compare_saved(current,baseline,*,reuse):
    current=Path(current);baseline=Path(baseline);numeric=metadata=records=0
    files=sorted(current.rglob('*.npz'))
    assert [f.relative_to(current) for f in files]==sorted(f.relative_to(baseline) for f in baseline.rglob('*.npz'))
    for file in files:
        with np.load(file) as a,np.load(baseline/file.relative_to(current)) as b:
            assert a.files==b.files
            for key in a.files:
                if key=='metadata_json' and reuse:
                    assert science_metadata(json.loads(a[key].item()))==science_metadata(json.loads(b[key].item()))
                    metadata+=1
                else:np.testing.assert_array_equal(a[key],b[key]);numeric+=1
    for file in sorted(current.glob('*.json')):
        a=json.loads(file.read_text());b=json.loads((baseline/file.name).read_text())
        if file.name in ('pipeline.json','summary.json'):
            assert a['correlation']['raw_bispectrum']['bytes']==(current/'correlation/raw-bispectrum.npz').stat().st_size
            assert b['correlation']['raw_bispectrum']['bytes']==(baseline/'correlation/raw-bispectrum.npz').stat().st_size
        assert (science_metadata(a)==science_metadata(b)) if reuse else (a==b)
        records+=1
    return {'exact_fields':numeric,'science_metadata':metadata,'JSON_records':records}


def run(inputs,baseline,output):
    inputs=Path(inputs).resolve();baseline=Path(baseline).resolve();output=Path(output)
    if output.exists():raise FileExistsError('choose a new output directory')
    before=int(Path('/proc/self/statm').read_text().split()[1])*resource.getpagesize()
    began=time.monotonic();output.mkdir(parents=True)
    calls=[];digest=input_identity.digest_file
    def count(path):calls.append(Path(path));return digest(path)
    input_identity.digest_file=count
    options=dict(pilot_integrations=64,integration_s=.1,max_rate_hz=100.,correlation_only=True,save_bispectrum=True)
    try:
        result=process_closure_session(inputs/'manifest.json',inputs/'clock.json',output/'sigmf',**options)
    finally:input_identity.digest_file=digest
    raw=[p for p in calls if p.suffix=='.sigmf-data']
    assert len(raw)==len(set(raw))==4
    actual_bytes=sum(p.stat().st_size for p in raw)
    assert result['input_identity']['pipeline_data_full_sha_passes_per_station']==1
    assert result['input_identity']['pipeline_data_hash_file_reads']==4
    assert result['input_identity']['pipeline_data_hash_bytes']==actual_bytes
    assert all(x['sigmf_data_hash_file_reads']==0 for x in result['input_identity']['direct_subruns'])
    process_closure_session(inputs/'legacy.json',inputs/'clock.json',output/'legacy',**options)
    compared={kind:compare_saved(output/kind,baseline/kind,reuse=kind=='sigmf') for kind in ['sigmf','legacy']}
    actual=load_spectral(output/'sigmf/correlation/shard-00000.npz')
    reference=independent_final(output/'sigmf/final-manifest.json',inputs/'clock.json',output/'sigmf/rate-only.json')
    np.testing.assert_allclose(actual['visibilities'],reference,rtol=1e-10,atol=1e-7)
    np.savez(output/'independent.npz',visibilities=reference)
    summary={'state':'complete','same_saved_input_as_stage172':True,'real_baselines':0,'new_image_fits':0,
             'data_full_hash_file_reads':len(raw),'data_full_hash_bytes':actual_bytes,
             'previous_three_pass_bytes':3*actual_bytes,'full_hash_bytes_avoided':2*actual_bytes,
             'whole_IO_or_hardware_throughput_measured':False,'compared':compared,
             'independent_visibility_max_abs_error':float(abs(actual['visibilities']-reference).max()),
             'rtol':1e-10,'atol_ADC2':1e-7,'shared_reference':'saved fitted rates and geometry; same finite sample, not independent observation',
             'wall_s':time.monotonic()-began,'import_current_RSS_bytes':before,
             'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
             'conservative_additional_peak_bytes':max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024-before)}
    write_json(output/'summary.json',summary)
    write_json(output/'environment.json',{'product_modules':{n:m.__file__ for n,m in sys.modules.items()
        if n.startswith('vsora_') and getattr(m,'__file__',None)}})
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True);p.add_argument('--baseline',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(run(a.input,a.baseline,a.output)))
