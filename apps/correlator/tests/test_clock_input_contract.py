"""公開相関APIが不正時計をbuffer構築・出力作成より前に拒否する。"""
from copy import deepcopy
import json

import pytest
from vsora_correlator import aligned
from workflows.vdif_closure_validation import make_fixture


BAD_CLOCKS=[
    ('root',None),('root',[]),('root','clock'),
    ('schema_version',True),('schema_version',False),('schema_version',1.0),
    ('schema_version','1'),('schema_version',2),
    ('max_abs_baseband_hz',True),('max_abs_baseband_hz',False),
    ('max_abs_baseband_hz','409600'),('max_abs_baseband_hz',None),
    ('max_abs_baseband_hz',float('nan')),('max_abs_baseband_hz',float('inf')),
    ('max_abs_baseband_hz',10**400),('max_abs_baseband_hz',0),
    ('max_abs_baseband_hz',-1),('max_abs_baseband_hz',1e6),
    ('stations',None),('stations',{}),('stations',[]),
    ('last_station',None),('last_station',[]),('last_id','OTHER'),
    ('last_offset',True),('last_offset',False),('last_offset','0'),
    ('last_offset',None),('last_offset',float('nan')),('last_offset',float('inf')),
    ('last_offset',10**400),('last_rate',True),('last_rate','2048000'),
    ('last_rate',None),('last_rate',float('nan')),('last_rate',float('inf')),
    ('last_rate',10**400),('last_rate',0),('last_rate',2048000*1.002),
    ('missing_key',None),('extra_key',None),('last_extra_key',None),
]


def changed(clock,field,value):
    result=deepcopy(clock)
    if field=='root':return value
    if field=='last_station':result['stations'][-1]=value
    elif field=='last_id':result['stations'][-1]['id']=value
    elif field=='last_offset':result['stations'][-1]['input_start_offset_s']=value
    elif field=='last_rate':result['stations'][-1]['actual_sample_rate_hz']=value
    elif field=='missing_key':result.pop('schema_version')
    elif field=='extra_key':result['extra']=True
    elif field=='last_extra_key':result['stations'][-1]['extra']=True
    else:result[field]=value
    return result


@pytest.mark.parametrize('field,value',BAD_CLOCKS)
def test_clock_rejected_before_any_buffer_or_output(tmp_path,monkeypatch,field,value):
    make_fixture(tmp_path/'input',frame_count=16)
    clock=tmp_path/'input/clock.json';clock.write_text(json.dumps(changed(json.loads(clock.read_text()),field,value)))
    calls=[]
    def buffer(*args,**kwargs):
        calls.append(True)
        raise AssertionError('invalid clock reached a VDIF buffer')
    monkeypatch.setattr(aligned,'SampleBuffer',buffer)
    output=tmp_path/'output'
    with pytest.raises(ValueError):aligned.correlate_aligned(tmp_path/'input/manifest.json',clock,output,1)
    assert not calls and not output.exists() and not (tmp_path/'output.partial').exists()


@pytest.mark.parametrize('numeric_type',[int,float])
def test_numeric_clock_still_reaches_real_buffer_boundary(tmp_path,monkeypatch,numeric_type):
    make_fixture(tmp_path/'input',frame_count=16)
    path=tmp_path/'input/clock.json';clock=json.loads(path.read_text())
    clock['max_abs_baseband_hz']=numeric_type(409600)
    for row in clock['stations']:
        row['input_start_offset_s']=numeric_type(0);row['actual_sample_rate_hz']=numeric_type(2048000)
    path.write_text(json.dumps(clock))
    class ReachedBuffer(Exception):pass
    def buffer(*args,**kwargs):raise ReachedBuffer
    monkeypatch.setattr(aligned,'SampleBuffer',buffer)
    with pytest.raises(ReachedBuffer):aligned.correlate_aligned(tmp_path/'input/manifest.json',path,tmp_path/'out',1)
