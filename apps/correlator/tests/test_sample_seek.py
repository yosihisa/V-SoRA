import numpy as np
import pytest
from vsora_formats.vdif import write_vdif
from vsora_correlator.aligned import SampleBuffer


@pytest.mark.parametrize('fraction',[0.,.35,.999])
def test_guarded_fir_seek_equals_sequential_values_and_masks(tmp_path,fraction):
    rng=np.random.default_rng(31);fs=2048000;x=.4*(rng.normal(size=4096*30)+1j*rng.normal(size=4096*30))
    valid=np.ones(len(x),bool);valid[4096*23:4096*24]=False
    p=tmp_path/'sample.vdif';write_vdif(p,x,'2026-10-02T08:00:00Z',fs,1,valid=valid)
    sequential=SampleBuffer(p,fs,1,1,fs,seek_input=False);seeking=SampleBuffer(p,fs,1,1,fs)
    try:
        for first in [4096*20+fraction,4096*22+fraction,4096*24+fraction]:
            queries=first+np.arange(8192)
            a,am=sequential.query(queries);b,bm=seeking.query(queries)
            np.testing.assert_array_equal(am,bm);np.testing.assert_allclose(a,b,atol=1e-15,rtol=1e-15)
        assert seeking.frames_read<sequential.frames_read-15
        assert seeking.initial_sample_index==4096*19
        assert seeking.maximum<5*4096
    finally:sequential.close();seeking.close()
