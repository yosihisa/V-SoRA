import numpy as np
import pytest
from astropy.time import Time
from vsora_formats.vdif import write_vdif,read_vdif


def test_complex_quantization_time_station_and_invalid(tmp_path):
    rng=np.random.default_rng(8)
    x=.4*(rng.normal(size=8192)+1j*rng.normal(size=8192))
    valid=np.ones(8192,bool);valid[4096:]=False
    p=tmp_path/'test.vdif'
    meta=write_vdif(p,x,'2026-10-02T08:00:00Z',2048000,3,valid=valid)
    y,mask,header=read_vdif(p,2048000,3)
    assert np.max(abs(x[:4096]-y[:4096]))<np.sqrt(2)/71+.000001
    np.testing.assert_array_equal(valid,mask)
    assert abs((Time(header['start_utc'])-Time('2026-10-02T08:00:00Z')).sec)<1e-9
    assert meta['invalid_frame_count']==1 and meta['clipped_fraction']==0
    with pytest.raises(ValueError): read_vdif(p,2048000,4)
    with pytest.raises(FileExistsError): write_vdif(p,x,'2026-10-02T08:00:00Z',2048000,3)


def test_missing_and_truncated_frames_rejected(tmp_path):
    p=tmp_path/'test.vdif'
    write_vdif(p,np.ones(4096*3,complex),'2026-10-02T08:00:00Z',2048000,3)
    original=p.read_bytes();framebytes=len(original)//3
    p.write_bytes(original[:framebytes]+original[2*framebytes:])
    with pytest.raises(ValueError): read_vdif(p,2048000,3)
    p.write_bytes(original[:-1])
    with pytest.raises(EOFError): read_vdif(p,2048000,3)
