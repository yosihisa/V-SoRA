"""固定原本の4ms相関で時計型検査と入力identityを確認する。画像は作らない。"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
from vsora_correlator.aligned import correlate_aligned
from vsora_correlator.input_identity import InputIdentity
from vsora_formats.spectral import load_spectral


CASES=('high_a','high_b','weak_a','weak_b')


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def write_json(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def science(path):
    data=load_spectral(path)
    return {'arrays':{k:{'dtype':v.dtype.str,'shape':list(v.shape),'sha256':hashlib.sha256(v.tobytes(order='C')).hexdigest()}
        for k,v in data.items() if isinstance(v,np.ndarray)},'metadata':data['metadata']}


def malformed(clock,name):
    q=deepcopy(clock)
    if name=='schema_boolean':q['schema_version']=True
    elif name=='band_boolean':q['max_abs_baseband_hz']=True
    elif name=='offset_boolean':q['stations'][0]['input_start_offset_s']=False
    else:raise ValueError('unknown malformed clock condition')
    return q


def run(raw_reference,record131,old_reference,output,*,installed=False,expected=None):
    raw=Path(raw_reference).resolve();record=Path(record131).resolve();old=Path(old_reference).resolve();out=Path(output).resolve()
    if out.exists():raise FileExistsError('choose a new clock contract output')
    published=json.loads(record.read_text());before=json.loads(old.read_text());assert len(before['cases'])==4
    assert all(sha(raw/row['case']/'input'/name)==value for row in published['cases'] for name,value in row['raw_input_file_sha256'].items())
    out.mkdir(parents=True);rows=[];measure=[]
    for name in CASES:
        base=raw/name/'input';manifest=base/'manifest.json';clock=base/'clock.json';folder=out/name
        identity=InputIdentity(manifest,clock);original=identity.public_identity
        start=time.monotonic();summary=correlate_aligned(manifest,clock,folder,1)
        elapsed=time.monotonic()-start;value=science(folder/'shard-00000.npz');data=load_spectral(folder/'shard-00000.npz')
        assert summary['state']=='complete' and summary['recorded_span_s']==.004 and value['metadata']['visibility_unit']=='ADC^2'
        if name=='high_a':assert value['arrays']==before['cases'][0]['numeric_arrays']
        files={str(p.relative_to(folder)):sha(p) for p in folder.rglob('*') if p.is_file()}
        try:correlate_aligned(manifest,clock,folder,1)
        except FileExistsError:pass
        else:raise AssertionError('existing valid correlation overwritten')
        assert files=={str(p.relative_to(folder)):sha(p) for p in folder.rglob('*') if p.is_file()}
        if installed:
            target=out/(name+'-cli');command=[sys.executable,'-m','vsora_correlator','correlate-aligned','--manifest',str(manifest),'--clock-model',str(clock),'--output',str(target),'--integrations','1']
            result=subprocess.run(command,capture_output=True,text=True,timeout=120);(out/(name+'-cli.log')).write_text(result.stdout+result.stderr);assert result.returncode==0,result.stderr[-1000:]
            assert json.loads((target/'summary.json').read_text())==summary and science(target/'shard-00000.npz')==value
            other=load_spectral(target/'shard-00000.npz')
            for key,array in data.items():
                if isinstance(array,np.ndarray):np.testing.assert_array_equal(other[key],array)
            repeated=subprocess.run(command,capture_output=True,text=True,timeout=30);assert repeated.returncode!=0 and 'FileExistsError' in repeated.stderr
        identity.assert_current(manifest,clock);assert identity.public_identity==original
        row={'case':name,'input_identity':original,'identity_diagnostics':identity.diagnostics,'summary':summary,'spectral':value}
        if expected is not None:assert row==expected['valid_cases'][len(rows)]
        rows.append(row);measure.append({'case':name,'api_elapsed_s':elapsed});print(json.dumps({'case':name,'complete':True}),flush=True)
    rejected=[];clock=json.loads((raw/'high_a/input/clock.json').read_text());manifest=raw/'high_a/input/manifest.json'
    for name in ['schema_boolean','band_boolean','offset_boolean']:
        path=out/(name+'.json');write_json(path,malformed(clock,name));target=out/name
        try:correlate_aligned(manifest,path,target,1)
        except ValueError:pass
        else:raise AssertionError('malformed boolean clock accepted')
        assert not target.exists() and not target.with_name(target.name+'.partial').exists()
        if installed:
            command=[sys.executable,'-m','vsora_correlator','correlate-aligned','--manifest',str(manifest),'--clock-model',str(path),'--output',str(target),'--integrations','1']
            result=subprocess.run(command,capture_output=True,text=True,timeout=30);assert result.returncode!=0 and 'ValueError' in result.stderr
            assert not target.exists() and not target.with_name(target.name+'.partial').exists()
        rejected.append({'condition':name,'api_rejected':True,'cli_rejected':installed,'no_output_or_partial':True})
    assert all(sha(raw/row['case']/'input'/name)==value for row in published['cases'] for name,value in row['raw_input_file_sha256'].items())
    origins={n:m.__file__ for n,m in sys.modules.items() if n.startswith('vsora_') and getattr(m,'__file__',None)}
    write_json(out/'runtime-private.json',origins);write_json(out/'measurements.json',measure)
    result={'stage':138,'state':'complete','valid_cases':rows,'malformed_clock_conditions':[x['condition'] for x in rejected],
        'all_malformed_api_rejected':True,'raw_files_sha_preserved':76,'canonical_high_a_matches_before_arrays':True,
        'truth_numerical_values_used':False,'real_clock_accuracy_verified':False,'physical_iq_convention_verified':False,
        'physical_adc_scale_or_sefd_verified':False,'new_image_or_noise_likelihood':False}
    if expected is not None:assert result==expected
    write_json(out/'summary.json',result);write_json(out/'verification.json',{'stage':138,'state':'complete','actual_valid_api_calls':4,'actual_valid_cli_calls':4 if installed else 0,'malformed_api_rejections':3,'malformed_cli_rejections':3 if installed else 0,'valid_cli_nonoverwrite_rejections':4 if installed else 0,'valid_api_nonoverwrite_rejections':4,'all_scientific_json_matches':expected is not None,'project_module_count':len(origins),'physical_clock_verified':False})
    assert sum(p.stat().st_size for p in out.rglob('*') if p.is_file())<32*1024**2
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw-reference',required=True);p.add_argument('--record131',required=True);p.add_argument('--old-reference',required=True);p.add_argument('--output',required=True)
    run(**vars(p.parse_args()))
