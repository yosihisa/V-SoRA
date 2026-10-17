"""Versioned common-power archive, numerical availability and legacy reads."""
from copy import deepcopy
import hashlib
from itertools import combinations
import json
import numpy as np
import pytest
from vsora_correlator.bispectrum_accumulator import BispectrumAccumulator
from vsora_correlator.bispectrum_power import normalize_common_power_bispectrum
from vsora_correlator.bispectrum_inspect import inspect_bispectrum_cell, inspect_bispectrum_file
from vsora_formats import bispectrum as module
from vsora_formats.spectral import save_spectral


from vsora_simulator.bispectrum_archive_validation import _example as sample

@pytest.mark.parametrize('mode',['complete','missing','two','zero_count','zero_station'])
@pytest.mark.parametrize('unit',['ADC','sqrt(Jy)'])
def test_v2_roundtrip_and_all_inspection_numbers(tmp_path,mode,unit):
    data,meta,source,raw=sample(tmp_path,mode,unit);before=deepcopy(data);path=tmp_path/'raw.npz'
    module.save_bispectrum(path,data,meta,schema_version=2);loaded=module.load_bispectrum(path,source)
    assert loaded['schema_version']==2 and loaded['source_visibility_verified']
    assert loaded['metadata']['common_power_sum_unit']==('ADC^2' if unit=='ADC' else 'Jy')
    assert loaded['metadata']['observed_power_ratio_unbiased_guarantee'] is False
    for name,value in data.items():np.testing.assert_array_equal(value,loaded[name]);np.testing.assert_array_equal(value,before[name])
    reference=normalize_common_power_bispectrum(raw)
    for ti in range(2):
        for fi in range(4):
            q=inspect_bispectrum_cell(loaded,ti,fi);assert q['raw_schema_version']==2 and q['observed_power_ratio_supported']
            for k,row in enumerate(q['triangles']):
                available=bool(reference['u3_available'][fi,k]);ordinary=bool(reference['ordinary_available'][fi,k])
                assert row['observed_power_normalized_u3_available']==available
                assert row['observed_power_normalized_ordinary_product_available']==ordinary
                assert row['observed_power_normalized_u3_quality_usable']==bool(available and data['channel_triangle_usable'][ti,fi,k])
                if available:
                    z=complex(row['observed_power_normalized_u3_real'],row['observed_power_normalized_u3_imag'])
                    np.testing.assert_allclose(z,reference['observed_power_normalized_u3'][fi,k],rtol=3e-14,atol=1e-14)
                else:assert row['observed_power_normalized_u3_real'] is None and row['observed_power_normalized_u3_imag'] is None
                if ordinary:
                    z=complex(row['observed_power_normalized_ordinary_product_real'],row['observed_power_normalized_ordinary_product_imag'])
                    np.testing.assert_allclose(z,reference['observed_power_normalized_ordinary_product'][fi,k],rtol=3e-14,atol=1e-14)
                else:assert row['observed_power_normalized_ordinary_product_real'] is None
            json.dumps(q,allow_nan=False)
    output=tmp_path/'inspect.json';q=inspect_bispectrum_file(path,source,output,1)
    assert json.loads(output.read_text())==q and q['source_visibility_verified']


def test_v1_keeps_missing_power_explicit(tmp_path):
    data,meta,source,_=sample(tmp_path);data.pop('common_station_power_sums');path=tmp_path/'raw.npz'
    module.save_bispectrum(path,data,meta);loaded=module.load_bispectrum(path,source)
    assert loaded['schema_version']==1
    q=inspect_bispectrum_cell(loaded,0,1)
    assert not q['observed_power_ratio_supported'] and q['normalized_bispectrum_unit'] is None
    for row in q['triangles']:
        assert row['observed_power_normalization_state']=='missing_common_power_v1'
        assert row['common_station_power_sums'] is None and row['observed_power_normalized_u3_real'] is None


@pytest.mark.parametrize('kind',['missing','extra','shape','float32','integer','complex','negative','nan','inf','masked','zero_count','zero_power'])
def test_invalid_v2_power(tmp_path,kind):
    d,m,_,_=sample(tmp_path)
    if kind=='missing':d.pop('common_station_power_sums')
    elif kind=='extra':d['unknown']=np.array(0)
    elif kind=='shape':d['common_station_power_sums']=d['common_station_power_sums'][...,:2]
    elif kind in ('float32','integer','complex'):d['common_station_power_sums']=d['common_station_power_sums'].astype({'float32':np.float32,'integer':np.int64,'complex':np.complex128}[kind])
    elif kind=='negative':d['common_station_power_sums'][0,0,0,0]=-1
    elif kind=='nan':d['common_station_power_sums'][0,0,0,0]=np.nan
    elif kind=='inf':d['common_station_power_sums'][0,0,0,0]=np.inf
    elif kind=='masked':d['common_station_power_sums']=np.ma.array(d['common_station_power_sums'])
    elif kind=='zero_count':
        d['common_fft_count'][0,0]=0;d['channel_triangle_usable'][0,:,0]=False
        for name in ('edge_sums','paired_edge_sums','triple_edge_sum'):d[name][0,:,0]=0
    elif kind=='zero_power':d['common_station_power_sums'][0,0,0,0]=0
    with pytest.raises(ValueError):module.validate_bispectrum(d,m,schema_version=2)


@pytest.mark.parametrize('key,value',[('common_power_station_order','k, j, i'),('common_power_sample_set','station-local'),('observed_power_ratio_unbiased_guarantee',True),('common_power_sum_unit','Jy')])
def test_v2_metadata_rejects_false_claims(tmp_path,key,value):
    d,m,_,_=sample(tmp_path);m[key]=value
    with pytest.raises(ValueError):module.validate_bispectrum(d,m,schema_version=2)


@pytest.mark.parametrize('version',[0,3,True,2.,'2',None])
def test_invalid_versions(tmp_path,version):
    d,m,_,_=sample(tmp_path)
    with pytest.raises(ValueError):module.validate_bispectrum(d,m,schema_version=version)


@pytest.mark.parametrize('version',[1,2])
def test_archive_version_and_members_must_match(tmp_path,version):
    d,m,_,_=sample(tmp_path);path=tmp_path/'raw.npz';module.save_bispectrum(path,d,m,schema_version=2)
    with np.load(path,allow_pickle=False) as f:wire={k:f[k] for k in f.files}
    if version==1:wire['schema_version']=np.array(1)
    else:wire.pop('common_station_power_sums')
    bad=tmp_path/'bad.npz';np.savez_compressed(bad,**wire)
    with pytest.raises(ValueError):module.load_bispectrum(bad)


def test_write_size_limit_atomic_cleanup(tmp_path,monkeypatch):
    d,m,_,_=sample(tmp_path);monkeypatch.setattr(module,'MAX_BYTES',32);out=tmp_path/'raw.npz'
    with pytest.raises(ValueError,match='decoded size'):module.save_bispectrum(out,d,m,schema_version=2)
    assert not out.exists() and not list(tmp_path.glob('.bispectrum-*'))


def test_default_writer_does_not_silently_upgrade(tmp_path):
    d,m,_,_=sample(tmp_path)
    with pytest.raises(ValueError):module.save_bispectrum(tmp_path/'raw.npz',d,m)


def test_big_endian_float64_supported(tmp_path):
    d,m,_,_=sample(tmp_path);d['common_station_power_sums']=d['common_station_power_sums'].astype('>f8')
    path=tmp_path/'raw.npz';module.save_bispectrum(path,d,m,schema_version=2)
    np.testing.assert_array_equal(module.load_bispectrum(path)['common_station_power_sums'],d['common_station_power_sums'])


def test_inspection_requires_explicit_version_two(tmp_path):
    d,m,_,_=sample(tmp_path)
    with pytest.raises(ValueError,match='explicit matching'):inspect_bispectrum_cell({**d,'metadata':m},0,1)


@pytest.mark.parametrize('mode,state',[('complete','masked_normalized_value'),('two','insufficient_samples'),('zero_station','zero_common_power')])
def test_mask_and_availability_states(tmp_path,mode,state):
    d,m,_,_=sample(tmp_path,mode);q=inspect_bispectrum_cell({**d,'metadata':m,'schema_version':2},0,0)
    assert q['triangles'][0]['observed_power_normalization_state']==state
    if mode=='two':assert q['triangles'][0]['observed_power_normalized_ordinary_product_available']

@pytest.mark.parametrize('field,value',[('schema_version',True),('mode','other'),('voltage_unit','Jy'),('case_id','c99'),('extra',1)])
def test_native_case_plan_cannot_be_changed(tmp_path,field,value):
    from vsora_simulator.bispectrum_archive_validation import case_plan,experiment
    case=dict(case_plan()[0]);case[field]=value
    with pytest.raises(ValueError,match='unmodified'):experiment(case,tmp_path/'case')
    assert not (tmp_path/'case').exists()


def test_native_all_eight_cases_and_no_overwrite(tmp_path):
    from vsora_simulator.bispectrum_archive_validation import run
    out=tmp_path/'study';q=run(out)
    assert len(q['cases'])==8 and sum(c['inspection_triangle_rows'] for c in q['cases'])==256
    assert q['legacy_missing_power_not_inferred'] and q['archive_versions_checked']==[1,2]
    assert all(c['all_arrays_roundtrip_exact'] and c['all_source_links_verified'] for c in q['cases'])
    assert json.loads((out/'summary.json').read_text())==q and (out/'archive-availability.png').is_file()
    with pytest.raises(FileExistsError):run(out)
