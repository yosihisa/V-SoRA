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


def test_partial_iterator_absolute_indices_time_and_invalid(tmp_path):
    from vsora_formats.vdif import iter_vdif_frames
    p=tmp_path/'seek.vdif';x=(np.arange(4096*12)%71)*.01+1j*(np.arange(4096*12)%31)*.01
    valid=np.ones(len(x),bool);valid[4096*8:4096*9]=False
    write_vdif(p,x.astype(complex),'2026-10-02T08:00:00Z',2048000,3,valid=valid)
    whole=list(iter_vdif_frames(p,2048000,3));partial=list(iter_vdif_frames(p,2048000,3,start_sample=4096*7+123))
    assert [f['sample_index'] for f in partial]==[4096*i for i in range(7,12)]
    for a,b in zip(whole[7:],partial):
        np.testing.assert_array_equal(a['data'],b['data']);np.testing.assert_array_equal(a['valid'],b['valid'])
        assert abs((a['time']-b['time']).sec)<1e-12
    with pytest.raises(ValueError,match='beyond'):list(iter_vdif_frames(p,2048000,3,start_sample=len(x)))
    with pytest.raises(ValueError,match='integer'):list(iter_vdif_frames(p,2048000,3,start_sample=True))


def test_seek_checks_origin_and_target_continuity(tmp_path):
    from vsora_formats.vdif import iter_vdif_frames
    from baseband import vdif
    p=tmp_path/'seek.vdif';write_vdif(p,np.ones(4096*12,complex),'2026-10-02T08:00:00Z',2048000,3)
    original=p.read_bytes();size=len(original)//12
    # A missing earlier frame shifts the target header time relative to sample0.
    p.write_bytes(original[:size*3]+original[size*4:])
    with pytest.raises(ValueError,match='missing'):list(iter_vdif_frames(p,2048000,3,start_sample=4096*7))
    p.write_bytes(original)
    with p.open('r+b') as stream:
        stream.seek(7*size);header=vdif.VDIFHeader.fromfile(stream);header=header.copy();header['station_id']=4
        stream.seek(7*size);header.tofile(stream)
    with pytest.raises(ValueError,match='station ID'):list(iter_vdif_frames(p,2048000,3,start_sample=4096*7))
    p.write_bytes(original[:-1])
    with pytest.raises(EOFError):list(iter_vdif_frames(p,2048000,3,start_sample=4096*7))


def test_seek_scope_does_not_claim_unread_prefix_is_valid(tmp_path):
    from baseband import vdif
    from vsora_formats.vdif import iter_vdif_frames
    p=tmp_path/'prefix.vdif';write_vdif(p,np.ones(4096*12,complex),'2026-10-02T08:00:00Z',2048000,3)
    size=p.stat().st_size//12
    with p.open('r+b') as stream:
        stream.seek(3*size);header=vdif.VDIFHeader.fromfile(stream).copy();header['frame_nr']=4
        stream.seek(3*size);header.tofile(stream)
    with pytest.raises(ValueError,match='missing'):list(iter_vdif_frames(p,2048000,3))
    # A corrupt header before the selected range is deliberately not inspected.
    partial=list(iter_vdif_frames(p,2048000,3,start_sample=4096*7))
    assert len(partial)==5 and partial[0]['sample_index']==4096*7
