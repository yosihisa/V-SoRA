"""Opt-in FX raw U3 sums; ordinary correlation arrays preserved exactly."""
import numpy as np
import pytest
from vsora_correlator.stream_fx import FXAccumulator
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum


@pytest.mark.parametrize('quality_enabled,missing',[(False,False),(False,True),(True,False),(True,True)])
def test_main_arrays_unchanged_and_raw_matches_common_batch(quality_enabled,missing):
    rng=np.random.default_rng(63);stations=4;nf=16;blocks=37;fs=2048000.;center=1.42e9
    x=rng.normal(size=(stations,nf*blocks))+1j*rng.normal(size=(stations,nf*blocks));valid=np.ones(x.shape,bool)
    if missing:valid[0,0]=False;valid[1,16*3+4]=False;valid[2,-1]=False
    quality={'channel_weights':True,'min_sk_blocks':24,'sk_bounds':[.1,3.],
        'exclude_rf_ranges_hz':[[center-.1,center+.1]]} if quality_enabled else None
    off=FXAccumulator(stations,fs,nf,center,quality)
    on=FXAccumulator(stations,fs,nf,center,quality,collect_bispectrum=True)
    for first in range(0,x.shape[1],nf*7):
        off.consume(x[:,first:first+nf*7],valid[:,first:first+nf*7]);on.consume(x[:,first:first+nf*7],valid[:,first:first+nf*7])
    baseline=off.finish(.002);combined=on.finish(.002)
    assert set(combined)-set(baseline)=={'raw_bispectrum'}
    for key,value in baseline.items():
        if isinstance(value,np.ndarray):np.testing.assert_array_equal(combined[key],value)
        else:assert combined[key]==value
    raw=combined['raw_bispectrum'];order=np.argsort(center+np.fft.fftfreq(nf,1/fs))
    spectrum=np.fft.fft(x.reshape(stations,blocks,nf).transpose(1,2,0),axis=1,norm='ortho')[:,order]
    block_ok=valid.reshape(stations,blocks,nf).all(axis=2).T
    for n,t in enumerate(raw['triangles']):
        good=block_ok[:,t].all(axis=1);reference=distinct_sample_bispectrum(spectrum[good].transpose(1,0,2),[t])
        assert raw['common_sample_count'][n]==good.sum()
        np.testing.assert_allclose(raw['distinct_sample_bispectrum'][:,n],reference['distinct_sample_bispectrum'][:,0],rtol=1e-12,atol=1e-12)
    np.testing.assert_array_equal(raw['frequencies_hz'],combined['frequencies_hz'])
    if quality_enabled:
        excluded=np.flatnonzero(abs(combined['frequencies_hz']-center)<.1)
        assert len(excluded)==1 and not raw['channel_triangle_usable'][excluded].any()
    assert not raw['input_sample_independence_verified'] and not raw['input_mask_independence_verified']


@pytest.mark.parametrize('blocks',[1,2,3])
def test_insufficient_triangle_samples(blocks):
    rng=np.random.default_rng(6302);a=FXAccumulator(3,2048000.,4,1.42e9,collect_bispectrum=True)
    x=rng.normal(size=(3,blocks*4))+1j*rng.normal(size=(3,blocks*4));a.consume(x)
    q=a.finish()['raw_bispectrum'];assert bool(q['distinct_sample_available'][0])==(blocks>=3)
    if blocks<3:
        assert not q['channel_triangle_usable'].any();np.testing.assert_array_equal(q['distinct_sample_bispectrum'],0)


@pytest.mark.parametrize('stations,nf,option',[(2,4,True),(9,4,True),(3,4097,True),(3,4,1),(3,4,'true')])
def test_invalid_opt_in_dimensions_or_type(stations,nf,option):
    with pytest.raises(ValueError):FXAccumulator(stations,2048000.,nf,1.42e9,collect_bispectrum=option)


@pytest.mark.parametrize('kind',['mask_dtype','masked_samples','masked_valid','overflow','sample_limit'])
def test_invalid_raw_chunk_does_not_change_fx_state(kind):
    a=FXAccumulator(3,2048000.,4,1.42e9,collect_bispectrum=True);x=np.ones((3,12),complex);valid=np.ones(x.shape,bool)
    a.consume(x,valid)
    if kind=='mask_dtype':valid=valid.astype(int)
    elif kind=='masked_samples':x=np.ma.array(x)
    elif kind=='masked_valid':valid=np.ma.array(valid)
    elif kind=='overflow':x=x*1e100
    elif kind=='sample_limit':a.bispectrum._counts[:]=1000000
    snapshot=(a.cross.copy(),a.counts.copy(),a.power.copy(),a.power2.copy(),a.station_counts.copy(),a.samples)
    with pytest.raises(ValueError):a.consume(x,valid)
    for actual,prior in zip((a.cross,a.counts,a.power,a.power2,a.station_counts,a.samples),snapshot):np.testing.assert_array_equal(actual,prior)


def test_default_two_station_fx_remains_available():
    a=FXAccumulator(2,2048000.,4,1.42e9);a.consume(np.ones((2,12),complex))
    q=a.finish();assert 'raw_bispectrum' not in q and q['pairs'].shape==(1,2)


def test_point_one_second_workflow_and_existing_output(tmp_path):
    from workflows.fx_bispectrum_validation import run
    out=tmp_path/'fx';q=run(out)
    assert len(q['cases'])==2 and all(c['ordinary_arrays_bit_identical'] for c in q['cases'])
    assert all(c['nominal_seconds']==.1 for c in q['cases'])
    assert q['cases'][0]['available_channel_triangles']==128
    assert q['cases'][1]['available_channel_triangles']==124
    assert not q['physical_adc_vdif_processed'] and not q['production_rml_noise_model_changed']
    assert (out/'fx-bispectrum.png').exists()
    with pytest.raises(FileExistsError):run(out)
