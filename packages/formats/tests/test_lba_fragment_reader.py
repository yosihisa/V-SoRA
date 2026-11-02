"""Synthetic closed-file API tests; no real data acquisition or clock inference."""
import hashlib
import os
from pathlib import Path
import numpy as np
import pytest

from vsora_formats.lba import LBAFragmentRecording
from workflows.public_lba_fragments import scalar_reference


@pytest.fixture
def pair(tmp_path):
    header=tmp_path/'header.bin';payload=tmp_path/'payload.bin'
    header.write_bytes(b'20200102:030405\n');raw=bytes(range(256))*256;payload.write_bytes(raw)
    return header,payload,raw


def record(pair,**options):
    return LBAFragmentRecording(*pair[:2],8000,nominal_sample_rate_hz=8000000,
                                recorded_pol_order=('R','L'),**options)


def test_real_seek_sequential_tail_bounds_and_nominal_context(pair):
    r=record(pair,chunk_samples=4093);expected=scalar_reference(pair[2])
    for pol in [0,1]:
        chunks=list(r.iter_real_chunks(recorded_pol_index=pol,start_sample=3,sample_count=8191))
        np.testing.assert_array_equal(np.concatenate([f['real_samples'] for f in chunks]),expected[3:8194,pol])
        assert [len(f['real_samples']) for f in chunks]==[4093,4093,5]
        assert chunks[0]['sample_index']==3 and chunks[0]['nominal_source_sample_index']==16003
        assert all('data' not in f and 'time' not in f and f['read_ok'] for f in chunks)
        for start,count in [(0,1),(1,7),(3,4097),(1023,65536),(1,65536),(r.sample_count-13,13)]:
            result=r.read_real_samples(start,count,recorded_pol_index=pol)
            assert result.dtype==np.int16 and not np.iscomplexobj(result)
            np.testing.assert_array_equal(result,expected[start:start+count,pol])
    assert r.maximum_payload_read_bytes==32770
    assert r.nominal_start_utc=='2020-01-02T03:04:05.002000000Z'
    assert r.original_header_datetime=='20200102:030405' and r.voltage_unit=='DiFX_s16_code'
    assert r.actual_sample_rate_hz is None and r.station_id is None and r.band_edge_frequency_hz is None
    assert not r.is_complex and not r.clock_accuracy_measured and not r.producer_checksum_verified
    assert not hasattr(r,'iter_frames') and r.payload_hash_reads==1


def test_half_microsecond_nominal_offset_does_not_round_original_header(pair):
    r=LBAFragmentRecording(*pair[:2],2,nominal_sample_rate_hz=8000000,recorded_pol_order=['L','R'])
    assert r.nominal_start_utc=='2020-01-02T03:04:05.000000500Z'
    assert pair[0].read_bytes()==b'20200102:030405\n' and r.recorded_pol_order==('L','R')


@pytest.mark.parametrize('chunk',[0,-1,True,1.5,65537])
def test_chunk_refuses_unbounded_or_noninteger_values(pair,chunk):
    with pytest.raises(ValueError,match='chunk_samples'):record(pair,chunk_samples=chunk)


@pytest.mark.parametrize('rate',[0,True,4000000,8000000.0,'8000000'])
def test_nominal_profile_is_explicit_and_not_measured_actual_rate(pair,rate):
    with pytest.raises(ValueError,match='nominal'):
        LBAFragmentRecording(*pair[:2],0,nominal_sample_rate_hz=rate,recorded_pol_order=('R','L'))


@pytest.mark.parametrize('offset',[-1,True,1.5,2**53+1])
def test_original_offset_is_bounded_integer(pair,offset):
    with pytest.raises(ValueError,match='offset'):
        LBAFragmentRecording(*pair[:2],offset,nominal_sample_rate_hz=8000000,recorded_pol_order=('R','L'))


@pytest.mark.parametrize('order',[None,('I','Q'),('R','R'),('L',),False])
def test_real_polarizations_cannot_be_relabelled_as_IQ(pair,order):
    with pytest.raises(ValueError,match='polarization'):
        LBAFragmentRecording(*pair[:2],0,nominal_sample_rate_hz=8000000,recorded_pol_order=order)


@pytest.mark.parametrize('start,count,pol',[(True,1,0),(-1,1,0),(0,0,0),(0,65537,0),(0,1,True),(0,1,2),(131071,2,0),(0,1.5,0)])
def test_read_refuses_invalid_ranges_and_polarization(pair,start,count,pol):
    with pytest.raises(ValueError):record(pair).read_real_samples(start,count,recorded_pol_index=pol)


def test_expected_pair_is_freshly_hashed_and_caller_identity_is_a_copy(pair,monkeypatch):
    import vsora_formats.lba as lba
    calls=[];original=lba._sha
    def count(path):calls.append(Path(path));return original(path)
    monkeypatch.setattr(lba,'_sha',count)
    expected={f'expected_{name}_sha256':hashlib.sha256(path.read_bytes()).hexdigest() for name,path in zip(['header','payload'],pair[:2])}
    a=record(pair,**expected);b=record(pair,**expected)
    a.read_real_samples(0,1,recorded_pol_index=0)
    assert calls.count(pair[1])==2 and a.expected_pair_verified and b.expected_pair_verified
    identity=a.fragment_identity;identity['payload']['sha256']='0'*64
    assert a.fragment_identity['payload']['sha256']==expected['expected_payload_sha256']
    for options in [{'expected_header_sha256':expected['expected_header_sha256']},
                    {**expected,'expected_payload_sha256':'A'*64},
                    {**expected,'expected_payload_sha256':'0'*64}]:
        with pytest.raises(ValueError):record(pair,**options)


@pytest.mark.parametrize('part',['header','payload','replacement','symlink'])
def test_normal_file_changes_are_refused(pair,tmp_path,part):
    r=record(pair)
    if part=='header':pair[0].write_bytes(b'20200102:030406\n')
    elif part=='payload':
        before=pair[1].stat()
        pair[1].write_bytes(b'\xff'+pair[2][1:])
        # A same-tick write can retain every raw stat field. Exercise a
        # detectable normal change here; the blind spot has its own test.
        os.utime(pair[1], ns=(before.st_atime_ns,before.st_mtime_ns+1000000000))
    elif part=='replacement':
        replacement=tmp_path/'new';replacement.write_bytes(pair[2]);replacement.replace(pair[1])
    else:
        target=tmp_path/'target';target.write_bytes(pair[2]);pair[1].unlink();pair[1].symlink_to(target)
    with pytest.raises(ValueError,match='changed'):r.read_real_samples(0,2,recorded_pol_index=0)


def test_same_real_file_and_partial_payload_refused(pair):
    with pytest.raises(ValueError,match='different real files'):
        LBAFragmentRecording(pair[0],pair[0],0,nominal_sample_rate_hz=8000000,recorded_pol_order=('R','L'))
    pair[1].write_bytes(b'\0')
    with pytest.raises(ValueError,match='whole u16'):record(pair)


def test_iterator_checks_final_boundary_after_last_yield(pair):
    iterator=record(pair).iter_real_chunks(recorded_pol_index=0,sample_count=2)
    assert len(next(iterator)['real_samples'])==2
    pair[0].write_bytes(b'20200102:030406\n')
    with pytest.raises(ValueError,match='changed'):next(iterator)


def test_artificial_all_stat_preservation_remains_a_blind_spot(pair,monkeypatch):
    import vsora_formats.lba as lba
    r=record(pair);signatures={(v[0],v[1]):v for v in r._signature}
    monkeypatch.setattr(lba,'_signature',lambda info:signatures[(info.st_dev,info.st_ino)])
    pair[1].write_bytes(b'\xff'+pair[2][1:])
    value=r.read_real_samples(0,1,recorded_pol_index=0)
    assert value[0]!=scalar_reference(pair[2])[0,0]
    assert r.fragment_identity['payload']['sha256']!=hashlib.sha256(pair[1].read_bytes()).hexdigest()
