"""Fresh file correspondence, not proof that spectra were computed from raw."""
import json
from pathlib import Path
import shutil
import time
from itertools import combinations

import numpy as np
import pytest

from vsora_correlator.input_identity import InputIdentity
from vsora_correlator.session import load_session
from vsora_formats.spectral import load_spectral,save_spectral
from vsora_imaging.synthesis import merge_spectral
from workflows.vdif_closure_validation import make_fixture
from workflows.sigmf_pipeline_validation import prepare


@pytest.fixture
def inputs(tmp_path):
    make_fixture(tmp_path/'stored',frame_count=1)
    root=tmp_path/'raw';prepare(tmp_path/'stored',root,frame_count=1)
    source=InputIdentity(root/'manifest.json',root/'clock.json');children=[];paths=[]
    for i in range(2):
        dest=tmp_path/f'child-{i}';dest.mkdir();shutil.copy2(root/'observation.json',dest/'observation.json')
        c=json.loads((root/'manifest.json').read_text());c['blocks_per_integration']=32
        for station in c['stations']:station['sigmf']=str(root/station['sigmf'])
        manifest=dest/'manifest.json';manifest.write_text(json.dumps(c))
        view=source.bind_sigmf_session(manifest,root/'clock.json');config=load_session(manifest,allow_sigmf=True)
        pairs=np.array(list(combinations(range(4),2)));v=np.ones((1,32,6),complex)
        data={'visibilities':v,'weights':np.ones(v.shape),'uvw_lambda':np.zeros(v.shape+(3,)),
              'pairs':pairs,'frequencies_hz':np.sort(1.42e9+np.fft.fftfreq(32,1/2048000)),
              'times_s':np.array([.00075+i*.0005]),'integration_s':np.full((1,6),.0005),
              'valid_fft_count':np.full((1,6),32,int)}
        meta={'config':config['_config'],'visibility_unit':'ADC^2','input_format':'sigmf_ci16_le',
              'time_origin_utc':config['_config']['observation']['start_utc'],
              'nominal_integration_s':.0005,'fft_length':32,'fft_sample_rate_hz':2048000,
              'clock_mapping_applied':True,'phase_center_corrected':True,'input_identity':view.public_identity}
        path=dest/'spectral.npz';save_spectral(path,data,meta);paths.append(path);children.append(manifest)
    return root,children,paths


def arguments(inputs):
    root,children,_=inputs
    return dict(source_manifest=root/'manifest.json',clock_model=root/'clock.json',input_manifests=children)


def test_fresh_original_hash_once_and_child_control_correspondence(inputs,tmp_path,monkeypatch):
    from vsora_correlator import input_identity
    calls=[];digest=input_identity.digest_file
    def count(path):calls.append(Path(path));return digest(path)
    monkeypatch.setattr(input_identity,'digest_file',count)
    result=merge_spectral(inputs[2],tmp_path/'verified.npz',**arguments(inputs))
    check=result['input_identity_verification'];assert result['original_files_rehashed']
    assert len([p for p in calls if p.suffix=='.sigmf-data'])==4
    assert check['source_diagnostics']['sigmf_data_hash_file_reads']==4
    assert all(d['sigmf_data_hash_file_reads']==0 for d in check['derived_diagnostics'])
    assert 'no computation proof' in result['sigmf_identity_scope']
    normal=merge_spectral(inputs[2],tmp_path/'normal.npz')
    assert not normal['original_files_rehashed']
    with np.load(tmp_path/'verified.npz') as a,np.load(tmp_path/'normal.npz') as b:
        for key in a.files:
            if key!='metadata_json':np.testing.assert_array_equal(a[key],b[key])
    with pytest.raises(FileExistsError):merge_spectral(inputs[2],tmp_path/'verified.npz',**arguments(inputs))


@pytest.mark.parametrize('name',['station-1.sigmf-data','station-1.sigmf-meta','clock.json','observation.json','child','root'])
def test_changed_original_or_derived_control_is_not_recorded_identity(inputs,tmp_path,name):
    root,children,paths=inputs
    path=children[0] if name=='child' else root/('manifest.json' if name=='root' else name)
    if name=='root':
        c=json.loads(path.read_text());c['fft_length']=64;path.write_text(json.dumps(c))
    elif name=='observation.json':
        c=json.loads(path.read_text());c['site']['height_m']+=1;path.write_text(json.dumps(c))
    elif name.endswith('.sigmf-data'):
        data=bytearray(path.read_bytes());data[-1]^=1;path.write_bytes(data)
    else:path.write_text(path.read_text()+' ')
    with pytest.raises(ValueError):merge_spectral(paths,tmp_path/'bad.npz',**arguments(inputs))
    assert not (tmp_path/'bad.npz').exists()


@pytest.mark.parametrize('kind',['config','fft','rate','duration','pairs','frequencies','claim'])
def test_spectral_claims_and_axes_must_match_fresh_child(inputs,tmp_path,kind):
    path=inputs[2][0];data=load_spectral(path);meta=data.pop('metadata')
    if kind=='config':meta['config']['site']['height_m']+=1
    elif kind=='fft':meta['fft_length']=64
    elif kind=='rate':meta['fft_sample_rate_hz']=2048001
    elif kind=='duration':meta['nominal_integration_s']=.001
    elif kind=='pairs':data['pairs']=data['pairs'][::-1]
    elif kind=='frequencies':data['frequencies_hz']+=1000
    else:meta['input_identity']['input_manifest_sha256']='a'*64
    path.unlink();save_spectral(path,data,meta)
    with pytest.raises(ValueError):merge_spectral(inputs[2],tmp_path/'bad.npz',**arguments(inputs))
    assert not (tmp_path/'bad.npz').exists()


def test_original_change_while_reading_spectra_is_detected(inputs,tmp_path,monkeypatch):
    import vsora_imaging.synthesis as module
    load=module.load_spectral;calls=[]
    def mutate(path):
        data=load(path);calls.append(1)
        if len(calls)==1:
            raw=inputs[0]/'station-1.sigmf-data';time.sleep(.02);words=bytearray(raw.read_bytes());words[-1]^=1;raw.write_bytes(words)
        return data
    monkeypatch.setattr(module,'load_spectral',mutate)
    with pytest.raises(ValueError,match='changed'):
        module.merge_spectral(inputs[2],tmp_path/'bad.npz',**arguments(inputs))
    assert not (tmp_path/'bad.npz').exists()


@pytest.mark.parametrize('missing',['source_manifest','clock_model','input_manifests'])
def test_partial_source_options_are_rejected_before_input_access(tmp_path,missing):
    options=dict(source_manifest='missing',clock_model='missing',input_manifests=['missing','missing']);options.pop(missing)
    with pytest.raises(ValueError,match='supplied together'):merge_spectral(['missing','missing'],tmp_path/'bad.npz',**options)


def test_wrong_manifest_count_and_legacy_source_are_rejected(inputs,tmp_path):
    opts=arguments(inputs)
    with pytest.raises(ValueError,match='one input manifest'):
        merge_spectral(inputs[2],tmp_path/'bad.npz',**{**opts,'input_manifests':[]})
    with pytest.raises(ValueError,match='SigMF-only'):
        merge_spectral(inputs[2],tmp_path/'bad.npz',**{**opts,'source_manifest':tmp_path/'stored/manifest.json','clock_model':tmp_path/'stored/clock.json'})


def test_reference_image_requires_explicit_source_and_type(tmp_path):
    from vsora_imaging.synthesis import image_synthesis
    with pytest.raises(ValueError,match='all explicit source'):
        image_synthesis(['missing','missing'],tmp_path/'bad',sigmf_reference_image=True)
    with pytest.raises(ValueError,match='bool required'):
        image_synthesis(['missing','missing'],tmp_path/'bad',sigmf_reference_image=1)
    with pytest.raises(ValueError,match='requires sigmf_reference_image'):
        image_synthesis(['missing','missing'],tmp_path/'bad',source_manifest='missing')
    assert not (tmp_path/'bad.partial').exists()


def test_live_source_reuse_rejects_claimed_digest(inputs,tmp_path):
    with pytest.raises(TypeError,match='live InputIdentity'):
        merge_spectral(inputs[2],tmp_path/'bad.npz',**arguments(inputs),_source_identity={'sha256':'claim'})


def test_sigmf_image_opt_in_and_no_information_failure_keep_partial(inputs,tmp_path):
    from vsora_imaging.synthesis import image_synthesis
    with pytest.raises(ValueError,match='SigMF images require explicit'):
        image_synthesis(inputs[2],tmp_path/'implicit',starts=1,max_iterations=20)
    assert not (tmp_path/'implicit').exists() and (tmp_path/'implicit.partial/failure.json').exists()
    with pytest.raises(ValueError,match='no high SNR'):
        image_synthesis(inputs[2],tmp_path/'weak',sigmf_reference_image=True,**arguments(inputs),starts=1,max_iterations=20)
    assert not (tmp_path/'weak').exists() and (tmp_path/'weak.partial/failure.json').exists()
