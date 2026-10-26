"""既存051の受動時間power診断を、重複しない保存pilot4件へ接続する。"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from vsora_formats.spectral import load_spectral
from vsora_correlator.time_scatter import diagnose_time_file, diagnose_time_scatter

CASES=('high_a','high_b','weak_a','weak_b')
CHANNELS=(3,4,5)


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def write_json(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def identity(data):
    return {k:{'dtype':v.dtype.str,'shape':list(v.shape),'sha256':hashlib.sha256(v.tobytes(order='C')).hexdigest()}
            for k,v in data.items() if k!='metadata'}


def enroll(reference,record):
    """全12pilot数値を公開記録と照合し、各原本のt0.3だけを解析する。"""
    inputs={};canonical={};expected=json.loads(Path(record).read_text())
    assert expected==json.loads((reference/'summary.json').read_text()) and expected['stage']==132
    for raw in CASES:
        previous=None
        for suffix in ('0.3','1','3'):
            case=f'{raw}_t{suffix}';row=next(v for v in expected['cases'] if v['case']==case)
            path=reference/case/'pipeline/pilot/shard-00000.npz';data=load_spectral(path)
            arrays=identity(data);assert arrays==row['science']['pilot']['arrays']
            assert data['visibilities'].shape[:2]==(750,8)
            if previous is not None:assert arrays==previous
            previous=arrays;inputs[f'{case}/pipeline/pilot/shard-00000.npz']=sha(path)
        case=f'{raw}_t0.3';pilot=reference/case/'pipeline/pilot/shard-00000.npz';profile=reference/case/'pipeline/rate-only.json'
        q=json.loads(profile.read_text());assert q['input_sha256']==sha(pilot)
        expected_rate=next(v for v in expected['cases'] if v['case']==case)['science']['pipeline']['rate_estimate']
        assert {k:v for k,v in q.items() if k!='input_sha256'}==expected_rate
        inputs[f'{case}/pipeline/rate-only.json']=sha(profile);canonical[raw]=(pilot,profile)
    return inputs,canonical


def run(reference,record132,output,*,installed=False,expected=None):
    reference=Path(reference).resolve();record132=Path(record132).resolve();out=Path(output).resolve()
    if out.exists():raise FileExistsError('choose new pilot diagnostic study')
    inputs,canonical=enroll(reference,record132);out.mkdir(parents=True);rows=[];timing=[]
    for raw,(pilot,profile) in canonical.items():
        for channel in CHANNELS:
            root=out/raw/f'channel-{channel}';root.mkdir(parents=True)
            for mode in ('unrotated','estimated_rate_rotation'):
                path=root/(mode+'.json');supplied=profile if mode=='estimated_rate_rotation' else None
                command=[sys.executable,'-m','vsora_correlator.time_scatter','--input',str(pilot),'--output',str(path),'--channel-index',str(channel)]
                if supplied is not None:command+=['--rate-profile',str(supplied)]
                started=time.monotonic()
                if installed:
                    q=subprocess.run(command,capture_output=True,text=True,timeout=180);(root/(mode+'-cli.log')).write_text(q.stdout+q.stderr)
                    if q.returncode:raise RuntimeError(q.stderr[-2000:])
                    result=json.loads(path.read_text())
                else:result=diagnose_time_file(pilot,path,channel,supplied)
                timing.append({'raw_case':raw,'channel':channel,'mode':mode,'elapsed_s':time.monotonic()-started})
                assert result['input_sha256']==sha(pilot) and result['rate_profile_sha256']==(None if supplied is None else sha(profile))
                assert not result['hardware_coherence_measured'] and not result['rate_profile_fit_dependence_calibrated']
                assert not result['production_rml_noise_model_changed'] and not result['generating_truth_used']
                before=sha(path)
                if installed:
                    again=subprocess.run(command,capture_output=True,text=True,timeout=30);assert again.returncode!=0 and 'FileExistsError' in again.stderr
                else:
                    try:diagnose_time_file(pilot,path,channel,supplied)
                    except FileExistsError:pass
                    else:raise AssertionError('existing time result overwritten')
                assert sha(path)==before
                row={'raw_case':raw,'channel_index':channel,'mode':mode,'diagnostic_json_sha256':before,'diagnostic':result}
                if expected is not None and expected['series'][len(rows)]!=row:raise ValueError('source/native pilot science differs')
                rows.append(row);write_json(out/'progress.json',{'state':'running','series_completed':len(rows)})
        print(json.dumps({'raw_case':raw,'series_completed':len(rows)}),flush=True)
        if sum(p.stat().st_size for p in out.rglob('*') if p.is_file())>32*1024**2:raise ValueError('32 MiB output limit exceeded')
    probe=diagnose_time_scatter(load_spectral(reference/'high_a_t0.3/pipeline/correlation/shard-00000.npz'),4)
    assert probe['state']=='unverified' and probe['reason']=='time_cell_count_outside_32_to_8192'
    assert all(sha(reference/n)==h for n,h in inputs.items())
    origins={n:m.__file__ for n,m in sys.modules.items() if n.startswith('vsora_') and getattr(m,'__file__',None)}
    write_json(out/'runtime-private.json',{'project_origins':origins});write_json(out/'measurements.json',{'series':timing})
    result={'stage':136,'state':'complete','series':rows,'canonical_raw_cases':list(CASES),'channels':list(CHANNELS),
            'input_files_sha256':inputs,'record132_sha256':sha(record132),'same_raw_three_pilot_numeric_arrays_equal':True,
            'final_correlation_probe':probe,'truth_numerical_values_used':False,'production_rml_changed':False,
            'limits':'Same 3s pilot used to estimate rate and measure conditional power. Unbounded power ratio, not amplitude coherence, unbiased ratio, independent profile test or hardware stability. No FFT/time independence calibration, filter model completion or image improvement.'}
    if expected is not None and result!=expected:raise ValueError('all source/native science differs')
    write_json(out/'summary.json',result);write_json(out/'progress.json',{'state':'complete','series_completed':24});return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference',required=True);p.add_argument('--record132',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.reference,a.record132,a.output)
