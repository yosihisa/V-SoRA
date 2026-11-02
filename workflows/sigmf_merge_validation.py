"""Merge saved stage174 windows without new voltage processing or image fits."""
import argparse
import json
from pathlib import Path
import resource
import sys
import time
import numpy as np
from vsora_formats.spectral import load_spectral
from vsora_imaging.synthesis import merge_spectral


def write_json(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def run(inputs,baseline,output):
    inputs=Path(inputs).resolve();baseline=Path(baseline).resolve();output=Path(output)
    if output.exists():raise FileExistsError('choose a new output directory')
    before=int(Path('/proc/self/statm').read_text().split()[1])*resource.getpagesize()
    began=time.monotonic();output.mkdir(parents=True);counts={}
    for kind in ['sigmf','legacy']:
        paths=[inputs/kind/f'window-{i:04d}/correlation/shard-00000.npz' for i in [1,0]]
        dest=output/kind;dest.mkdir()
        result=merge_spectral(paths,dest/'merged.npz');write_json(dest/'summary.json',result)
        original=[load_spectral(p) for p in paths];merged=load_spectral(dest/'merged.npz')
        times=np.concatenate([d['times_s'] for d in original]);order=np.argsort(times)
        expected={k:original[0][k] if k in ('pairs','frequencies_hz')
                  else np.concatenate([d[k] for d in original],axis=0)[order]
                  for k in original[0] if k!='metadata' and (kind=='sigmf' or k!='valid_fft_count')}
        assert set(merged)-{'metadata'}==set(expected)
        for key,array in expected.items():np.testing.assert_array_equal(merged[key],array)
        counts[kind]=len(expected)
        if kind=='sigmf':
            assert merged['metadata']['time_origin_utc']=='2026-10-02T08:00:00.000000000Z'
            assert not result['original_files_rehashed']
            assert all(p['input_identity']==d['metadata']['input_identity']
                       for p,d in zip(merged['metadata']['source_inputs'],original))
            assert merged['metadata']['sigmf_original_identity']['input_sigmf']==original[0]['metadata']['input_identity']['input_sigmf']
        else:
            with np.load(dest/'merged.npz') as a,np.load(baseline/'merged.npz') as b:
                assert a.files==b.files
                for key in a.files:np.testing.assert_array_equal(a[key],b[key])
            assert result==json.loads((baseline/'summary.json').read_text())
    assert 'vsora_imaging.rml' not in sys.modules and 'vsora_imaging.closure' not in sys.modules
    summary={'state':'complete','fixed_stage174_shards_reused':True,'reverse_input_order':True,
        'all_numerical_fields_exact':counts,'legacy174_NPZ_metadata_and_return_exact':True,
        'new_voltage_processing_or_conversion':False,'original_files_rehashed':False,
        'recorded_identity_agreement_only':True,'new_image_fits':0,'real_baselines':0,'new_MC_trials':0,
        'nanosecond_fraction_proof':'separate arithmetic-only synthetic metadata unit; no raw epoch altered',
        'wall_s':time.monotonic()-began,'import_current_RSS_bytes':before,
        'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        'conservative_additional_peak_bytes':max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024-before)}
    write_json(output/'summary.json',summary)
    write_json(output/'environment.json',{'product_modules':{n:m.__file__ for n,m in sys.modules.items()
        if n.startswith('vsora_') and getattr(m,'__file__',None)}})
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True)
    p.add_argument('--baseline',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(run(a.input,a.baseline,a.output)))
