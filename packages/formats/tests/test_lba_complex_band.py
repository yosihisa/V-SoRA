"""Synthetic code-reader and finite-operator tests, no observation inference."""
import hashlib
import os

import numpy as np
import pytest

import vsora_formats.lba_band as band
from vsora_formats.lba import LBAFragmentRecording
from vsora_formats.lba_band import LBAComplexBandView
from workflows.lba_complex_band_validation import finite_reference, operator_probes
from workflows.public_lba_fragments import scalar_reference


@pytest.fixture
def source(tmp_path):
    header=tmp_path/'header';payload=tmp_path/'payload'
    header.write_bytes(b'20200102:030405\n');raw=bytes(range(256))*256;payload.write_bytes(raw)
    return header,payload,raw


def reader(source,offset=1,order=('R','L')):
    return LBAFragmentRecording(source[0],source[1],offset,
        nominal_sample_rate_hz=8000000,recorded_pol_order=order)


def view(source,pol=0,**kwargs):
    return LBAComplexBandView(reader(source),recorded_pol_index=pol,sideband='U',**kwargs)


@pytest.mark.parametrize('pol',[0,1])
@pytest.mark.parametrize('start,count',[(64,1),(65,7),(1027,4096),(1028,4097),(65539,16384)])
def test_real_code_finite_sum(source,pol,start,count):
    v=view(source,pol);values=scalar_reference(source[2])[:,pol]
    expected=finite_reference(values[start-64:start+count+64].astype(float),2+start-64)
    actual=v.read_complex_samples(start,count)
    assert actual.dtype==np.complex128 and actual.shape==(count,)
    np.testing.assert_allclose(actual,expected,rtol=1e-11,atol=1e-8)


def test_chunk_seek_tail_and_nominal_coordinates(source):
    r=reader(source,offset=3,order=('L','R'));v=LBAComplexBandView(r,recorded_pol_index=1,sideband='U',chunk_samples=4093)
    chunks=list(v.iter_complex_chunks(start_sample=1027,sample_count=8191))
    assert [len(x['complex_samples']) for x in chunks]==[4093,4093,5]
    np.testing.assert_array_equal(np.concatenate([x['complex_samples'] for x in chunks]),v.read_complex_samples(1027,8191))
    assert chunks[0]['sample_index']==1027 and chunks[0]['nominal_source_sample_index']==1033
    assert chunks[0]['nominal_offset_s']==1027/8000000
    assert chunks[0]['polarization_label']=='R' and chunks[0]['recorded_pol_index']==1
    assert 'data' not in chunks[0] and 'time' not in chunks[0] and not hasattr(v,'iter_frames')
    assert v.nominal_start_utc==r.nominal_start_utc and v.nominal_sample_rate_hz==8000000
    assert v.actual_sample_rate_hz is None and not v.clock_accuracy_measured and v.center_frequency_hz is None
    assert v.station_id is None and v.band_edge_frequency_hz is None
    tail=v.read_complex_samples(v.stop_valid_sample_index-13,13);assert len(tail)==13
    assert r.payload_hash_reads==1


def test_original_offset_sets_mixer_phase(source):
    a=LBAComplexBandView(reader(source,offset=0),recorded_pol_index=0,sideband='U')
    b=LBAComplexBandView(reader(source,offset=1),recorded_pol_index=0,sideband='U')
    np.testing.assert_array_equal(b.read_complex_samples(1028,4096),-a.read_complex_samples(1028,4096))


def test_coefficients_and_tone_response(source):
    v=view(source);h=v.filter_coefficients.copy();probes=operator_probes(h)
    assert probes['tone_actual'].shape==(14,257)
    altered=v.filter_coefficients;altered[:]=0
    np.testing.assert_array_equal(h,v.filter_coefficients)
    meta=v.processing_identity
    assert meta['filter_coefficients_sha256']==hashlib.sha256(h.astype('<f8').tobytes()).hexdigest()
    assert meta['required_support_each_side_samples']==64 and meta['real_to_complex_amplitude_factor']==2
    assert not meta['downsampled'] and not meta['ideal_analytic_or_perfect_image_rejection']
    meta['source_fragment_identity']['payload']['sha256']='changed'
    assert v.processing_identity['source_fragment_identity']['payload']['sha256']!='changed'


@pytest.mark.parametrize('index',[None,True,-1,2,0.,'R'])
def test_bad_pol(source,index):
    with pytest.raises(ValueError):LBAComplexBandView(reader(source),recorded_pol_index=index,sideband='U')


@pytest.mark.parametrize('sideband',[None,False,'L','u',1,{}])
def test_bad_sideband(source,sideband):
    with pytest.raises(ValueError):LBAComplexBandView(reader(source),recorded_pol_index=0,sideband=sideband)


@pytest.mark.parametrize('chunk',[0,True,1.,16385,None])
def test_bad_chunk(source,chunk):
    with pytest.raises(ValueError):view(source,chunk_samples=chunk)


@pytest.mark.parametrize('start,count',[(0,1),(63,1),(64,0),(64,True),(64,1.),(True,1),(64,16385),(131008,1),(131007,2)])
def test_support_and_types(source,start,count):
    with pytest.raises(ValueError):view(source).read_complex_samples(start,count)


@pytest.mark.parametrize('start,count',[(0,None),(True,None),(64,0),(64,False),(64,1.),(131008,None)])
def test_iterator_bad_range(source,start,count):
    with pytest.raises(ValueError):list(view(source).iter_complex_chunks(start_sample=start,sample_count=count))


@pytest.mark.parametrize('name,value',[('original_payload_offset_bytes',2),('nominal_sample_rate_hz',True),
    ('sample_count',10000),('recorded_pol_order',('L','R')),('actual_sample_rate_hz',8000000)])
def test_parent_context_changes(source,name,value):
    r=reader(source);v=LBAComplexBandView(r,recorded_pol_index=0,sideband='U');setattr(r,name,value)
    with pytest.raises(ValueError,match='context changed'):v.read_complex_samples(64,1)


@pytest.mark.parametrize('kind',['header','payload'])
def test_parent_file_change(source,kind):
    v=view(source)
    if kind=='header':source[0].write_bytes(b'20200102:030406\n')
    else:
        before=source[1].stat();source[1].write_bytes(b'\xff'+source[2][1:])
        os.utime(source[1],ns=(before.st_atime_ns,before.st_mtime_ns+1000000000))
    with pytest.raises(ValueError,match='changed'):v.read_complex_samples(64,1)


def test_guard_after_transform_and_last_iterator(source,monkeypatch):
    v=view(source);old=band.np.convolve
    def mutate(*args,**kwargs):
        result=old(*args,**kwargs);source[0].write_bytes(b'20200102:030406\n');return result
    monkeypatch.setattr(band.np,'convolve',mutate)
    with pytest.raises(ValueError,match='changed'):v.read_complex_samples(64,1)


def test_iterator_last_guard(source):
    v=view(source);it=v.iter_complex_chunks(sample_count=1);next(it)
    source[0].write_bytes(b'20200102:030406\n')
    with pytest.raises(ValueError,match='changed'):next(it)


def test_source_required_and_short_support(source):
    with pytest.raises(TypeError):LBAComplexBandView({},recorded_pol_index=0,sideband='U')
    source[1].write_bytes(bytes(64))
    with pytest.raises(ValueError,match='support'):view(source)


def test_constructor_rejects_physical_clock_inference(source):
    r=reader(source);r.actual_sample_rate_hz=8000000
    with pytest.raises(ValueError):LBAComplexBandView(r,recorded_pol_index=0,sideband='U')


@pytest.mark.parametrize('name,value',[('recorded_pol_index',1),('nominal_sample_rate_hz',True),
    ('sideband','L'),('chunk_samples',8192),('actual_sample_rate_hz',8000000)])
def test_view_configuration_is_fixed(source,name,value):
    v=view(source);setattr(v,name,value)
    with pytest.raises(ValueError,match='view context changed'):v.read_complex_samples(64,1)
