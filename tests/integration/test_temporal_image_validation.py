"""未使用の値が学習入力や局所fitへ混入しないことを実計算で確かめる。"""
from copy import deepcopy
from itertools import combinations
import numpy as np
import pytest
from workflows.temporal_image_validation import split_times,partition_input,prior_image,NUMERIC_FIELDS
from vsora_imaging.rml import fit_closure_image


def sample():
    pairs=np.array(list(combinations(range(4),2)));v=np.ones((8,1,6),complex);v*=np.exp(1j*np.linspace(-.03,.03,6));w=np.full(v.shape,1e4)
    return {'visibilities':v,'weights':w,'pairs':pairs,'uvw_lambda':np.zeros((*v.shape,3)),'times_s':np.arange(8,dtype=float),'frequencies_hz':np.array([1.42e9]),'integration_s':np.ones((8,6)),
            'metadata':{'visibility_unit':'ADC^2','config':{'source':{'ra_deg':1.,'dec_deg':2.,'model':'known-shape','total_flux_jy':1000.},'observation':{'frequency_hz':1.42e9},'image':{},'stations':[{'truth_gain':3.}]},'clock_truth':'excluded'},'diagnostic_station_power':np.ones((8,1,4))}


def test_even_odd_complement_all_and_balanced_indices():
    a=split_times(8);np.testing.assert_array_equal(np.flatnonzero(a['even_training']),[0,2,4,6]);np.testing.assert_array_equal(a['odd_training'],~a['even_training'])
    assert not (a['even_training']&a['odd_training']).any() and (a['even_training']|a['odd_training']).all() and a['all_training'].all()


def test_partition_strips_truth_and_diagnostics_preserves_original():
    d=sample();before=deepcopy(d);mask=split_times(8)['even_training'];q=partition_input(d,mask)
    assert set(q)==set(NUMERIC_FIELDS)|{'metadata'} and set(q['metadata']['config'])=={'source','image','observation'}
    assert q['metadata']['config']['source']=={'model':'unknown','ra_deg':1.,'dec_deg':2.}
    assert not q['metadata']['generating_truth_supplied_to_fitter'] and q['metadata']['training_time_indices']==[0,2,4,6]
    assert q['visibilities'][~mask].min()==1+0j and np.all(q['weights'][~mask]==0)
    for k in NUMERIC_FIELDS:np.testing.assert_array_equal(d[k],before[k])
    assert d['metadata']==before['metadata']


def test_unseen_visibility_weight_and_truth_changes_cannot_change_training_numbers_or_actual_fit():
    d=sample();mask=split_times(8)['even_training'];changed=deepcopy(d);changed['visibilities'][~mask]*=37*np.exp(1.7j);changed['weights'][~mask]*=2.;changed['metadata']['config']['source']['total_flux_jy']=1e10
    a=partition_input(d,mask);b=partition_input(changed,mask)
    for k in NUMERIC_FIELDS:np.testing.assert_array_equal(a[k],b[k])
    assert a['metadata']==b['metadata']
    kwargs={'pixels':8,'pixel_arcsec':64.,'starts':1,'max_iterations':2,'seed':21}
    x,s=fit_closure_image(a['uvw_lambda'],a['visibilities'],a['weights'],a['pairs'],**kwargs)
    y,t=fit_closure_image(b['uvw_lambda'],b['visibilities'],b['weights'],b['pairs'],**kwargs);np.testing.assert_array_equal(x,y)
    for value in [s,t]:
        for run in value['runs']:run.pop('elapsed_s')
    assert s==t


@pytest.mark.parametrize('mask',[np.ones(7,bool),np.ones(8,int),np.ones((8,1),bool),[True],None])
def test_bad_time_mask_is_rejected(mask):
    with pytest.raises(ValueError):partition_input(sample(),mask)


@pytest.mark.parametrize('n',[0,1,-1,True,8.,None])
def test_bad_time_count_is_rejected(n):
    with pytest.raises(ValueError):split_times(n)


def test_zero_training_weights_are_preserved_without_fabricating_data():
    d=sample();q=partition_input(d,np.zeros(8,bool));assert np.all(q['visibilities']==1+0j) and not q['weights'].any()
    with pytest.raises(ValueError,match='no high SNR'):fit_closure_image(q['uvw_lambda'],q['visibilities'],q['weights'],q['pairs'],pixels=8,starts=1,max_iterations=1)


def test_all_training_does_not_change_any_numeric_input_and_prior_matches_native():
    d=sample();q=partition_input(d,split_times(8)['all_training'])
    for k in NUMERIC_FIELDS:np.testing.assert_array_equal(q[k],d[k])
    from vsora_imaging.rml import ClosureObjective
    objective=ClosureObjective(q['uvw_lambda'],q['visibilities'],q['weights'],q['pairs'],pixels=8,pixel_arcsec=64.,prior_fwhm_arcsec=240.)
    np.testing.assert_array_equal(prior_image().ravel(),objective.prior)


@pytest.mark.parametrize('unit',['ADC^2','Jy'])
def test_training_archive_roundtrip_handles_both_units_and_jy_read_alias(tmp_path,unit):
    from vsora_formats.spectral import save_spectral,load_spectral
    from workflows.temporal_image_validation import training_arrays_identity
    d=sample();d['metadata']['visibility_unit']=unit;q=partition_input(d,split_times(8)['even_training']);path=tmp_path/'training.npz'
    save_spectral(path,{k:q[k] for k in NUMERIC_FIELDS},q['metadata']);loaded=load_spectral(path)
    assert training_arrays_identity(loaded)==training_arrays_identity(q) and loaded['metadata']==q['metadata']
    if unit=='Jy':assert loaded['vis_jy'] is loaded['visibilities']
    with np.load(path,allow_pickle=False) as archive:assert not any(archive[n].dtype.hasobject for n in archive.files)
