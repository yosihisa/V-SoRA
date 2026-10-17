"""Finite common-sample algebra; no IID, phase or observing confidence claim."""
from itertools import permutations
import copy
import numpy as np
import pytest
from vsora_correlator.bispectrum_accumulator import BispectrumAccumulator
from vsora_correlator.bispectrum_power import normalize_common_power_bispectrum
from vsora_simulator.bispectrum_observed_power import observed_power_normalized_bispectrum


def accumulated(x,mask=None,chunk=7):
 a=BispectrumAccumulator(x.shape[-1],x.shape[1])
 for start in range(0,len(x),chunk):a.consume(x[start:start+chunk],None if mask is None else mask[start:start+chunk])
 return a.finish()


@pytest.mark.parametrize('stations',[3,4,8])
@pytest.mark.parametrize('chunk',[1,7,17])
@pytest.mark.parametrize('missing',[False,True])
def test_all_common_triangles_match_voltage_api(stations,chunk,missing):
 rng=np.random.default_rng(8901);x=rng.normal(size=(17,3,stations))+1j*rng.normal(size=(17,3,stations))
 mask=rng.uniform(size=(17,stations))>.12 if missing else np.ones((17,stations),bool)
 before=x.copy();q=accumulated(x,mask,chunk);r=normalize_common_power_bispectrum(q)
 for n,t in enumerate(q['triangles']):
  good=mask[:,t].all(axis=1)
  assert good.sum()>=3
  np.testing.assert_allclose(q['common_station_power_sums'][:,n],(abs(x[good][:,:,t])**2).sum(axis=0),rtol=1e-14)
  ref=observed_power_normalized_bispectrum(x[good].transpose(1,0,2),[t])
  for key in ('observed_power_normalized_u3','observed_power_normalized_ordinary_product'):
   np.testing.assert_allclose(r[key][:,n],ref[key][:,0],rtol=2e-11,atol=2e-12)
 assert r['u3_available'].all() and r['ordinary_available'].all()
 assert not r['input_sample_independence_verified'] and not r['input_mask_independence_verified']
 np.testing.assert_array_equal(x,before)


def test_direct_ordered_distinct_indices():
 rng=np.random.default_rng(8902);x=rng.normal(size=(5,2,3))+1j*rng.normal(size=(5,2,3))
 q=accumulated(x);r=normalize_common_power_bispectrum(q);numerator=np.zeros(2,complex)
 for a,b,c in permutations(range(5),3):numerator+=(x[a,:,0]*x[a,:,1].conj())*(x[b,:,1]*x[b,:,2].conj())*(x[c,:,2]*x[c,:,0].conj())
 power=(abs(x)**2).mean(axis=0)
 np.testing.assert_allclose(r['observed_power_normalized_u3'][:,0],numerator/60/np.prod(power,axis=-1),rtol=1e-12,atol=1e-12)


@pytest.mark.parametrize('gain_case',['moderate','large_product','tiny_product'])
def test_fixed_gain_cancels_without_forming_overflowing_power_product(gain_case):
 rng=np.random.default_rng(8903);x=rng.normal(size=(13,2,3))+1j*rng.normal(size=(13,2,3))
 amplitudes={'moderate':[.4,3.,.75],'large_product':[1e120,1e120,1e-120],'tiny_product':[1e-120,1e-120,1e120]}[gain_case]
 g=np.asarray(amplitudes)*np.exp(1j*np.array([.4,-.8,1.7]));a=normalize_common_power_bispectrum(accumulated(x));b=normalize_common_power_bispectrum(accumulated(x*g))
 for k in ('observed_power_normalized_u3','observed_power_normalized_ordinary_product'):np.testing.assert_allclose(a[k],b[k],rtol=1e-10,atol=2e-12)


@pytest.mark.parametrize('kept',[0,1,2,3])
def test_availability_not_implicit_zero_measurement(kept):
 x=np.ones((4,2,3),complex);mask=np.zeros((4,3),bool);mask[:kept]=True
 q=accumulated(x,mask);r=normalize_common_power_bispectrum(q)
 assert bool(r['u3_available'][0,0])==(kept>=3) and bool(r['ordinary_available'][0,0])==(kept>0)
 np.testing.assert_array_equal(r['observed_power_normalized_u3'],1 if kept>=3 else 0)
 np.testing.assert_array_equal(r['observed_power_normalized_ordinary_product'],1 if kept>0 else 0)


def test_zero_station_power_explicit_and_quality_flags_retained():
 x=np.ones((5,2,4),complex);x[:,:,0]=0;q=accumulated(x)
 q['channel_triangle_usable']=np.zeros(q['distinct_sample_bispectrum'].shape,bool)
 r=normalize_common_power_bispectrum(q)
 for n,t in enumerate(q['triangles']):assert bool(r['u3_available'][0,n])==(0 not in t)
 assert not r['normalized_u3_existing_quality_usable'].any()
 np.testing.assert_array_equal(r['observed_power_normalized_u3'][:,3],1)
 assert r['existing_quality_mask_supplied'] and not r['source_file_identity_verified']


def test_power_only_overflow_is_atomic_for_all_accumulated_sums():
 a=BispectrumAccumulator(3,2);a.consume(np.ones((3,2,3),complex));snapshot=[v.copy() for v in (a._p,a._a,a._h,a._j,a._counts)]
 bad=np.zeros((3,2,3),complex);bad[:,:,0]=1e200
 with pytest.raises(ValueError):a.consume(bad)
 for actual,expected in zip((a._p,a._a,a._h,a._j,a._counts),snapshot):np.testing.assert_array_equal(actual,expected)
 assert a._nominal==3


def test_fx_reorders_common_power_and_preserves_main_visibility_arrays():
 from vsora_correlator.stream_fx import FXAccumulator
 rng=np.random.default_rng(8904);nf=16;blocks=19;ns=4
 x=rng.normal(size=(ns,nf*blocks))+1j*rng.normal(size=(ns,nf*blocks));mask=np.ones(x.shape,bool);mask[0,3]=False;mask[1,nf*3]=False
 on=FXAccumulator(ns,2048000.,nf,1.42e9,collect_bispectrum=True);off=FXAccumulator(ns,2048000.,nf,1.42e9)
 for first in range(0,x.shape[1],nf*7):on.consume(x[:,first:first+nf*7],mask[:,first:first+nf*7]);off.consume(x[:,first:first+nf*7],mask[:,first:first+nf*7])
 a=on.finish();b=off.finish()
 for k,v in b.items():
  if isinstance(v,np.ndarray):np.testing.assert_array_equal(a[k],v)
  else:assert a[k]==v
 raw=a['raw_bispectrum'];r=normalize_common_power_bispectrum(raw);order=np.argsort(1.42e9+np.fft.fftfreq(nf,1/2048000.))
 fft=np.fft.fft(x.reshape(ns,blocks,nf).transpose(1,2,0),axis=1,norm='ortho')[:,order];valid=mask.reshape(ns,blocks,nf).all(axis=2).T
 for n,t in enumerate(raw['triangles']):
  good=valid[:,t].all(axis=1);ref=observed_power_normalized_bispectrum(fft[good].transpose(1,0,2),[t])
  np.testing.assert_allclose(raw['common_station_power_sums'][:,n],(abs(fft[good][:,:,t])**2).sum(axis=0),rtol=1e-14)
  np.testing.assert_allclose(r['observed_power_normalized_u3'][:,n],ref['observed_power_normalized_u3'][:,0],rtol=1e-11,atol=2e-12)
 np.testing.assert_array_equal(r['channel_triangle_usable'],raw['channel_triangle_usable'])


def test_global_station_power_is_not_substituted_for_triangle_common_power():
 x=np.ones((6,1,4),complex);x[:3,0,0]=10;mask=np.ones((6,4),bool);mask[:3,1]=False
 q=accumulated(x,mask);idx=np.flatnonzero((q['triangles']==[0,1,2]).all(axis=1))[0]
 assert q['common_station_power_sums'][0,idx,0]==3
 assert (abs(x[mask[:,0],0,0])**2).sum()==303
 np.testing.assert_allclose(normalize_common_power_bispectrum(q)['observed_power_normalized_u3'][0,idx],1)


@pytest.mark.parametrize('kind',['missing_power','negative_power','complex_power','masked_power','bad_shape','nan_power','bad_count','float_count','bad_triangle','duplicate_triangle','real_u3','nan_u3','zero_count_nonzero','insufficient_u3','zero_power_nonzero','quality_shape','quality_int'])
def test_bad_normalization_inputs(kind):
 q=accumulated(np.ones((5,2,4),complex));q=copy.deepcopy(q)
 if kind=='missing_power':del q['common_station_power_sums']
 elif kind=='negative_power':q['common_station_power_sums']*= -1
 elif kind=='complex_power':q['common_station_power_sums']=q['common_station_power_sums'].astype(complex)
 elif kind=='masked_power':q['common_station_power_sums']=np.ma.array(q['common_station_power_sums'])
 elif kind=='bad_shape':q['common_station_power_sums']=q['common_station_power_sums'][:,:,:2]
 elif kind=='nan_power':q['common_station_power_sums'][0,0,0]=np.nan
 elif kind=='bad_count':q['common_sample_count'][0]=-1
 elif kind=='float_count':q['common_sample_count']=q['common_sample_count'].astype(float)
 elif kind=='bad_triangle':q['triangles'][0]=[1,0,2]
 elif kind=='duplicate_triangle':q['triangles'][1]=q['triangles'][0]
 elif kind=='real_u3':q['distinct_sample_bispectrum']=q['distinct_sample_bispectrum'].real
 elif kind=='nan_u3':q['distinct_sample_bispectrum'][0,0]=np.nan
 elif kind=='zero_count_nonzero':q['common_sample_count'][0]=0
 elif kind=='insufficient_u3':q['common_sample_count'][0]=2
 elif kind=='zero_power_nonzero':q['common_station_power_sums'][0,0,0]=0
 elif kind=='quality_shape':q['channel_triangle_usable']=np.ones((1,1),bool)
 elif kind=='quality_int':q['channel_triangle_usable']=np.ones(q['distinct_sample_bispectrum'].shape,int)
 with pytest.raises(ValueError):normalize_common_power_bispectrum(q)


def test_storage_and_returned_power_do_not_alias_internal_state():
 a=BispectrumAccumulator(8,4096);assert a._p.nbytes==4096*56*3*8
 a.consume(np.ones((3,4096,8),complex));q=a.finish();q['common_station_power_sums'][:]=99
 np.testing.assert_array_equal(a._p,3)


@pytest.mark.parametrize('scale',[1e-200,1e200])
def test_unrepresentable_normalized_ratio_rejected(scale):
 q=accumulated(np.ones((5,1,3),complex));q['common_station_power_sums'][:]=scale
 with pytest.raises(ValueError,match='outside representable'):normalize_common_power_bispectrum(q)


@pytest.mark.parametrize('kind',['power_overflow','power_erasure','u3_component_erasure','ordinary_component_erasure'])
def test_extended_precision_input_not_silently_erased(kind):
 if np.finfo(np.longdouble).maxexp<=np.finfo(np.float64).maxexp:pytest.skip('no extended exponent range')
 q=accumulated(np.ones((5,1,3),complex))
 if kind.startswith('power_'):q['common_station_power_sums']=np.full((1,1,3),np.longdouble('1e400' if kind=='power_overflow' else '1e-400'))
 else:
  key='distinct_sample_bispectrum' if kind=='u3_component_erasure' else 'ordinary_common_sample_product'
  q[key]=np.ones((1,1),np.clongdouble);q[key].imag=np.longdouble('1e-400')
 with pytest.raises(ValueError,match='remain finite and nonzero'):normalize_common_power_bispectrum(q)


def test_channel_dependent_station_gain_with_same_materialized_masks():
 rng=np.random.default_rng(8905);x=rng.normal(size=(19,5,4))+1j*rng.normal(size=(19,5,4))
 mask=rng.uniform(size=(19,4))>.1
 g=np.exp(rng.uniform(-.8,.8,size=(5,4))+1j*rng.uniform(-np.pi,np.pi,size=(5,4)))
 a=normalize_common_power_bispectrum(accumulated(x,mask));b=normalize_common_power_bispectrum(accumulated(x*g[None,:,:],mask))
 for k in ('observed_power_normalized_u3','observed_power_normalized_ordinary_product'):np.testing.assert_allclose(a[k],b[k],rtol=1e-11,atol=2e-12)
