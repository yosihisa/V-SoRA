"""Verify installed opt-in FX accumulation outside the checkout."""
import argparse
import json
from pathlib import Path
import numpy as np
import vsora_correlator.stream_fx as fx_module
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    module_path=Path(fx_module.__file__).resolve()
    if 'site-packages' not in module_path.parts:raise RuntimeError('installed package required')
    rng=np.random.default_rng(6304);x=rng.normal(size=(4,16*33))+1j*rng.normal(size=(4,16*33))
    valid=np.ones(x.shape,bool);valid[0,0]=False;valid[2,16*5+1]=False
    off=fx_module.FXAccumulator(4,2048000.,16,1.42e9)
    on=fx_module.FXAccumulator(4,2048000.,16,1.42e9,collect_bispectrum=True)
    for first in range(0,x.shape[1],16*7):
        off.consume(x[:,first:first+16*7],valid[:,first:first+16*7]);on.consume(x[:,first:first+16*7],valid[:,first:first+16*7])
    baseline=off.finish();combined=on.finish();raw=combined['raw_bispectrum']
    for k,v in baseline.items():
        if isinstance(v,np.ndarray):np.testing.assert_array_equal(v,combined[k])
        elif v!=combined[k]:raise RuntimeError('ordinary output differs')
    order=np.argsort(1.42e9+np.fft.fftfreq(16,1/2048000.))
    spectrum=np.fft.fft(x.reshape(4,33,16).transpose(1,2,0),axis=1,norm='ortho')[:,order]
    block_ok=valid.reshape(4,33,16).all(axis=2).T
    for n,t in enumerate(raw['triangles']):
        good=block_ok[:,t].all(axis=1)
        q=distinct_sample_bispectrum(spectrum[good].transpose(1,0,2),[t])
        np.testing.assert_allclose(raw['distinct_sample_bispectrum'][:,n],q['distinct_sample_bispectrum'][:,0],rtol=1e-12,atol=1e-12)
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    q={'state':'complete','installed_imports':True,'outside_checkout':True,
       'ordinary_arrays_bit_identical':True,'batch_u3_matches':True,
       'common_fft_count':raw['common_sample_count'].tolist(),
       'actual_temporal_independence_verified':False,'production_rml_noise_model_changed':False}
    (out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');print(json.dumps(q))


if __name__=='__main__':main()
