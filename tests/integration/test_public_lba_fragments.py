"""Synthetic representation and refusal tests; no network or real recordings."""
import datetime as dt
import numpy as np
import pytest
from workflows.public_lba_fragments import old_header,window_offset,decode,scalar_reference,repack,run


def test_all_u16_patterns_vector_scalar_and_bit_roundtrip():
    raw=np.arange(65536,dtype='<u2').tobytes()
    codes,values=decode(raw)
    np.testing.assert_array_equal(values,scalar_reference(raw))
    assert repack(codes)==raw


@pytest.mark.parametrize('header',[b'',b'20200102:030405',b'20200102:030405\0',b'20201302:030405\n',b'20200102:240405\n'])
def test_header_refuses_unsupported_or_impossible_fields(header):
    with pytest.raises(ValueError):old_header(header)


def test_supplied_epoch_and_original_byte_offset():
    header=b'20200102:030405\n'
    assert old_header(header)==dt.datetime(2020,1,2,3,4,5,tzinfo=dt.timezone.utc)
    assert window_offset(header,'2020-01-02T03:04:07.002Z',40000000)==8008000
    for start in ['2020-01-02T03:04:04Z','2020-01-02T03:04:15Z','2020-01-02T03:04:05']:
        with pytest.raises(ValueError):window_offset(header,start,40000000)


@pytest.mark.parametrize('raw',[b'',b'\x00',bytearray(b'\0\0')])
def test_payload_profile_refuses_partial_words(raw):
    with pytest.raises(ValueError):decode(raw)


def test_repack_refuses_out_of_range_or_wrong_band_count():
    for c in [np.array([[0,4],[0,1]],dtype=np.uint8),np.zeros((4,1),np.uint8),np.zeros((2,2),np.int16)]:
        with pytest.raises(ValueError):repack(c)


def test_nonoverwrite_precedes_input_access(tmp_path):
    output=tmp_path/'existing';output.mkdir()
    with pytest.raises(FileExistsError):run(tmp_path/'missing',output)
