"""Finite model arithmetic tests; artificial recordings and declared masks only."""
from copy import deepcopy
import os

import numpy as np
import pytest
import vsora_correlator.lba_alignment as alignment
from vsora_formats.lba import LBAFragmentRecording
from vsora_formats.lba_band import LBAComplexBandView
from workflows.lba_clocked_band_validation import finite_clock_reference, model_case
from workflows.public_lba_fragments import scalar_reference


@pytest.fixture
def source(tmp_path):
    header=tmp_path/'header';payload=tmp_path/'payload'
    header.write_bytes(b'20200102:030405\n');raw=bytes((i*73+19)%256 for i in range(65536));payload.write_bytes(raw)
    reader=LBAFragmentRecording(header,payload,1,nominal_sample_rate_hz=8000000,recorded_pol_order=('R','L'))
    view=LBAComplexBandView(reader,recorded_pol_index=0,sideband='U')
    return view,reader,raw


@pytest.mark.parametrize('case',[0,1])
@pytest.mark.parametrize('start',[96.125,1027.25,12000.5])
def test_full_finite_reference_and_chunk_invariance(source,case,start):
    band,reader,raw=source;m=model_case(case)
    view=alignment.LBAClockedBandView(band,model=m,invalid_source_ranges=[(1050,1052)])
    times=m['input_start_offset_s']+(start+np.arange(129)*1.0001)/m['actual_sample_rate_hz']
    got=view.query(times);expected,valid,positions=finite_clock_reference(scalar_reference(raw)[:,0],2,m,times,[(1050,1052)])
    np.testing.assert_allclose(got['complex_samples'],expected,rtol=1e-9,atol=1e-5)
    np.testing.assert_array_equal(got['valid'],valid)
    np.testing.assert_allclose(got['source_positions'],positions,rtol=0,atol=1e-9)
    parts=[view.query(times[:1]),view.query(times[1:8]),view.query(times[8:39]),view.query(times[39:])]
    for key in ['complex_samples','valid','source_positions','query_times_s']:
        np.testing.assert_array_equal(got[key],np.concatenate([p[key] for p in parts]))
    assert reader.payload_hash_reads==1 and reader.maximum_payload_read_bytes<=8258
    assert band.actual_sample_rate_hz is None and band.station_id is None


@pytest.mark.parametrize('key,value',[
    ('schema_version',True),('station_id','../station'),('station_id',None),
    ('time_origin_utc','2020-99-02T03:04:05Z'),('time_origin_utc','2020-01-02T03:04:05+00:00'),
    ('time_origin_utc','2020-01-02T03:04:05.1234567890Z'),
    ('actual_sample_rate_hz',None),('actual_sample_rate_hz',True),('actual_sample_rate_hz',float('nan')),
    ('actual_sample_rate_hz',0),('actual_sample_rate_hz',8009000),('actual_sample_rate_hz',10**400),
    ('input_start_offset_s',False),('input_start_offset_s',3.01),
    ('rf_band_edge_hz',None),('rf_band_edge_hz',0),('rf_band_edge_hz',float('inf')),
    ('output_center_frequency_hz',1),('phase_offset_rad',None),('phase_offset_rad',True),
    ('clock_provenance','assumed'),('rf_provenance','verified')])
def test_bad_model_before_any_sample_read(source,key,value):
    band,reader,_=source;m=model_case();m[key]=value
    with pytest.raises(ValueError):alignment.LBAClockedBandView(band,model=m)
    assert reader.payload_read_calls==0


def test_complete_model_and_live_view_required(source):
    band,reader,_=source
    for m in [None,{},dict(model_case(),unexpected=1)]:
        with pytest.raises(ValueError):alignment.LBAClockedBandView(band,model=m)
    with pytest.raises(TypeError):alignment.LBAClockedBandView(reader,model=model_case())


@pytest.mark.parametrize('invalid',[None,True,[(3,2)],[(-1,2)],[(0,True)],[(0,999999)],[(4,9),(8,10)],[(9,10),(1,2)]])
def test_invalid_range_contract(source,invalid):
    with pytest.raises(ValueError):alignment.LBAClockedBandView(source[0],model=model_case(),invalid_source_ranges=invalid)


@pytest.mark.parametrize('times',[[],[True],[False,.001],[[.001]],['.001'],[1j],
    [float('nan')],[float('inf')],[.001,.001],[.002,.001],[3.01],np.arange(2049)*1e-7,
    np.array([2,1],dtype=np.uint64)])
def test_bad_queries_before_read(source,times):
    band,reader,_=source;view=alignment.LBAClockedBandView(band,model=model_case())
    with pytest.raises(ValueError):view.query(times)
    assert reader.payload_read_calls==0


def simple_model():
    m=model_case();m.update(actual_sample_rate_hz=8000000,input_start_offset_s=0,
                           rf_band_edge_hz=1719000000,phase_offset_rad=0.)
    return m


@pytest.mark.parametrize('positions',[[95.9],[131072-97],[1000.,18000.]])
def test_support_and_span_before_read(source,positions):
    band,reader,_=source;view=alignment.LBAClockedBandView(band,model=simple_model())
    with pytest.raises(ValueError):view.query(np.array(positions)/8000000)
    assert reader.payload_read_calls==0


def test_maximum_read_and_center_not_rebased(source):
    band,reader,_=source;view=alignment.LBAClockedBandView(band,model=simple_model())
    result=view.query(np.array([1001.25,17319.25])/8000000)
    assert result['complex_input_count']==16384 and reader.maximum_payload_read_bytes<=8258
    first=view.query([96/8000000]);np.testing.assert_array_equal(first['source_positions'],[96.])
    assert first['processing_identity']['additional_causal_filter'] is False
    assert not first['processing_identity']['sample_coordinate_rebased']


def test_invalid_raw_support_and_unused_extra_guard(source):
    band,_,_=source;times=[1000/8000000]
    bad=alignment.LBAClockedBandView(band,model=simple_model(),invalid_source_ranges=[(1096,1097)]).query(times)
    assert not bad['valid'][0] and bad['complex_samples'][0]==0
    good=alignment.LBAClockedBandView(band,model=simple_model(),invalid_source_ranges=[(1097,1098)]).query(times)
    assert good['valid'][0]


def test_model_and_identity_are_copies(source):
    band,_,_=source;m=simple_model();view=alignment.LBAClockedBandView(band,model=m)
    m['actual_sample_rate_hz']=None;x=view.processing_identity;x['model']['station_id']='changed'
    assert view.processing_identity['model']['station_id']=='ARTIFICIAL-0'
    assert view.processing_identity['model']['time_origin_utc'].endswith('.123456789Z')
    assert not view.processing_identity['caller_provenance_verified']
    assert band.actual_sample_rate_hz is None
    view.query([1000/8000000])


def test_source_and_model_change_rejected(source):
    band,_,_=source;view=alignment.LBAClockedBandView(band,model=simple_model())
    view._model['actual_sample_rate_hz']=8000000.0
    with pytest.raises(ValueError):view.query([1000/8000000])
    view=alignment.LBAClockedBandView(band,model=simple_model());band.polarization_label='L'
    with pytest.raises(ValueError):view.query([1000/8000000])


def test_original_change_during_interpolation_rejected(source,monkeypatch):
    band,reader,_=source;view=alignment.LBAClockedBandView(band,model=simple_model());original=alignment.interpolate_samples
    def changed(*args,**kwargs):
        answer=original(*args,**kwargs);stat=reader.payload_path.stat()
        os.utime(reader.payload_path,ns=(stat.st_atime_ns,stat.st_mtime_ns+1000000));return answer
    monkeypatch.setattr(alignment,'interpolate_samples',changed)
    with pytest.raises(ValueError):view.query([1000/8000000])


def test_phase_origin_convention_with_mock_constant_band(source,monkeypatch):
    band,_,_=source;m=model_case();view=alignment.LBAClockedBandView(band,model=m)
    monkeypatch.setattr(band,'read_complex_samples',lambda start,count:np.ones(count,dtype=complex))
    times=m['input_start_offset_s']+np.array([1000.25,1001.5])/m['actual_sample_rate_hz']
    p=(times-m['input_start_offset_s'])*m['actual_sample_rate_hz']
    # Unreduced direct origin formula, independent of the product constant/delta split.
    angle=np.pi/2*(2+p)+2*np.pi*(m['rf_band_edge_hz']-m['output_center_frequency_hz'])*times+m['phase_offset_rad']
    np.testing.assert_allclose(view.query(times)['complex_samples'],np.exp(1j*angle),rtol=0,atol=1e-9)


def test_unit_context_change_rejected(source):
    view=alignment.LBAClockedBandView(source[0],model=simple_model());view.voltage_unit='ADC'
    with pytest.raises(ValueError):view.query([1000/8000000])
