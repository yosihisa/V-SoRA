"""Stored distinct synthetic voltages through correlation-only sequences.

Keep originals, derived voltages and all numerical results in ignored outputs/.
This validates software connection, not real baselines or image reconstruction.
"""
import argparse
import json
from pathlib import Path
import resource
import sys
import time

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import numpy as np
from vsora_correlator.sequence import process_sequence
from vsora_correlator import input_identity
from vsora_formats.spectral import load_spectral
from workflows.sigmf_pipeline_validation import independent_final, prepare


def write_json(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def compare_legacy(current,baseline):
    """All NPZ fields exact; only root shared-identity accounting may differ."""
    count=records=0
    files=sorted(current.rglob('*.npz'))
    assert [f.relative_to(current) for f in files]==sorted(f.relative_to(baseline) for f in baseline.rglob('*.npz'))
    for f in files:
        with np.load(f) as a,np.load(baseline/f.relative_to(current)) as b:
            assert a.files==b.files
            for key in a.files:np.testing.assert_array_equal(a[key],b[key]);count+=1
    for f in current.glob('*.json'):
        a=json.loads(f.read_text());b=json.loads((baseline/f.name).read_text())
        if f.name in ('summary.json','pipeline.json'):
            a.pop('input_identity');b.pop('input_identity')
        assert a==b;records+=1
    return {'exact_NPZ_fields':count,'JSON_records_except_root_identity_accounting':records}


def run(inputs,baseline,output):
    inputs=Path(inputs).resolve();baseline=Path(baseline).resolve();output=Path(output)
    if output.exists():raise FileExistsError('choose a new output directory')
    before=int(Path('/proc/self/statm').read_text().split()[1])*resource.getpagesize()
    began=time.monotonic();output.mkdir(parents=True)
    calls=[];digest=input_identity.digest_file
    def count(path):calls.append(Path(path));return digest(path)
    input_identity.digest_file=count
    options=dict(window_count=2,pilot_integrations=64,integration_s=.1,max_rate_hz=100.,
                 correlation_only=True,save_bispectrum=True)
    try:result=process_sequence(inputs/'manifest.json',inputs/'clock.json',output/'sigmf',**options)
    finally:input_identity.digest_file=digest
    raw=[p for p in calls if p.suffix=='.sigmf-data']
    assert len(raw)==len(set(raw))==4
    hashed_bytes=sum(p.stat().st_size for p in raw)
    assert hashed_bytes==9175040
    assert result['input_identity']['sigmf_data_hash_file_reads']==4
    assert result['input_identity']['sigmf_data_hash_bytes']==hashed_bytes
    assert result['completed_steps']==result['total_steps']==6
    assert result['closures'] is result['rml'] is result['synthesis'] is None
    assert not (output/'sigmf/synthesis').exists()
    process_sequence(inputs/'legacy.json',inputs/'clock.json',output/'legacy',**options)
    compared={};errors=[]
    for index,start in enumerate([.002,.130]):
        name=f'window-{index:04d}';window=output/'sigmf'/name
        child=json.loads((window/'summary.json').read_text())
        assert child['input_sigmf']==result['input_sigmf']
        assert child['input_identity']['pipeline_data_hash_file_reads']==4
        assert all(x['sigmf_data_hash_file_reads']==0 for x in child['input_identity']['direct_subruns'])
        compared[name]=compare_legacy(output/'legacy'/name,baseline/name)
        actual=load_spectral(window/'correlation/shard-00000.npz')
        reference=independent_final(window/'final-manifest.json',inputs/'clock.json',window/'rate-only.json',start_offset_s=start)
        if index==0:
            np.testing.assert_array_equal(reference,independent_final(window/'final-manifest.json',inputs/'clock.json',window/'rate-only.json'))
        np.testing.assert_allclose(actual['visibilities'],reference,rtol=1e-10,atol=1e-7)
        assert actual['metadata']['visibility_unit']=='ADC^2' and np.all(actual['valid_fft_count']==6400)
        np.savez(output/f'independent-{index}.npz',visibilities=reference)
        errors.append(float(abs(actual['visibilities']-reference).max()))
    summary={'state':'complete','input_kind':'distinct stored synthetic station code units, supplied nominal clocks',
             'real_baselines':0,'new_image_fits':0,'window_count':2,'data_full_hash_file_reads':len(raw),
             'data_full_hash_bytes':hashed_bytes,'full_hash_passes_per_station':1,
             'whole_IO_or_hardware_throughput_measured':False,'legacy173_comparison':compared,
             'independent_visibility_max_abs_error_per_window':errors,'rtol':1e-10,'atol_ADC2':1e-7,
             'shared_reference':'saved fitted rates and geometry; same finite sample, not independent observation',
             'wall_s':time.monotonic()-began,'import_current_RSS_bytes':before,
             'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
             'conservative_additional_peak_bytes':max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024-before)}
    write_json(output/'summary.json',summary)
    write_json(output/'environment.json',{'product_modules':{n:m.__file__ for n,m in sys.modules.items()
        if n.startswith('vsora_') and getattr(m,'__file__',None)}})
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    p.add_argument('--baseline');p.add_argument('--prepare',action='store_true');a=p.parse_args()
    if a.prepare:prepare(a.input,a.output,frame_count=140)
    else:
        if not a.baseline:p.error('--baseline is required for validation')
        print(json.dumps(run(a.input,a.baseline,a.output)))
