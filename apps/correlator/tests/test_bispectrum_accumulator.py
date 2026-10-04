"""Common-sample incremental U3 sums checked against independent batch sums."""
from itertools import permutations
import numpy as np
import pytest
from vsora_correlator.bispectrum_accumulator import BispectrumAccumulator
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum


@pytest.mark.parametrize('stations,channels',[(3,1),(4,7),(8,2)])
def test_chunks_match_all_batch_triangles(stations,channels):
    rng=np.random.default_rng(61);x=rng.normal(size=(17,channels,stations))+1j*rng.normal(size=(17,channels,stations))
    a=BispectrumAccumulator(stations,channels)
    for part in (x[:1],x[1:3],x[3:11],x[11:]):a.consume(part)
    q=a.finish();ref=distinct_sample_bispectrum(x.transpose(1,0,2))
    np.testing.assert_array_equal(q['triangles'],ref['triangles'])
    np.testing.assert_allclose(q['distinct_sample_bispectrum'],ref['distinct_sample_bispectrum'],rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(q['ordinary_common_sample_product'],ref['ordinary_visibility_product'],rtol=1e-12,atol=1e-12)
    assert (q['common_sample_count']==17).all() and q['distinct_sample_available'].all()
    assert not q['input_sample_independence_verified'] and not q['generating_truth_used']


def test_small_explicit_all_distinct_time_indices():
    rng=np.random.default_rng(6102);x=rng.normal(size=(5,2,3))+1j*rng.normal(size=(5,2,3))
    a=BispectrumAccumulator(3,2);a.consume(x[:2]);a.consume(x[2:]);q=a.finish()
    expected=np.zeros(2,complex)
    for i,j,k in permutations(range(5),3):
        expected+=(x[i,:,0]*x[i,:,1].conj())*(x[j,:,1]*x[j,:,2].conj())*(x[k,:,2]*x[k,:,0].conj())
    np.testing.assert_allclose(q['distinct_sample_bispectrum'][:,0],expected/60,rtol=1e-12,atol=1e-12)


def test_each_triangle_uses_one_common_sample_set():
    rng=np.random.default_rng(6103);x=rng.normal(size=(12,3,4))+1j*rng.normal(size=(12,3,4))
    ok=np.ones((12,4),bool);ok[:2,0]=False;ok[2:5,1]=False;ok[5:9,2]=False
    a=BispectrumAccumulator(4,3);a.consume(x[:4],ok[:4]);a.consume(x[4:],ok[4:]);q=a.finish()
    for n,t in enumerate(q['triangles']):
        good=ok[:,t].all(axis=1);assert q['common_sample_count'][n]==good.sum()
        ref=distinct_sample_bispectrum(x[good].transpose(1,0,2),[t])
        np.testing.assert_allclose(q['distinct_sample_bispectrum'][:,n],ref['distinct_sample_bispectrum'][:,0],rtol=1e-12,atol=1e-12)
    assert q['input_mask_supplied'] and not q['input_mask_independence_verified']


@pytest.mark.parametrize('kept',[0,1,2,3])
def test_insufficient_common_samples_are_explicit(kept):
    a=BispectrumAccumulator(3,2);ok=np.zeros((4,3),bool);ok[:kept]=True
    a.consume(np.ones((4,2,3),complex),ok);q=a.finish()
    assert q['common_sample_count'][0]==kept and bool(q['distinct_sample_available'][0])==(kept>=3)
    np.testing.assert_array_equal(q['distinct_sample_bispectrum'],1 if kept>=3 else 0)
    assert np.isfinite(q['ordinary_common_sample_product']).all()


def test_empty_finish_and_one_shot():
    a=BispectrumAccumulator(3,1);q=a.finish();assert not q['distinct_sample_available'].any()
    np.testing.assert_array_equal(q['common_sample_count'],0)
    with pytest.raises(ValueError):a.finish()
    with pytest.raises(ValueError):a.consume(np.ones((3,1,3),complex))


def test_output_overflow_is_not_a_valid_finished_result():
    a=BispectrumAccumulator(3,1)
    a.consume(np.full((1000,1,3),1e50,dtype=complex))
    with pytest.raises(ValueError,match='output outside'):a.finish()
    assert not a._finished


def test_fixed_station_gain_and_subset():
    rng=np.random.default_rng(6104);x=rng.normal(size=(13,2,4))+1j*rng.normal(size=(13,2,4))
    g=np.array([.4,3,1.5,.75])*np.exp(1j*np.array([.2,-.7,1.1,2.1]));t=np.array([[0,1,3],[1,2,3]])
    a=BispectrumAccumulator(4,2,t);b=BispectrumAccumulator(4,2,t)
    a.consume(x);b.consume(x*g);q=a.finish();r=b.finish();factor=np.prod(abs(g[t])**2,axis=1)
    np.testing.assert_allclose(r['distinct_sample_bispectrum'],q['distinct_sample_bispectrum']*factor,rtol=1e-12,atol=1e-12)
    reconstructed=(np.prod(q['edge_sums'],axis=-1)-q['paired_edge_sums'][:,:,0]*q['edge_sums'][:,:,2]
        -q['paired_edge_sums'][:,:,1]*q['edge_sums'][:,:,1]-q['paired_edge_sums'][:,:,2]*q['edge_sums'][:,:,0]+2*q['triple_edge_sum'])/(13*12*11)
    np.testing.assert_allclose(reconstructed,q['distinct_sample_bispectrum'])


@pytest.mark.parametrize('stations,channels,triangles',[(True,1,None),(2,1,None),(9,1,None),(3,False,None),(3,0,None),(3,4097,None),(3,1,[]),(3,1,[[0,2,1]]),(3,1,[[0,1,3]]),(3,1,[[0.,1.,2.]]),(3,1,[[0,1,2],[0,1,2]])])
def test_bad_constructor(stations,channels,triangles):
    with pytest.raises(ValueError):BispectrumAccumulator(stations,channels,triangles)


@pytest.mark.parametrize('kind',['real','nan','inf','empty','shape','masked','mask_int','mask_shape','mask_masked','overflow','count'])
def test_bad_chunk_is_atomic(kind):
    a=BispectrumAccumulator(3,2);x=np.ones((3,2,3),complex);a.consume(x);valid=None
    if kind=='real':x=x.real
    elif kind=='nan':x[0,0,0]=np.nan
    elif kind=='inf':x[0,0,0]=np.inf
    elif kind=='empty':x=x[:0]
    elif kind=='shape':x=x[:,:1]
    elif kind=='masked':x=np.ma.array(x)
    elif kind=='mask_int':valid=np.ones((3,3),int)
    elif kind=='mask_shape':valid=np.ones((3,2),bool)
    elif kind=='mask_masked':valid=np.ma.array(np.ones((3,3),bool))
    elif kind=='overflow':x*=1e100
    elif kind=='count':a._counts[:]=1000000
    snapshot=(a._a.copy(),a._h.copy(),a._j.copy(),a._counts.copy(),a._nominal)
    with pytest.raises(ValueError):a.consume(x,valid)
    for actual,prior in zip((a._a,a._h,a._j,a._counts,a._nominal),snapshot):np.testing.assert_array_equal(actual,prior)


def test_upper_dimensions_fixed_storage_and_input_preservation():
    a=BispectrumAccumulator(8,4096);x=np.ones((1,4096,8),complex);before=x.copy()
    storage=sum(v.nbytes for v in (a._a,a._h,a._j,a._counts))
    a.consume(x);a.consume(x);a.consume(x);q=a.finish()
    assert q['triangles'].shape==(56,3) and q['distinct_sample_bispectrum'].shape==(4096,56)
    assert storage==sum(v.nbytes for v in (a._a,a._h,a._j,a._counts))
    np.testing.assert_array_equal(x,before);np.testing.assert_allclose(q['distinct_sample_bispectrum'],1)


def test_synthetic_iq_fft_workflow_and_saved_raw_arrays(tmp_path):
    from workflows.streaming_bispectrum_validation import run
    out=tmp_path/'streaming';q=run(out)
    assert q['synthetic_gaussian_iq_fft_processed'] and not q['physical_adc_vdif_processed']
    assert q['cases'][0]['common_sample_count']==[257]*4
    assert q['cases'][1]['common_sample_count']==[245,250,249,248]
    assert all(c['saved_raw_sums_roundtrip_exact'] for c in q['cases'])
    assert all(c['maximum_chunk_blocks']==7 for c in q['cases'])
    assert (out/'summary.json').exists() and (out/'streaming-bispectrum.png').exists()
    with pytest.raises(FileExistsError):run(out)
