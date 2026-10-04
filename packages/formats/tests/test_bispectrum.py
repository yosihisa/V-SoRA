"""Strict raw U3 sidecar and links to a canonical spectral visibility."""
from copy import deepcopy
import hashlib
from itertools import combinations
import io
import json
from pathlib import Path
import zipfile
import numpy as np
import pytest
from vsora_correlator.bispectrum_accumulator import BispectrumAccumulator
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum
from vsora_formats.bispectrum import save_bispectrum,load_bispectrum,validate_bispectrum
from vsora_formats.spectral import save_spectral


@pytest.fixture
def fixture(tmp_path):
    rng=np.random.default_rng(62);x=rng.normal(size=(7,4,4))+1j*rng.normal(size=(7,4,4))
    acc=BispectrumAccumulator(4,4);acc.consume(x[:2]);acc.consume(x[2:]);q=acc.finish()
    times=np.array([.01,.02]);freq=1.42e9+np.arange(4,dtype=float);ids=['A0','A1','A2','A3'];epoch='2026-10-04T00:00:00Z'
    pairs=np.array(list(combinations(range(4),2)))
    visibility=np.stack([(x[:,:,i]*x[:,:,j].conj()).mean(axis=0) for i,j in pairs],axis=-1)
    original={'visibilities':np.repeat(visibility[None],2,axis=0),'weights':np.ones((2,4,6)),
        'uvw_lambda':np.zeros((2,4,6,3)),'pairs':pairs,'times_s':times,'frequencies_hz':freq,'valid_fft_count':np.full((2,6),7)}
    original_meta={'visibility_unit':'ADC^2','time_origin_utc':epoch,'config':{'stations':[{'id':v} for v in ids]},'fft_length':4,'fft_sample_rate_hz':1024}
    source=tmp_path/'visibility.npz';save_spectral(source,original,original_meta)
    with source.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    metadata={'station_ids':ids,'time_origin_utc':epoch,'voltage_unit':'ADC','fft_length':4,'sample_rate_hz':1024,
        'visibility_sha256':digest,'processing_notes':['Synthetic spectral coefficients for format validation.']}
    data={'triangles':q['triangles'],'times_s':times,'frequencies_hz':freq,
        'common_fft_count':np.repeat(q['common_sample_count'][None],2,axis=0),'nominal_fft_count':np.full(2,7),
        'edge_sums':np.repeat(q['edge_sums'][None],2,axis=0),'paired_edge_sums':np.repeat(q['paired_edge_sums'][None],2,axis=0),
        'triple_edge_sum':np.repeat(q['triple_edge_sum'][None],2,axis=0),'channel_triangle_usable':np.ones((2,4,4),bool)}
    return data,metadata,source,original,original_meta,x


def test_roundtrip_reconstruction_source_link_and_no_overwrite(fixture,tmp_path):
    data,meta,source,_,_,x=fixture;out=tmp_path/'raw.npz';before=deepcopy(data)
    save_bispectrum(out,data,meta);q=load_bispectrum(out,source)
    for k,v in data.items():np.testing.assert_array_equal(q[k],v);np.testing.assert_array_equal(data[k],before[k])
    expected=distinct_sample_bispectrum(x.transpose(1,0,2))['distinct_sample_bispectrum']
    np.testing.assert_allclose(q['distinct_sample_bispectrum'],np.repeat(expected[None],2,axis=0),rtol=1e-12,atol=1e-12)
    assert q['source_visibility_verified'] and not q['metadata']['input_sample_independence_verified']
    assert q['metadata']['bispectrum_unit']=='ADC^6' and not load_bispectrum(out)['source_visibility_verified']
    with pytest.raises(FileExistsError):save_bispectrum(out,data,meta)
    assert not list(tmp_path.glob('.bispectrum-*'))


def test_zero_count_is_unavailable(fixture,tmp_path):
    data,meta,*_=fixture;data['common_fft_count'][:]=0;data['channel_triangle_usable'][:]=False
    for k in ('edge_sums','paired_edge_sums','triple_edge_sum'):data[k][:]=0
    out=tmp_path/'zero.npz';save_bispectrum(out,data,meta);q=load_bispectrum(out)
    assert not q['distinct_sample_available'].any();np.testing.assert_array_equal(q['distinct_sample_bispectrum'],0)


@pytest.mark.parametrize('kind',['keys','masked','shape','real','nan','tri_duplicate','tri_reverse','tri_range','time_duplicate','freq_reverse','freq_zero','count_negative','count_float','count_bool','count_exceeds_nominal','mask_type','mask_insufficient','zero_nonzero_sum','j_negative','j_imaginary','overflow'])
def test_invalid_arrays(fixture,kind):
    d,m,*_=fixture
    if kind=='keys':d['unknown']=0
    elif kind=='masked':d['edge_sums']=np.ma.array(d['edge_sums'])
    elif kind=='shape':d['edge_sums']=d['edge_sums'][...,:2]
    elif kind=='real':d['edge_sums']=d['edge_sums'].real
    elif kind=='nan':d['edge_sums'][0,0,0,0]=np.nan
    elif kind=='tri_duplicate':d['triangles'][1]=d['triangles'][0]
    elif kind=='tri_reverse':d['triangles'][0]=[0,2,1]
    elif kind=='tri_range':d['triangles'][0]=[0,1,4]
    elif kind=='time_duplicate':d['times_s'][1]=d['times_s'][0]
    elif kind=='freq_reverse':d['frequencies_hz']=d['frequencies_hz'][::-1]
    elif kind=='freq_zero':d['frequencies_hz'][0]=0
    elif kind=='count_negative':d['common_fft_count'][0,0]=-1
    elif kind=='count_float':d['common_fft_count']=d['common_fft_count'].astype(float)
    elif kind=='count_bool':d['common_fft_count']=d['common_fft_count'].astype(bool)
    elif kind=='count_exceeds_nominal':d['common_fft_count'][0,0]=8
    elif kind=='mask_type':d['channel_triangle_usable']=d['channel_triangle_usable'].astype(int)
    elif kind=='mask_insufficient':d['common_fft_count'][0,0]=2
    elif kind=='zero_nonzero_sum':d['common_fft_count'][0,0]=0;d['channel_triangle_usable'][0,:,0]=False
    elif kind=='j_negative':d['triple_edge_sum'][0,0,0]=-1
    elif kind=='j_imaginary':d['triple_edge_sum'][0,0,0]+=1j
    elif kind=='overflow':d['edge_sums'][:]=1e200
    with pytest.raises(ValueError):validate_bispectrum(d,m)


@pytest.mark.parametrize('key,value',[('station_ids',['A0']*4),('time_origin_utc','2026-10-04T00:00:00'),('time_origin_utc','2026-10-04T00:00:00+09:00'),('voltage_unit','Jy'),('fft_length',True),('fft_length',5),('sample_rate_hz',float('nan')),('sample_rate_hz',True),('visibility_sha256','not-a-hash'),('processing_notes',[]),('input_sample_independence_verified',True),('input_mask_independence_verified',0),('bispectrum_unit','Jy^3'),('unknown','value')])
def test_invalid_metadata(fixture,key,value):
    d,m,*_=fixture;m[key]=value
    with pytest.raises(ValueError):validate_bispectrum(d,m)


@pytest.mark.parametrize('kind',['hash','axes','ids','epoch','fft','fs','unit','counts_missing','count_exceeds','same_count_edge_sum','usable_zero_weight'])
def test_source_link_rejects_mismatch(fixture,tmp_path,kind):
    d,m,source,original,metadata,_=fixture
    if kind=='hash':m['visibility_sha256']='0'*64
    elif kind=='axes':d['times_s']+=.1
    elif kind=='ids':m['station_ids'][0]='A4'
    elif kind=='epoch':m['time_origin_utc']='2026-10-04T00:00:01Z'
    elif kind=='fft':metadata['fft_length']=8
    elif kind=='fs':metadata['fft_sample_rate_hz']=2048
    elif kind=='unit':metadata['visibility_unit']='Jy'
    elif kind=='counts_missing':del original['valid_fft_count']
    elif kind=='count_exceeds':original['valid_fft_count'][:]=6
    elif kind=='same_count_edge_sum':d['edge_sums'][0,0,0,0]+=1
    elif kind=='usable_zero_weight':original['weights'][0,0,0]=0
    if kind in ('fft','fs','unit','counts_missing','count_exceeds','usable_zero_weight'):
        source.unlink();save_spectral(source,original,metadata)
        with source.open('rb') as stream:m['visibility_sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
    out=tmp_path/'raw.npz';save_bispectrum(out,d,m)
    with pytest.raises(ValueError):load_bispectrum(out,source)


@pytest.mark.parametrize('kind',['extra','object','version','metadata_shape','declared_payload'])
def test_archive_validation(fixture,tmp_path,kind):
    d,m,*_=fixture;normal=tmp_path/'normal.npz';save_bispectrum(normal,d,m)
    with np.load(normal,allow_pickle=False) as f:arrays={k:f[k] for k in f.files}
    bad=tmp_path/'bad.npz'
    if kind=='declared_payload':
        header=io.BytesIO();np.lib.format.write_array_header_1_0(header,{'descr':'<c16','fortran_order':False,'shape':(1000000000,)})
        with zipfile.ZipFile(normal) as z,zipfile.ZipFile(bad,'w') as w:
            for name in z.namelist():w.writestr(name,header.getvalue() if name=='edge_sums.npy' else z.read(name))
        with pytest.raises(ValueError,match='array payload'):load_bispectrum(bad)
        return
    if kind=='extra':arrays['unknown']=np.array(1)
    elif kind=='object':arrays['edge_sums']=np.array([object()],dtype=object)
    elif kind=='version':arrays['schema_version']=np.array(2)
    elif kind=='metadata_shape':arrays['metadata_json']=np.array([json.dumps(m)])
    np.savez_compressed(bad,**arrays)
    with pytest.raises(ValueError):load_bispectrum(bad)


def test_atomic_write_cleanup(fixture,tmp_path,monkeypatch):
    import vsora_formats.bispectrum as module
    d,m,*_=fixture
    def fail(*args,**kwargs):raise RuntimeError('injected writer failure')
    monkeypatch.setattr(module.np,'savez_compressed',fail)
    with pytest.raises(RuntimeError):save_bispectrum(tmp_path/'raw.npz',d,m)
    assert not (tmp_path/'raw.npz').exists() and not list(tmp_path.glob('.bispectrum-*'))


def test_jy_declared_unit_and_source_match(fixture,tmp_path):
    d,m,source,original,meta,_=fixture;m['voltage_unit']='sqrt(Jy)';meta['visibility_unit']='Jy'
    source.unlink();save_spectral(source,original,meta)
    with source.open('rb') as stream:m['visibility_sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
    out=tmp_path/'raw.npz';save_bispectrum(out,d,m);q=load_bispectrum(out,source)
    assert q['metadata']['bispectrum_unit']=='Jy^3' and q['source_visibility_verified']


def test_cell_and_metadata_size_limits(fixture):
    d,m,*_=fixture;m['fft_length']=4096
    a=np.broadcast_to(np.ones((),complex),(2,4096,56,3))
    d['edge_sums']=a;d['paired_edge_sums']=a;d['triple_edge_sum']=a[:,:,:,0]
    with pytest.raises(ValueError,match='dimensions'):validate_bispectrum(d,m)
    d,m,*_=fixture;m['processing_notes']=['x'*32768]
    with pytest.raises(ValueError,match='metadata too large'):validate_bispectrum(d,m)


def test_no_overwrite_when_destination_appears_during_write(fixture,tmp_path,monkeypatch):
    import vsora_formats.bispectrum as module
    d,m,*_=fixture;out=tmp_path/'raw.npz'
    def race(temp,destination):
        Path(destination).write_bytes(b'existing destination')
        raise FileExistsError('destination appeared')
    monkeypatch.setattr(module.os,'link',race)
    with pytest.raises(FileExistsError):save_bispectrum(out,d,m)
    assert out.read_bytes()==b'existing destination' and not list(tmp_path.glob('.bispectrum-*'))


def test_synthetic_two_cell_workflow_and_existing_output(tmp_path):
    from workflows.bispectrum_sidecar_validation import run
    out=tmp_path/'sidecar';q=run(out)
    assert q['common_fft_count']==[[13,13,15,15],[14,16,13,13]]
    assert q['source_visibility_verified'] and q['raw_arrays_roundtrip_exact']
    assert not q['actual_temporal_independence_verified'] and not q['production_rml_noise_model_changed']
    assert (out/'bispectrum-sidecar.png').exists()
    with pytest.raises(FileExistsError):run(out)


def test_archive_declared_size_limit(fixture,tmp_path,monkeypatch):
    import vsora_formats.bispectrum as module
    d,m,*_=fixture;out=tmp_path/'raw.npz';save_bispectrum(out,d,m)
    assert module.MAX_BYTES==40*1024**2
    monkeypatch.setattr(module,'MAX_BYTES',32)
    with pytest.raises(ValueError,match='oversized'):load_bispectrum(out)
