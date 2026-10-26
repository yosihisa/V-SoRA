"""原本の独立seed/資源予算と、実VDIFの破損を確認する。"""
from copy import deepcopy
import json
import numpy as np
import pytest
from baseband import vdif
from workflows.independent_raw_matrix import PLAN,validate_plan,expected_vdif_bytes,check_resources,validate_station,START,FS
from vsora_formats.vdif import write_vdif


def test_duplicate_seed_cannot_be_called_independent():
    rows=deepcopy(PLAN);rows[1]['seed']=rows[0]['seed']
    with pytest.raises(ValueError,match='duplicate generation seed'):validate_plan(rows)


def test_colliding_or_unsafe_case_ids_are_rejected():
    rows=deepcopy(PLAN);rows[1]['case']=rows[0]['case']
    with pytest.raises(ValueError,match='duplicate case'):validate_plan(rows)
    rows[1]['case']='../elsewhere'
    with pytest.raises(ValueError,match='safe'):validate_plan(rows)


@pytest.mark.parametrize('value',[True,-1,1.2])
def test_invalid_generation_seed_rejected(value):
    rows=deepcopy(PLAN);rows[0]['seed']=value
    with pytest.raises(ValueError,match='seed'):validate_plan(rows)


def test_size_estimate_and_insufficient_resource_refusal():
    assert expected_vdif_bytes(1,1)==8224 and expected_vdif_bytes()==100003840
    check_resources(4*1024**3,8*1024**3)
    for disk,memory,cases in [(4*1024**3-1,8*1024**3,4),(4*1024**3,8*1024**3-1,4),(4*1024**3,8*1024**3,6)]:
        with pytest.raises(ValueError):check_resources(disk,memory,cases)


def raw(path,valid=None):
    x=np.exp(1j*np.arange(8192)*.013);write_vdif(path,x,START,FS,7,scale=1.,valid=valid,voltage_unit='ADC');return path


def test_all_headers_and_boundary_values_of_real_small_vdif(tmp_path):
    p=raw(tmp_path/'station.vdif');record,arrays=validate_station(p,7,2)
    assert record['frames_checked']==2 and record['sample_count']==8192 and set(arrays)=={'first','last'}
    assert all(v.shape==(4096,) and np.isfinite(v).all() for v in arrays.values())


def test_duplicate_frame_number_is_rejected(tmp_path):
    p=raw(tmp_path/'station.vdif')
    with p.open('r+b') as f:
        f.seek(8224);h=vdif.VDIFHeader.fromfile(f).copy();h['frame_nr']=0;f.seek(8224);h.tofile(f)
    with pytest.raises(ValueError,match='sequence'):validate_station(p,7,2)


def test_invalid_frame_and_wrong_physical_length_are_rejected(tmp_path):
    mask=np.ones(8192,bool);mask[4096:]=False;p=raw(tmp_path/'invalid.vdif',mask)
    with pytest.raises(ValueError,match='sequence'):validate_station(p,7,2)
    p=raw(tmp_path/'short.vdif')
    with p.open('r+b') as f:f.truncate(8223)
    with pytest.raises(ValueError,match='physical size'):validate_station(p,7,2)
