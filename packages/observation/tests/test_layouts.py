import json
from pathlib import Path
import numpy as np
import pytest
from vsora_observation import layouts as w


@pytest.mark.parametrize('n',[4,8])
@pytest.mark.parametrize('kind',['spread','line','ring'])
@pytest.mark.parametrize('maximum',[25.,100.,600.])
def test_maximum_distance_and_shape(n,kind,maximum):
    positions=w.reference_layout(n,kind,maximum);base=w.reference_layout(n,kind)
    assert positions.shape==(n,3) and np.isfinite(positions).all()
    np.testing.assert_array_equal(positions[:,2],0)
    assert np.linalg.norm(positions[:,None]-positions[None,:],axis=-1).max()==pytest.approx(maximum,rel=1e-14)
    np.testing.assert_allclose(positions,base*maximum/600,rtol=1e-14,atol=1e-14)


@pytest.mark.parametrize('n',[4,8])
@pytest.mark.parametrize('kind',['spread','line','ring'])
def test_default_is_bit_identical_to_existing_gui(n,kind):
    golden=json.loads((Path(__file__).resolve().parents[3]/'validation/runs/stage080/legacy-layouts.json').read_text())['layouts'][f'{n}-{kind}']
    assert w.reference_layout(n,kind).tobytes()==np.asarray(golden,dtype=float).tobytes()


@pytest.mark.parametrize('n',[True,np.bool_(True),3,9,4.,'4'])
def test_invalid_station_count(n):
    with pytest.raises(ValueError):w.reference_layout(n,'spread')


@pytest.mark.parametrize('kind',['other',None,[],True])
def test_invalid_layout_kind(kind):
    with pytest.raises(ValueError):w.reference_layout(4,kind)


@pytest.mark.parametrize('maximum',[True,np.bool_(True),0,-1,9,601,np.nan,np.inf,1j,'100',[100],np.ma.array(100.)])
def test_invalid_maximum(maximum):
    with pytest.raises(ValueError):w.reference_layout(4,'spread',maximum)
