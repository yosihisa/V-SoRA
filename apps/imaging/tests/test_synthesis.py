from itertools import combinations
from pathlib import Path
import numpy as np
import pytest
from vsora_observation import load_config
from vsora_formats.spectral import save_spectral,load_spectral
from vsora_imaging.synthesis import merge_spectral


def write(path,origin='2026-10-02T08:00:00Z',unit='ADC^2',frequency=1.42e9,times=(.15,.25),aligned=True):
    config=load_config(Path(__file__).resolve().parents[3]/'configs/experiments/ideal-point.json')
    config['source']['model']='unknown';config['source'].pop('total_flux_jy')
    p=np.array(list(combinations(range(4),2)));v=np.ones((2,1,6),complex)
    w=np.full(v.shape,1e4);w[0,0,0]=0
    data={'visibilities':v,'weights':w,'pairs':p,'uvw_lambda':np.zeros((*v.shape,3)),
          'times_s':np.array(times),'frequencies_hz':np.array([frequency]),'integration_s':np.full((2,6),.1)}
    save_spectral(path,data,{'config':config,'visibility_unit':unit,'time_origin_utc':origin,
         'phase_center_corrected':True,'clock_mapping_applied':aligned,'nominal_integration_s':.1})


def test_sort_utc_and_preserve_flags_without_averaging(tmp_path):
    write(tmp_path/'early.npz');write(tmp_path/'late.npz','2026-10-02T08:00:10Z')
    result=merge_spectral([tmp_path/'late.npz',tmp_path/'early.npz'],tmp_path/'merged.npz')
    data=load_spectral(tmp_path/'merged.npz')
    assert np.allclose(data['times_s'],[.15,.25,10.15,10.25])
    assert data['visibilities'].shape==(4,1,6)
    assert np.all(data['weights'][[0,2],0,0]==0)
    assert np.allclose(result['exposure_per_baseline_s'],.4)
    assert len(data['metadata']['source_inputs'])==2 and data['metadata']['visibility_unit']=='ADC^2'
    assert data['metadata']['config']['observation']['start_utc']=='2026-10-02T08:00:00.000Z'
    with pytest.raises(FileExistsError):merge_spectral([tmp_path/'early.npz',tmp_path/'late.npz'],tmp_path/'merged.npz')


@pytest.mark.parametrize('options',[{'unit':'Jy'},{'frequency':1.4201e9},{'aligned':False},{'times':(.15,.24)}])
def test_mismatch_or_overlap_is_rejected(tmp_path,options):
    write(tmp_path/'a.npz');write(tmp_path/'b.npz',**options)
    with pytest.raises(ValueError):merge_spectral([tmp_path/'a.npz',tmp_path/'b.npz'],tmp_path/'merged.npz')
    assert not (tmp_path/'merged.npz').exists()


def write_sigmf(path,times=(.15,.25),origin='2026-10-02T08:00:00.123456789Z',change=None):
    """Arithmetic-only metadata claims, not a real recording identity."""
    write(path,origin=origin,times=times)
    data=load_spectral(path);meta=data.pop('metadata')
    data['valid_fft_count']=np.full((len(times),6),100,dtype=np.int64)
    meta['config']['observation']['start_utc']=origin
    meta['input_format']='sigmf_ci16_le'
    meta['input_identity']={'input_manifest_sha256':'1'*64,'input_clock_sha256':'2'*64,
        'input_observation_sha256':'3'*64,'input_sigmf':[
            {'station_id':s['id'],'metadata':{'sha256':'4'*64,'bytes':200},
             'data':{'sha256':str(i+5)*64,'bytes':4000}}
            for i,s in enumerate(meta['config']['stations'])]}
    if change:change(meta)
    path.unlink();save_spectral(path,data,meta)


def integer_origin_ns(text):
    from datetime import datetime,timezone
    dt=datetime.strptime(text[:19],'%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
    delta=dt-datetime(1970,1,1,tzinfo=timezone.utc)
    fraction=text[19:-1].lstrip('.')
    return (delta.days*86400+delta.seconds)*10**9+int(fraction.ljust(9,'0'))


def test_sigmf_merge_preserves_integer_nanosecond_epoch_and_all_fields(tmp_path):
    write_sigmf(tmp_path/'a.npz');write_sigmf(tmp_path/'b.npz',times=(.35,.45),
        change=lambda m:m['input_identity'].update(input_manifest_sha256='9'*64))
    result=merge_spectral([tmp_path/'b.npz',tmp_path/'a.npz'],tmp_path/'merged.npz')
    data=load_spectral(tmp_path/'merged.npz');m=data['metadata']
    assert result['time_origin_utc']=='2026-10-02T08:00:00.123456789Z'
    assert not result['original_files_rehashed'] and not m['original_files_rehashed']
    assert m['time_origin_precision_digits']==9 and 'Recorded agreement only' in m['sigmf_identity_scope']
    assert m['config']['observation']['start_utc']==result['time_origin_utc']
    expected=integer_origin_ns(result['time_origin_utc'])
    for t,want in zip(data['times_s'],[.15,.25,.35,.45]):
        assert abs(integer_origin_ns(m['time_origin_utc'])+round(t*10**9)-(expected+round(want*10**9)))<=1
    assert expected-integer_origin_ns('2026-10-02T08:00:00.123Z')==456789
    assert [s['input_identity']['input_manifest_sha256'] for s in m['source_inputs']]==['9'*64,'1'*64]
    assert np.all(data['weights'][[0,2],0,0]==0)
    np.testing.assert_array_equal(data['valid_fft_count'],np.full((4,6),100))
    with pytest.raises(ValueError,match='already merged SigMF'):
        merge_spectral([tmp_path/'merged.npz',tmp_path/'a.npz'],tmp_path/'twice.npz')
    assert not (tmp_path/'twice.npz').exists()


@pytest.mark.parametrize('change',[
    lambda m:m.pop('input_identity'),
    lambda m:m.pop('input_format'),
    lambda m:m.update(visibility_unit='Jy'),
    lambda m:m['input_identity'].update(input_clock_sha256='a'*64),
    lambda m:m['input_identity'].update(input_observation_sha256='a'*64),
    lambda m:m['input_identity'].update(input_manifest_sha256='bad'),
    lambda m:m['input_identity']['input_sigmf'].reverse(),
    lambda m:m['input_identity']['input_sigmf'][0]['metadata'].update(sha256='a'*64),
    lambda m:m['input_identity']['input_sigmf'][0]['data'].update(bytes=True),
    lambda m:m['input_identity']['input_sigmf'][0]['data'].update(bytes=0),
    lambda m:m['input_identity']['input_sigmf'][0]['data'].update(sha256='a'*63),
    lambda m:m['input_identity']['input_sigmf'][0]['data'].update(sha256='6'*64),
    lambda m:m.update(time_origin_utc='2026-10-02T08:00:00.1234567890Z'),
    lambda m:m.update(time_origin_utc='2026-10-02T08:00:00.123456799Z'),
])
def test_sigmf_inconsistent_or_malformed_claims_fail_before_output(tmp_path,change):
    write_sigmf(tmp_path/'a.npz');write_sigmf(tmp_path/'b.npz',times=(.35,.45),change=change)
    with pytest.raises(ValueError):merge_spectral([tmp_path/'a.npz',tmp_path/'b.npz'],tmp_path/'bad.npz')
    assert not (tmp_path/'bad.npz').exists()


def test_mixed_recordings_and_shifted_epoch_rejected(tmp_path):
    write_sigmf(tmp_path/'a.npz');write(tmp_path/'legacy.npz',times=(.35,.45))
    with pytest.raises(ValueError,match='mixed SigMF'):
        merge_spectral([tmp_path/'a.npz',tmp_path/'legacy.npz'],tmp_path/'mixed.npz')
    write_sigmf(tmp_path/'other.npz',times=(.35,.45),origin='2026-10-02T08:00:01.123456789Z')
    with pytest.raises(ValueError,match='axes differ'):
        merge_spectral([tmp_path/'a.npz',tmp_path/'other.npz'],tmp_path/'shifted.npz')


def test_merge_only_cli_does_not_invoke_image_fitting(tmp_path,monkeypatch,capsys):
    import sys
    import vsora_imaging.synthesis as module
    write_sigmf(tmp_path/'a.npz');write_sigmf(tmp_path/'b.npz',times=(.35,.45))
    def forbidden(*a,**k):raise AssertionError('merge-only must not fit an image')
    monkeypatch.setattr(module,'image_synthesis',forbidden)
    monkeypatch.setattr(sys,'argv',['vsora-synthesis','--inputs',str(tmp_path/'a.npz'),str(tmp_path/'b.npz'),
        '--output',str(tmp_path/'merged.npz'),'--merge-only'])
    module.main();assert 'original_files_rehashed' in capsys.readouterr().out


@pytest.mark.parametrize('kind',['missing','bool','negative','shape','unknown'])
def test_sigmf_fft_count_and_unrecognized_field_cannot_be_lost(tmp_path,kind):
    write_sigmf(tmp_path/'a.npz');write_sigmf(tmp_path/'b.npz',times=(.35,.45))
    path=tmp_path/'b.npz';data=load_spectral(path);meta=data.pop('metadata')
    if kind=='missing':data.pop('valid_fft_count')
    elif kind=='bool':data['valid_fft_count']=np.ones((2,6),bool)
    elif kind=='negative':data['valid_fft_count'][0,0]=-1
    elif kind=='shape':data['valid_fft_count']=np.ones((2,5),int)
    else:data['unrecognized_extra']=np.ones(2)
    path.unlink();save_spectral(path,data,meta)
    with pytest.raises(ValueError):merge_spectral([tmp_path/'a.npz',path],tmp_path/'bad.npz')
    assert not (tmp_path/'bad.npz').exists()
