"""独立seedの有限VDIF原本だけを生成する。相関・画像化は行わない。"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import sys
import time
import numpy as np
from astropy.time import Time
import astropy.units as u
from baseband import vdif
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from vsora_observation import load_config
from workflows.vdif_synthesis_validation import extended_fixture

PLAN=[{'case':'high_a','seed':131001,'sefd_jy':1000.},{'case':'high_b','seed':131002,'sefd_jy':1000.},
      {'case':'weak_a','seed':131003,'sefd_jy':10000.},{'case':'weak_b','seed':131004,'sefd_jy':10000.}]
FRAMES=1520;FS=2048000;SAMPLES=4096;STATIONS=8;START='2026-10-02T10:00:00Z';BUDGET=512*1024**2


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_plan(plan):
    if not plan:raise ValueError('nonempty raw matrix required')
    ids=[];seeds=[]
    for row in plan:
        if set(row)!={'case','seed','sefd_jy'} or not isinstance(row['case'],str) or not re.fullmatch('[a-z][a-z0-9_]*',row['case']):raise ValueError('safe unique case identifiers required')
        if isinstance(row['seed'],bool) or not isinstance(row['seed'],int) or row['seed']<0:raise ValueError('nonnegative integer generation seed required')
        if isinstance(row['sefd_jy'],bool) or not isinstance(row['sefd_jy'],(int,float)) or not np.isfinite(row['sefd_jy']) or row['sefd_jy']<=0:raise ValueError('finite positive assumed SEFD required')
        ids.append(row['case']);seeds.append(row['seed'])
    if len(set(ids))!=len(ids):raise ValueError('duplicate case identifier')
    if len(set(seeds))!=len(seeds):raise ValueError('duplicate generation seed is not an independent raw case')
    return plan


def expected_vdif_bytes(frames=FRAMES,stations=STATIONS):
    if any(isinstance(v,bool) or not isinstance(v,int) or v<1 for v in [frames,stations]):raise ValueError('positive integer frame/station count required')
    return frames*stations*(SAMPLES*2+32)


def check_resources(free_bytes,available_memory_bytes,cases=4):
    if expected_vdif_bytes()*cases>BUDGET:raise ValueError('raw matrix exceeds fixed 512MiB disk budget')
    if free_bytes<4*1024**3:raise ValueError('at least 4GiB free disk required')
    if available_memory_bytes<8*1024**3:raise ValueError('at least 8GiB MemAvailable required')


def available_memory():return int(next(v.split()[1] for v in Path('/proc/meminfo').read_text().splitlines() if v.startswith('MemAvailable:')))*1024


def validate_station(path,expected_station,frame_count=FRAMES):
    path=Path(path);metadata=json.loads(path.with_suffix('.json').read_text());expected_size=expected_vdif_bytes(frame_count,1)
    if path.stat().st_size!=expected_size:raise ValueError('VDIF physical size does not match fixed frame count')
    if (metadata['sample_count']!=frame_count*SAMPLES or metadata['sample_rate_hz']!=FS or metadata['decoded_voltage_unit']!='ADC'
            or metadata['samples_per_frame']!=SAMPLES or not metadata['complex'] or metadata['bits_per_component']!=8):raise ValueError('VDIF sidecar differs from fixed raw profile')
    scale=metadata['decoded_voltage_scale'];decoded={};records=[]
    with path.open('rb') as f:
        first=vdif.VDIFHeader.fromfile(f,verify=True);seconds=first['seconds'];epoch=first['ref_epoch']
        if abs((first.get_time(frame_rate=500*u.Hz)-Time(START)).to_value(u.s))>1e-7:raise ValueError('VDIF start UTC differs from fixed profile')
        for i in range(frame_count):
            f.seek(i*8224);h=vdif.VDIFHeader.fromfile(f,verify=True)
            if (h['seconds']!=seconds+i//500 or h['frame_nr']!=i%500 or h['ref_epoch']!=epoch or h['station_id']!=expected_station
                    or h['invalid_data'] or h.edv!=0 or not h.complex_data or h.bps!=8 or h.samples_per_frame!=SAMPLES or h.frame_nbytes!=8224):raise ValueError('VDIF header sequence differs from fixed raw profile')
        for name,i in [('first',0),('last',frame_count-1)]:
            f.seek(i*8224);frame=vdif.VDIFFrame.fromfile(f,verify=True);q=np.asarray(frame.data).reshape(-1).astype(np.complex128)*scale
            if not frame.valid or q.shape!=(SAMPLES,) or not np.isfinite(q).all():raise ValueError('invalid boundary decode')
            decoded[name]=q;records.append({'boundary':name,'frame_index':i,'sample_index':i*SAMPLES,'decoded_complex128_sha256':hashlib.sha256(q.tobytes()).hexdigest()})
    return {'station_numeric_id':expected_station,'frames_checked':frame_count,'sample_count':metadata['sample_count'],'vdif_bytes':expected_size,'decoded_voltage_unit':'ADC','decoded_voltage_scale':scale,
            'clipped_fraction':metadata['clipped_fraction'],'boundaries':records},decoded


def origins():return {n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('vsora_') and getattr(m,'__file__',None)}


def worker(case_name,output):
    row=next(v for v in validate_plan(PLAN) if v['case']==case_name);out=Path(output);out.mkdir(parents=True,exist_ok=False)
    check_resources(shutil.disk_usage(out).free,available_memory(),1);began=time.monotonic()
    truth,rates,generating=extended_fixture(out/'input',START,seed=row['seed'],model='casa',sefd_jy=row['sefd_jy'],frame_count=FRAMES)
    observation=out/'input/observation.json';c=json.loads(observation.read_text());c['noise']['enabled']=True;observation.write_text(json.dumps(c,indent=2)+'\n');c=load_config(observation)
    assert c['source']['model']=='unknown' and 'total_flux_jy' not in c['source'] and c['seed']==42 and not any(k in c for k in ['station_rates_hz','gains'])
    manifest=json.loads((out/'input/manifest.json').read_text());clock=json.loads((out/'input/clock.json').read_text());assert manifest['sample_rate_hz']==FS and manifest['fft_length']==8 and len(manifest['stations'])==8 and all(v['actual_sample_rate_hz']==FS and v['input_start_offset_s']==0 for v in clock['stations'])
    positions=np.array([v['enu_m'] for v in c['stations']]);maximum=float(np.linalg.norm(positions[:,None]-positions[None,:],axis=-1).max());assert maximum<=600.000000001
    np.save(out/'truth.npy',truth);(out/'generation.json').write_text(json.dumps(generating,indent=2)+'\n');station_records=[];arrays={}
    for i in range(1,9):
        record,boundaries=validate_station(out/f'input/station-{i}.vdif',i);station_records.append(record)
        arrays.update({f'ST{i:02d}_{key}':v for key,v in boundaries.items()})
    np.savez_compressed(out/'boundary-decodes.npz',**arrays);raw_files={f.name:sha(f) for f in sorted((out/'input').iterdir()) if f.is_file()};assert len(raw_files)==19
    science={'case':row['case'],'seed':row['seed'],'assumed_sefd_jy':row['sefd_jy'],'start_utc':START,'frame_count':FRAMES,'sample_rate_hz':FS,'samples_per_frame':SAMPLES,'recorded_span_s':FRAMES*SAMPLES/FS,'maximum_baseline_m':maximum,
             'generating':generating,'raw_input_file_sha256':raw_files,'truth_npy_sha256':sha(out/'truth.npy'),'boundary_npz_sha256':sha(out/'boundary-decodes.npz'),'station_validation':station_records,
             'observed_model_unknown':True,'observed_config_seed':42,'observed_config_seed_is_generation_seed':False,'observer_noise_enabled_corrected_to_describe_raw':True,'exact_clock_and_decoder_scales_supplied':True,'gain_truth_not_exported_by_existing_fixture':True,
             'noise_only_intervention':False,'source_or_rate_truth_supplied_to_inference':False,'inference_executed':False,'raw_vdif_bytes':sum(v['vdif_bytes'] for v in station_records)}
    (out/'science.json').write_text(json.dumps(science,indent=2)+'\n');runtime={'elapsed_s':time.monotonic()-began,'peak_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'project_origins':origins()};(out/'runtime-private.json').write_text(json.dumps(runtime,indent=2)+'\n');print(json.dumps({'case':case_name,'complete':True,'elapsed_s':runtime['elapsed_s']}),flush=True)


def run(output,mode):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False);validate_plan(PLAN);check_resources(shutil.disk_usage(out).free,available_memory())
    if mode=='installed' and (Path.cwd().resolve().is_relative_to(ROOT) or (Path.cwd()/'tools/run.py').exists() or 'PYTHONPATH' in os.environ):raise ValueError('installed study requires outside checkout cwd without runner or PYTHONPATH')
    rows=[];measurements=[];env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');env.pop('PYTHONPATH',None)
    for spec in PLAN:
        command=[sys.executable]+([str(ROOT/'tools/run.py'),'workflows.independent_raw_matrix'] if mode=='source' else [str(Path(__file__).resolve())])+['--worker',spec['case'],'--output',str(out/spec['case'])]
        print(json.dumps({'starting_case':spec['case'],'mode':mode}),flush=True);q=subprocess.run(command,cwd=Path.cwd(),env=env,capture_output=True,text=True,timeout=180);(out/(spec['case']+'.log')).write_text(q.stdout+q.stderr)
        if q.returncode:raise RuntimeError('owned fixture worker failed: '+spec['case'])
        science=json.loads((out/spec['case']/'science.json').read_text());private=json.loads((out/spec['case']/'runtime-private.json').read_text());rows.append(science);measurements.append({k:v for k,v in private.items() if k!='project_origins'})
        expected={d.name:d for d in list((ROOT/'apps').glob('*/src/vsora_*'))+list((ROOT/'packages').glob('*/src/vsora_*'))}
        assert all(Path(v).is_relative_to(expected[n.split('.')[0]] if mode=='source' else Path(sys.prefix)) for n,v in private['project_origins'].items())
        repeat=subprocess.run(command,cwd=Path.cwd(),env=env,capture_output=True,text=True,timeout=30);assert repeat.returncode!=0 and 'FileExistsError' in repeat.stderr
        assert science==json.loads((out/spec['case']/'science.json').read_text());assert all(sha(out/spec['case']/'input'/name)==digest for name,digest in science['raw_input_file_sha256'].items());assert sha(out/spec['case']/'truth.npy')==science['truth_npy_sha256'] and sha(out/spec['case']/'boundary-decodes.npz')==science['boundary_npz_sha256'];(out/(spec['case']+'-nonoverwrite.log')).write_text(repeat.stderr)
    assert len({v['truth_npy_sha256'] for v in rows})==1
    assert len({tuple(v['raw_input_file_sha256'][f'station-{i}.vdif'] for i in range(1,9)) for v in rows})==4
    total=sum(f.stat().st_size for f in out.rglob('*') if f.is_file());assert total<BUDGET
    result={'stage':131,'state':'complete','fixed_plan':PLAN,'cases':rows,'case_count':4,'headers_checked':4*8*FRAMES,'boundary_decodes':64,'distinct_generation_seeds':True,'distinct_raw_vdif_hash_vectors':True,
            'dependencies':{n:importlib.metadata.version(n) for n in ['numpy','scipy','astropy','baseband']},'raw_vdif_bytes_total':4*expected_vdif_bytes(),'configured_budget_each_environment_bytes':BUDGET,'same_snapshot_geometry':True,'zero_sky_control_generated':False,
            'limits':'Four fixed single-epoch synthetic raw cases, two seeds per assumed SEFD. Seeds change noise/gain/LO jointly. Fixed 3.04s, midpoint narrowband sky, FFT-periodic bandlimited Gaussian, exact clocks/decoder scales. No inference/correlation/image, null-sky false alarm, independent eight observations, real RTL-SDR/Cas A, measured SEFD or full-night/GPU validation.'}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');(out/'measurements.json').write_text(json.dumps({'mode':mode,'cases':measurements,'actual_output_bytes_before_final_records':total},indent=2)+'\n');assert sum(f.stat().st_size for f in out.rglob('*') if f.is_file())<BUDGET;print(json.dumps({'complete':True,'mode':mode,'raw_cases':4,'headers':result['headers_checked'],'bytes':total}),flush=True);return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--mode',choices=['source','installed'],default='source');p.add_argument('--worker',choices=[v['case'] for v in PLAN]);a=p.parse_args()
    if a.worker:worker(a.worker,Path(a.output).resolve())
    else:run(a.output,a.mode)
