"""Fresh original binding of saved stage174 spectra; no new image fitting."""
import argparse
import json
from pathlib import Path
import sys
import resource,time
import numpy as np

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from workflows.sigmf_merge_validation import run as run_default,write_json
from vsora_imaging.synthesis import merge_spectral
from vsora_correlator import input_identity


def run(inputs,source,baseline,output):
    inputs=Path(inputs).resolve();source=Path(source).resolve();baseline=Path(baseline).resolve();output=Path(output)
    before=int(Path('/proc/self/statm').read_text().split()[1])*resource.getpagesize();began=time.monotonic()
    summary=run_default(inputs,baseline/'legacy',output)
    for kind in ['sigmf','legacy']:
        with np.load(output/kind/'merged.npz') as a,np.load(baseline/kind/'merged.npz') as b:
            assert a.files==b.files
            for key in a.files:np.testing.assert_array_equal(a[key],b[key])
        assert json.loads((output/kind/'summary.json').read_text())==json.loads((baseline/kind/'summary.json').read_text())
    paths=[inputs/'sigmf'/f'window-{i:04d}/correlation/shard-00000.npz' for i in [1,0]]
    manifests=[p.parent.parent/'final-manifest.json' for p in paths]
    dest=output/'verified';dest.mkdir();calls=[];digest=input_identity.digest_file
    def count(path):calls.append(Path(path));return digest(path)
    input_identity.digest_file=count
    try:
        result=merge_spectral(paths,dest/'merged.npz',source_manifest=source/'manifest.json',
            clock_model=source/'clock.json',input_manifests=manifests)
    finally:input_identity.digest_file=digest
    write_json(dest/'summary.json',result)
    raw=[p for p in calls if p.suffix=='.sigmf-data'];assert len(raw)==len(set(raw))==4
    hashed=sum(p.stat().st_size for p in raw);assert hashed==9175040
    diagnostics=result['input_identity_verification'];assert result['original_files_rehashed']
    assert diagnostics['source_diagnostics']['sigmf_data_hash_file_reads']==4
    assert all(d['sigmf_data_hash_file_reads']==0 for d in diagnostics['derived_diagnostics'])
    with np.load(dest/'merged.npz') as a,np.load(output/'sigmf/merged.npz') as b:
        assert a.files==b.files
        for key in a.files:
            if key!='metadata_json':np.testing.assert_array_equal(a[key],b[key])
        m=json.loads(a['metadata_json'].item());n=json.loads(b['metadata_json'].item())
        assert m['sigmf_original_identity']==n['sigmf_original_identity']
        for key in ['original_files_rehashed','sigmf_identity_scope','input_identity_verification']:m.pop(key,None);n.pop(key,None)
        assert m==n
    assert 'vsora_imaging.rml' not in sys.modules and 'vsora_imaging.closure' not in sys.modules
    summary.pop('original_files_rehashed');summary.pop('legacy174_NPZ_metadata_and_return_exact')
    summary.update(default_original_files_rehashed=False,verified_original_files_rehashed=True,
        recorded_identity_agreement_only=False,legacy175_NPZ_metadata_and_return_exact=True,wall_s=time.monotonic()-began,import_current_RSS_bytes=before,
        peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        conservative_additional_peak_bytes=max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024-before),
        fresh_original_hash_file_reads=len(raw),fresh_original_hash_bytes=hashed,
        derived_data_new_hash_reads=0,default175_all_fields_and_JSON_exact=True,
        verified_numerical_fields_exact=True,computation_history_or_producer_authentication_proved=False)
    write_json(output/'summary.json',summary)
    write_json(output/'environment.json',{'product_modules':{n:m.__file__ for n,m in sys.modules.items()
        if n.startswith('vsora_') and getattr(m,'__file__',None)}})
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['input','source','baseline','output']:p.add_argument('--'+n,required=True)
    a=p.parse_args();print(json.dumps(run(a.input,a.source,a.baseline,a.output)))
