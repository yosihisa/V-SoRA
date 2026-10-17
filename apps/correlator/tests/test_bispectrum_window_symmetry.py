"""Archive-to-window-test transport, not a new physical null calibration."""
import copy
import hashlib
import json
import os
import numpy as np
import pytest
from vsora_correlator import bispectrum_window_symmetry as module
from vsora_correlator.bispectrum_window_symmetry import window_symmetry_from_bispectrum, inspect_bispectrum_window_file
from vsora_correlator.bispectrum_inspect import inspect_bispectrum_cell
from vsora_formats.bispectrum import save_bispectrum, load_bispectrum
from vsora_imaging.window_symmetry import exact_window_sign_flip_test
from vsora_simulator.bispectrum_archive_validation import _example


@pytest.fixture
def example(tmp_path):
    arrays,meta,source,_=_example(tmp_path)
    raw=tmp_path/'raw.npz'
    save_bispectrum(raw,arrays,meta,schema_version=2)
    return raw,source,load_bispectrum(raw,source)


def test_all_features_and_core_result(example):
    _,_,data=example
    actual=window_symmetry_from_bispectrum(data,1)
    expected=np.array([[r['observed_power_normalized_u3_imag']
                       for r in inspect_bispectrum_cell(data,t,1)['triangles']] for t in range(2)])
    assert actual['imaginary_normalized_u3']==expected.tolist()
    assert actual['conditional_test']==exact_window_sign_flip_test(expected)
    assert not actual['source_visibility_verified']
    assert actual['common_fft_count']==data['common_fft_count'].tolist()
    assert actual['all_saved_windows_and_triangles_used']
    for key in ('joint_window_sign_invariance_verified','window_independence_verified',
                'upstream_selection_invariance_verified','source_detection_claimed',
                'source_extent_claimed','image_confidence_claimed','unknown_lo_estimated',
                'production_rml_noise_model_changed'):
        assert actual[key] is False


@pytest.mark.parametrize('windows',[1,2,3,4,8,12])
def test_entire_axis_and_resolution(example,windows):
    _,_,original=example;data=copy.deepcopy(original)
    for key in ('edge_sums','paired_edge_sums','triple_edge_sum','common_station_power_sums',
                'common_fft_count','nominal_fft_count','channel_triangle_usable'):
        data[key]=np.repeat(data[key][:1],windows,axis=0)
    data['times_s']=np.arange(windows,dtype=float)*.01
    q=window_symmetry_from_bispectrum(data,1)
    assert q['conditional_test']['windows']==windows
    assert q['nominal_five_percent_resolution_available']==(windows>=6)
    # Copied values are deliberately a transport fixture, not independent draws.
    assert q['window_independence_verified'] is False


@pytest.mark.parametrize('channel',[-1,4,True,False,None,1.,float('nan'),'1',np.bool_(True)])
def test_invalid_channel(example,channel):
    with pytest.raises(ValueError):window_symmetry_from_bispectrum(example[2],channel)


@pytest.mark.parametrize('version',[1,None,'2',2.,True,False])
def test_invalid_version(example,version):
    data=copy.deepcopy(example[2]);data['schema_version']=version
    with pytest.raises(ValueError):window_symmetry_from_bispectrum(data,1)


@pytest.mark.parametrize('windows',[0,13])
def test_no_implicit_time_subset(example,windows):
    data=copy.deepcopy(example[2]);data['times_s']=np.arange(windows,dtype=float)
    with pytest.raises(ValueError,match='all saved windows'):window_symmetry_from_bispectrum(data,1)


@pytest.mark.parametrize('mode',['two','zero_count','zero_station'])
def test_unavailable_not_zero_or_dropped(tmp_path,mode):
    data,meta,source,_=_example(tmp_path,mode)
    raw=tmp_path/'raw.npz';save_bispectrum(raw,data,meta,schema_version=2)
    with pytest.raises(ValueError):
        window_symmetry_from_bispectrum(load_bispectrum(raw,source),1)


def test_masked_cell_rejected(example):
    with pytest.raises(ValueError,match='no automatic selection'):
        window_symmetry_from_bispectrum(example[2],0)


def test_single_bad_window_not_dropped(example):
    data=copy.deepcopy(example[2]);data['channel_triangle_usable'][1,1,0]=False
    with pytest.raises(ValueError,match='no automatic selection'):
        window_symmetry_from_bispectrum(data,1)


def test_source_and_all_result_fields(example,tmp_path):
    raw,source,data=example;out=tmp_path/'result/result.json'
    result=inspect_bispectrum_window_file(raw,source,out,1)
    expected=window_symmetry_from_bispectrum(data,1)
    expected.update(source_visibility_verified=True,raw_bispectrum_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
                    source_visibility_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    assert result==expected==json.loads(out.read_text())


def test_no_overwrite(example,tmp_path):
    raw,source,_=example;out=tmp_path/'result.json';out.write_bytes(b'keep')
    with pytest.raises(FileExistsError):inspect_bispectrum_window_file(raw,source,out,1)
    assert out.read_bytes()==b'keep'


def test_output_suffix(example,tmp_path):
    with pytest.raises(ValueError):inspect_bispectrum_window_file(*example[:2],tmp_path/'bad.txt',1)


def test_wrong_companion(example,tmp_path):
    raw,source,_=example;source.write_bytes(source.read_bytes()+b'changed')
    out=tmp_path/'result.json'
    with pytest.raises(ValueError):inspect_bispectrum_window_file(raw,source,out,1)
    assert not out.exists()


def test_input_changes_during_inspection(example,tmp_path,monkeypatch):
    raw,source,_=example;original=module.window_symmetry_from_bispectrum
    def changed(data,channel):
        q=original(data,channel)
        stamp=raw.stat();os.utime(raw,ns=(stamp.st_atime_ns,stamp.st_mtime_ns+1000000))
        return q
    monkeypatch.setattr(module,'window_symmetry_from_bispectrum',changed)
    out=tmp_path/'result.json'
    with pytest.raises(ValueError,match='input changed'):
        inspect_bispectrum_window_file(raw,source,out,1)
    assert not out.exists()


def test_missing_raw(example,tmp_path):
    with pytest.raises(FileNotFoundError):
        inspect_bispectrum_window_file(tmp_path/'missing.npz',example[1],tmp_path/'result.json',1)


def test_inputs_unchanged(example):
    data=example[2];before={k:v.copy() for k,v in data.items() if isinstance(v,np.ndarray)}
    window_symmetry_from_bispectrum(data,np.int64(1))
    for key,expected in before.items():np.testing.assert_array_equal(data[key],expected)


@pytest.mark.parametrize('bad',[None,[],{},'raw'])
def test_invalid_data(bad):
    with pytest.raises(ValueError):window_symmetry_from_bispectrum(bad,1)
