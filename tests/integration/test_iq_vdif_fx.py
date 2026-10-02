from pathlib import Path
import numpy as np
from vsora_formats.vdif import write_vdif,read_vdif
from vsora_correlator.fx import fx_correlate


def test_vdif_fx_against_independent_time_correlation(tmp_path):
    rng=np.random.default_rng(6)
    x=.5*(rng.normal(size=65536)+1j*rng.normal(size=65536))
    a=.8*np.exp(.7j);b=.9*np.exp(-.2j)
    decoded=[]
    for i,g in enumerate([a,b]):
        p=tmp_path/f'ST{i}.vdif'
        write_vdif(p,g*x,'2026-10-02T08:00:00Z',2048000,i+1)
        y,valid,_=read_vdif(p,2048000,i+1);assert valid.all();decoded.append(y)
    correlated=fx_correlate(np.array(decoded),2048000)['vis_jy'][:,0].mean()
    expected=a*b.conjugate()*np.mean(abs(x)**2)
    assert abs(correlated/expected-1)<.001
