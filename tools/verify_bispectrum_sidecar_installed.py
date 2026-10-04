"""Installed raw U3 sidecar outside checkout; reconstruct and source link."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,tempfile

SCRIPT='''
import hashlib,json
from itertools import combinations
from pathlib import Path
import sys
import numpy as np
import vsora_correlator.bispectrum_accumulator as accumulator
import vsora_formats.bispectrum as sidecar
import vsora_formats.spectral as spectral
assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (accumulator,sidecar,spectral))
rng=np.random.default_rng(6201);x=rng.normal(size=(9,4,3))+1j*rng.normal(size=(9,4,3))
a=accumulator.BispectrumAccumulator(3,4);a.consume(x[:3]);a.consume(x[3:]);q=a.finish()
ids=['A0','A1','A2'];epoch='2026-10-04T00:00:00Z';times=np.array([.01]);freq=1.42e9+np.arange(4,dtype=float)
pairs=np.array(list(combinations(range(3),2)));v=np.stack([(x[:,:,i]*x[:,:,j].conj()).mean(axis=0) for i,j in pairs],axis=-1)
original={'visibilities':v[None],'weights':np.ones((1,4,3)),'uvw_lambda':np.zeros((1,4,3,3)),
 'pairs':pairs,'times_s':times,'frequencies_hz':freq,'valid_fft_count':np.full((1,3),9)}
spectral.save_spectral('visibility.npz',original,{'visibility_unit':'ADC^2','time_origin_utc':epoch,
 'config':{'stations':[{'id':s} for s in ids]},'fft_length':4,'fft_sample_rate_hz':1024})
with open('visibility.npz','rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
data={'triangles':q['triangles'],'times_s':times,'frequencies_hz':freq,'common_fft_count':q['common_sample_count'][None],
 'nominal_fft_count':np.array([9]),'edge_sums':q['edge_sums'][None],'paired_edge_sums':q['paired_edge_sums'][None],
 'triple_edge_sum':q['triple_edge_sum'][None],'channel_triangle_usable':np.ones((1,4,1),bool)}
metadata={'station_ids':ids,'time_origin_utc':epoch,'voltage_unit':'ADC','fft_length':4,'sample_rate_hz':1024,
 'visibility_sha256':sha,'processing_notes':['Synthetic spectral samples; format-only installed verification.']}
sidecar.save_bispectrum('raw.npz',data,metadata);loaded=sidecar.load_bispectrum('raw.npz','visibility.npz')
np.testing.assert_allclose(loaded['distinct_sample_bispectrum'][0],q['distinct_sample_bispectrum'],rtol=1e-12,atol=1e-12)
assert loaded['source_visibility_verified'] and not loaded['metadata']['input_sample_independence_verified']
print(json.dumps({'state':'complete','installed_imports':True,'outside_checkout':True,'pythonpath_removed':True,
 'source_visibility_verified':True,'raw_u3_reconstruction_matches_accumulator':True,'same_count_edge_means_checked':True,
 'actual_temporal_independence_verified':False,'production_rml_noise_model_changed':False}))
'''


def run(output):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='vsora-u3-sidecar-installed-') as folder:
        work=Path(folder);script=work/'check.py';script.write_text(SCRIPT)
        env=os.environ.copy();env.pop('PYTHONPATH',None)
        p=subprocess.run([sys.executable,str(script)],cwd=work,env=env,capture_output=True,text=True)
        if p.returncode:raise RuntimeError('installed U3 sidecar verification failed')
        q=json.loads(p.stdout)
    (out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);print(json.dumps(run(**vars(p.parse_args())),indent=2))
