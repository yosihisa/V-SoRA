"""Installed VDIF raw bispectrum CLI outside checkout, compared to frozen source."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,tempfile

SCRIPT='''
import json,subprocess,sys
from pathlib import Path
import numpy as np
import vsora_correlator.aligned as aligned
from vsora_formats import spectral,bispectrum
from vsora_correlator.bispectrum_power import normalize_common_power_bispectrum
assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (aligned,spectral,bispectrum))
spec=json.loads(Path(sys.argv[1]).read_text());out=Path(spec['output'])
import tempfile
assert Path.cwd().is_relative_to(Path(tempfile.gettempdir())) and not Path('tools/run.py').exists()
command=[str(Path(sys.prefix)/'bin/vsora-correlate'),'correlate-aligned','--manifest',spec['manifest'],
 '--clock-model',spec['clock_model'],'--output',str(out/'correlation'),'--integrations','2',
 '--rate-profile',spec['rate_profile'],'--save-bispectrum']
r=subprocess.run(command,cwd=Path.cwd(),capture_output=True,text=True);assert r.returncode==0,r.stderr
original=spectral.load_spectral(spec['reference']);current=spectral.load_spectral(out/'correlation/shard-00000.npz')
keys=[k for k,v in original.items() if isinstance(v,np.ndarray)]
for k in keys:np.testing.assert_array_equal(current[k],original[k])
assert current['metadata']==original['metadata']
raw=bispectrum.load_bispectrum(out/'correlation/raw-bispectrum.npz',out/'correlation/shard-00000.npz')
assert raw['source_visibility_verified'] and not raw['metadata']['input_sample_independence_verified']
reference_raw=bispectrum.load_bispectrum(spec['raw_reference'],spec['reference'])
assert raw['schema_version']==2 and reference_raw['schema_version']==2
for key in bispectrum.arrays_for_version(2)|{'distinct_sample_bispectrum'}:
    np.testing.assert_array_equal(raw[key],reference_raw[key])
assert raw['metadata']==reference_raw['metadata']
def normalized(data,ti):
    counts=data['common_fft_count'][ti]
    ordinary=np.divide(np.prod(data['edge_sums'][ti],axis=-1),counts[None,:].astype(float)**3,
        out=np.zeros_like(data['triple_edge_sum'][ti]),where=counts[None,:]>0)
    return normalize_common_power_bispectrum({'triangles':data['triangles'],'common_sample_count':counts,
        'common_station_power_sums':data['common_station_power_sums'][ti],
        'distinct_sample_bispectrum':data['distinct_sample_bispectrum'][ti],
        'ordinary_common_sample_product':ordinary,'channel_triangle_usable':data['channel_triangle_usable'][ti]})
for ti in range(len(raw['times_s'])):
    a=normalized(raw,ti);b=normalized(reference_raw,ti)
    assert set(a)==set(b)
    for key,value in a.items():
        if isinstance(value,np.ndarray):np.testing.assert_array_equal(value,b[key])
        else:assert value==b[key]
modules={name:m for name,m in sys.modules.items() if name.startswith('vsora_') and getattr(m,'__file__',None)}
assert modules and all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in modules.values())

again=subprocess.run(command,cwd=Path.cwd(),capture_output=True,text=True);assert again.returncode!=0
print(json.dumps({'state':'complete','installed_imports':True,'outside_checkout':True,'scientific_cli_cwd_in_temporary_workspace':True,'pythonpath_removed':True,
 'installed_cli_save_bispectrum':True,'raw_schema_version':2,'all_common_power_and_raw_arrays_identical':True,'all_normalized_fields_identical':True,'all_project_modules_under_runtime_prefix':True,'project_module_count':len(modules),'project_module_names':sorted(modules),'frozen_vdif_recorrelated':True,'ordinary_numeric_arrays_compared':len(keys),
 'ordinary_arrays_bit_identical':True,'ordinary_metadata_identical':True,'source_visibility_verified':True,
 'common_fft_count':raw['common_fft_count'].tolist(),'no_overwrite_checked':True,
 'actual_temporal_independence_verified':False,'production_rml_noise_model_changed':False}))
'''


def run(output,manifest,clock_model,rate_profile,reference,raw_reference):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    spec={'output':str(out),**{k:str(Path(v).resolve()) for k,v in zip(('manifest','clock_model','rate_profile','reference','raw_reference'),(manifest,clock_model,rate_profile,reference,raw_reference))}}
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-vdif-u3-cli-') as directory:
        folder=Path(directory);script=folder/'check.py';script.write_text(SCRIPT);options=folder/'options.json';options.write_text(json.dumps(spec))
        r=subprocess.run([sys.executable,str(script),str(options)],cwd=folder,env=env,capture_output=True,text=True)
    (out/'execution.log').write_text(r.stdout+r.stderr)
    if r.returncode:raise RuntimeError('installed VDIF raw bispectrum CLI verification failed')
    q=json.loads(r.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('output','manifest','clock-model','rate-profile','reference','raw-reference'):p.add_argument('--'+name,required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
