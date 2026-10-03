"""Installed single-cell noise CLI and optional frozen VDIF comparison."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SCRIPT='''
import hashlib,json,subprocess,sys
from pathlib import Path
import numpy as np
from vsora_correlator import noise_diagnostics,stream_fx,aligned
from vsora_formats import spectral
assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (noise_diagnostics,stream_fx,aligned,spectral))
spec=json.loads(Path(sys.argv[1]).read_text());out=Path(spec['output'])
if spec.get('manifest'):
    aligned.correlate_aligned(spec['manifest'],spec['clock_model'],out/'correlation',1,rate_profile=spec['rate_profile'])
    source=out/'correlation/shard-00000.npz';current=spectral.load_spectral(source)
    old=spectral.load_spectral(spec['reference']);keys=['visibilities','weights','uvw_lambda','pairs','times_s','frequencies_hz','integration_s']
    keys += [k for k in old if k.startswith('diagnostic_')]
    for k in keys:assert np.array_equal(old[k],current[k]),k
    old_report=noise_diagnostics.diagnose_noise_cell(old,0,len(old['frequencies_hz'])//2)
    assert old_report['state']=='unverified' and old_report['reason']=='missing_station_power_flags_or_fft_counts'
    comparison={'frozen_vdif_recorrelated':True,'matching_arrays':keys,'maximum_array_difference':0.,
        'old_archive_unverified_without_pair_counts':True}
else:
    rng=np.random.default_rng(47);s=np.ones((4,4))+np.eye(4)
    z=(rng.normal(size=(32768,4))+1j*rng.normal(size=(32768,4)))/np.sqrt(2)
    x=(z @ np.linalg.cholesky(s).T).T
    quality={'channel_weights':True,'min_sk_blocks':24,'sk_bounds':[.2,5.],'exclude_rf_ranges_hz':[]}
    acc=stream_fx.FXAccumulator(4,2048000,64,1.42e9,quality)
    for first in range(0,x.shape[1],8192):acc.consume(x[:,first:first+8192])
    data=acc.finish();v=data.pop('vis_jy');data.update(visibilities=v,uvw_lambda=np.zeros((*v.shape,3)))
    meta={'visibility_unit':'ADC^2','diagnostic_power_unit':'ADC^2','config':{'stations':[{'id':f'ST{i+1:02d}'} for i in range(4)]}}
    source=out/'gaussian-fft.npz';spectral.save_spectral(source,data,meta);current=spectral.load_spectral(source)
    comparison={'frozen_vdif_recorrelated':False,'iid_gaussian_iq_generated':True,'dummy_geometry_not_image_validation':True}
result=out/'noise.json';command=[str(Path(sys.prefix)/'bin/vsora-noise-diagnose'),'--input',str(source),'--output',str(result),
    '--channel-index',str(len(current['frequencies_hz'])//2)]
cli=subprocess.run(command,cwd=str(out),capture_output=True,text=True);assert cli.returncode==0,cli.stderr
q=json.loads(result.read_text());assert q['state']=='conditional_estimate'
assert q['input_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
assert not q['iid_fft_independence_verified'] and not q['production_rml_noise_model_changed']
assert q['visibility_covariance_ensemble_unbiased_only_if_assumptions_hold'] and q['closure_covariance_first_order_not_unbiased_guarantee']
again=subprocess.run(command,cwd=str(out),capture_output=True,text=True);assert again.returncode!=0
print(json.dumps({'installed_imports':True,'installed_cli_outside_checkout':True,'state':q['state'],
 'nominal_common_fft_blocks':q['nominal_common_fft_blocks'],'time_index':q['time_index'],'channel_index':q['channel_index'],
 'input_sha256':q['input_sha256'],'no_overwrite_checked':True,'iid_fft_independence_verified':False,
 'scope':'Software transport/statistics diagnostic. Nominal FFT count, no actual FIR/ADC covariance accuracy, hardware confidence or image fidelity.',**comparison}))
'''


def run(output,manifest=None,clock_model=None,rate_profile=None,reference=None):
    parameters=(manifest,clock_model,rate_profile,reference)
    if any(p is not None for p in parameters) and not all(p is not None for p in parameters):
        raise ValueError('VDIF comparison needs manifest, clock model, rate profile and reference')
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    spec={'output':str(out)}
    if manifest is not None:
        spec.update({k:str(Path(v).resolve()) for k,v in zip(('manifest','clock_model','rate_profile','reference'),parameters)})
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-noise-cli-') as directory:
        script=Path(directory)/'check.py';script.write_text(SCRIPT);options=Path(directory)/'options.json'
        options.write_text(json.dumps(spec));r=subprocess.run([sys.executable,str(script),str(options)],cwd=directory,env=env,capture_output=True,text=True)
    (out/'execution.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
    q=json.loads(r.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    for name in ('manifest','clock-model','rate-profile','reference'):parser.add_argument('--'+name)
    print(json.dumps(run(**vars(parser.parse_args())),indent=2))
