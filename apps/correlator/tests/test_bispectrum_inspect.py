import hashlib,json
import os
from itertools import combinations
import numpy as np
import pytest
from vsora_correlator.bispectrum_accumulator import BispectrumAccumulator
from vsora_correlator import bispectrum_inspect as module
from vsora_formats.bispectrum import save_bispectrum,load_bispectrum,reconstruct_bispectrum
from vsora_formats.spectral import save_spectral


def sample(blocks=7,missing=False):
    rng=np.random.default_rng(66);x=rng.normal(size=(max(blocks,1),4,4))+1j*rng.normal(size=(max(blocks,1),4,4))
    good=np.ones((len(x),4),bool)
    if blocks==0:good[:]=False
    elif missing:good[:2,0]=False;good[3,1]=False
    a=BispectrumAccumulator(4,4);a.consume(x,good);q=a.finish()
    m=q['common_sample_count'];usable=np.broadcast_to(m>=3,(2,4,4)).copy();usable[:,0]=False
    data={'triangles':q['triangles'],'times_s':np.array([.01,.02]),'frequencies_hz':1.42e9+np.arange(4,dtype=float),
          'common_fft_count':np.stack([m,m]),'nominal_fft_count':np.full(2,len(x)),
          'edge_sums':np.stack([q['edge_sums']]*2),'paired_edge_sums':np.stack([q['paired_edge_sums']]*2),
          'triple_edge_sum':np.stack([q['triple_edge_sum']]*2),'channel_triangle_usable':usable}
    meta={'station_ids':['A0','A1','A2','A3'],'time_origin_utc':'2026-10-04T00:00:00Z','voltage_unit':'ADC',
          'fft_length':4,'sample_rate_hz':1024.,'visibility_sha256':'0'*64,'processing_notes':['Synthetic spectra for stored-value inspection only.']}
    return {**data,'metadata':meta},x,good


def files(tmp_path):
    data,x,good=sample();meta=data['metadata'];pairs=np.array(list(combinations(range(4),2)))
    values=np.stack([(x[:,:,i]*x[:,:,j].conj()).mean(axis=0) for i,j in pairs],axis=-1)
    original={'visibilities':np.stack([values]*2),'weights':np.ones((2,4,6)),'uvw_lambda':np.zeros((2,4,6,3)),
       'pairs':pairs,'times_s':data['times_s'],'frequencies_hz':data['frequencies_hz'],'valid_fft_count':np.full((2,6),len(x))}
    source=tmp_path/'source.npz';raw=tmp_path/'raw.npz'
    save_spectral(source,original,{'visibility_unit':'ADC^2','time_origin_utc':meta['time_origin_utc'],
       'config':{'stations':[{'id':i} for i in meta['station_ids']]},'fft_length':4,'fft_sample_rate_hz':1024.})
    meta['visibility_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    save_bispectrum(raw,{k:v for k,v in data.items() if k!='metadata'},meta)
    return raw,source


@pytest.mark.parametrize('ti,fi',[(0,1),(1,3),(0,0)])
def test_cell_values_and_masks_without_noise_claim(ti,fi):
    data,_,_=sample(missing=True);before={k:v.copy() for k,v in data.items() if isinstance(v,np.ndarray)}
    q=module.inspect_bispectrum_cell(data,ti,fi);u=reconstruct_bispectrum(data)
    for i,row in enumerate(q['triangles']):
        assert row['common_fft_count']==data['common_fft_count'][ti,i]
        assert row['distinct_sample_bispectrum_real']==u[ti,fi,i].real
        assert row['distinct_sample_bispectrum_imag']==u[ti,fi,i].imag
        assert row['channel_triangle_usable']==(fi!=0)
        assert row['state']==('masked_raw_value' if fi==0 else 'usable_raw_value')
    assert q['bispectrum_unit']=='ADC^6' and not q['noise_covariance_estimated'] and not q['source_visibility_verified']
    assert not q['production_rml_noise_model_changed'] and not q['closure_phase_unbiased_guarantee']
    json.dumps(q,allow_nan=False)
    for k,v in before.items():np.testing.assert_array_equal(v,data[k])


@pytest.mark.parametrize('blocks',[0,1,2])
def test_unavailable_u3_is_null_not_numeric_zero(blocks):
    data,_,_=sample(blocks);q=module.inspect_bispectrum_cell(data,0,1)
    for row in q['triangles']:
        assert row['state']=='insufficient_samples' and not row['distinct_sample_available']
        assert row['distinct_sample_bispectrum_real'] is None and row['distinct_sample_bispectrum_imag'] is None
        if blocks==0:assert row['ordinary_common_sample_product_real'] is None


@pytest.mark.parametrize('ti,fi',[(True,0),(0,True),(-1,0),(2,0),(0,4),(1.5,0),(0,'1')])
def test_invalid_indices(ti,fi):
    data,_,_=sample()
    with pytest.raises(ValueError,match='indices'):module.inspect_bispectrum_cell(data,ti,fi)


def test_verified_file_identity_and_no_overwrite(tmp_path):
    raw,source=files(tmp_path);out=tmp_path/'inspect.json';q=module.inspect_bispectrum_file(raw,source,out,1,1)
    assert q['source_visibility_verified'] and q['raw_bispectrum_sha256']==hashlib.sha256(raw.read_bytes()).hexdigest()
    assert q['source_visibility_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    assert json.loads(out.read_text())==q
    with pytest.raises(FileExistsError):module.inspect_bispectrum_file(raw,source,out,1,1)


@pytest.mark.parametrize('which',['raw','source'])
def test_input_changed_during_read_refuses_output(tmp_path,monkeypatch,which):
    raw,source=files(tmp_path);original=module.load_bispectrum
    def changed(*a,**kw):
        q=original(*a,**kw);path=raw if which=='raw' else source;stamp=path.stat()
        os.utime(path,ns=(stamp.st_atime_ns,stamp.st_mtime_ns+1_000_000_000));return q
    monkeypatch.setattr(module,'load_bispectrum',changed)
    with pytest.raises(ValueError,match='changed'):module.inspect_bispectrum_file(raw,source,tmp_path/'inspect.json',1)
    assert not (tmp_path/'inspect.json').exists()


def test_wrong_source_and_suffix_refused(tmp_path):
    raw,source=files(tmp_path);wrong=tmp_path/'wrong.npz';wrong.write_bytes(source.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='SHA256'):module.inspect_bispectrum_file(raw,wrong,tmp_path/'inspect.json',1)
    with pytest.raises(ValueError,match='JSON'):module.inspect_bispectrum_file(raw,source,tmp_path/'out.npz',1)
    assert not (tmp_path/'inspect.json').exists()


@pytest.mark.parametrize('bad',[None,{}, {'metadata':{}}])
def test_incomplete_raw_data_rejected(bad):
    with pytest.raises(ValueError,match='metadata'):module.inspect_bispectrum_cell(bad,0,1)
