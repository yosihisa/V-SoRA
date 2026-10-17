import copy
import numpy as np
import pytest
from vsora_simulator.template_score import fit_template_mean_score as fit,score_template_features as score

@pytest.fixture
def trained():
    p=np.array([[0.,1.],[1.,2.],[0.,3.]])
    c=np.array([[2.,3.],[4.,1.],[3.,5.]])
    return p,c,fit(p,c)

def test_projection_oracle(trained):
    p,c,m=trained;scale=max(abs(p).max(),abs(c).max())
    means=np.stack((p.mean(0),c.mean(0)))/scale
    d=means[1]-means[0];d/=abs(d).max()
    expected=np.sum((p/scale-means.mean(0))*d,axis=1)
    np.testing.assert_allclose(score(p,m),expected,rtol=1e-14,atol=1e-14)
    assert score(p.mean(0)[None,:],m)[0]<0<score(c.mean(0)[None,:],m)[0]
    assert not m['gaussian_density_fitted'] and not m['image_likelihood_defined']

@pytest.mark.parametrize('scale',[1e-200,1e200,-3.])
def test_feature_global_scaling(trained,scale):
    p,c,m=trained
    np.testing.assert_allclose(score(p*scale,fit(p*scale,c*scale)),score(p,m),rtol=2e-14,atol=2e-14)

def test_label_swap(trained):
    p,c,m=trained
    np.testing.assert_allclose(score(p,fit(c,p)),-score(p,m),rtol=2e-14,atol=2e-14)

@pytest.mark.parametrize('value',[0.,2.])
def test_equal_training_means_not_predictable(value):
    p=np.full((3,2),value);m=fit(p,p)
    assert m['state']=='unidentifiable_training_means'
    with pytest.raises(ValueError):score(p,m)

@pytest.mark.parametrize('bad',[None,np.ma.array([[1.,2.],[3.,4.]],mask=True),
    np.ones(3),np.ones((2,0)),np.ones((2,2,2)),np.ones((0,2)),np.ones((2,113)),
    np.ones((2,2),bool),np.ones((2,2),complex),np.full((2,2),np.nan),
    np.full((2,2),np.inf),np.ones((8193,1)),np.array([['a'],['b']])])
def test_invalid_matrix(bad):
    with pytest.raises(ValueError):fit(bad,np.ones((2,2)))

def test_training_count_and_dimension():
    with pytest.raises(ValueError):fit(np.ones((1,2)),np.ones((2,2)))
    with pytest.raises(ValueError):fit(np.ones((2,1)),np.ones((2,2)))

@pytest.mark.parametrize('field,value',[
    ('feature_count',True),('feature_count',3),('feature_count',2.),
    ('training_global_scale',0.),('training_global_scale',-1.),('training_global_scale',True),
    ('training_global_scale',float('inf')),('training_global_scale','1'),
    ('scaled_midpoint',[1.]),('scaled_midpoint',[1j,0j]),
    ('mean_difference_direction',[0.,0.]),('mean_difference_direction',[float('nan'),1.]),
    ('mean_difference_direction',np.ma.array([1.,2.],mask=True))])
def test_invalid_model_fields(trained,field,value):
    p,_,m=trained;m=copy.deepcopy(m);m[field]=value
    with pytest.raises(ValueError):score(p,m)

@pytest.mark.parametrize('model',[None,{}, {'state':'unidentifiable_training_means'},{'state':'unknown'}])
def test_unidentified_model(model):
    with pytest.raises(ValueError):score(np.ones((2,2)),model)

def test_score_does_not_change_model_or_inputs(trained):
    p,_,m=trained;before=copy.deepcopy(m);values=p.copy()
    score(p,m)
    assert m==before;np.testing.assert_array_equal(p,values)

def test_bad_test_dimension(trained):
    with pytest.raises(ValueError):score(np.ones((2,3)),trained[2])

def test_numerical_range_rejected():
    m=fit(np.array([[1e-300],[2e-300]]),np.array([[3e-300],[4e-300]]))
    with pytest.raises(ValueError):score(np.array([[1e300]]),m)
    m=fit(np.array([[1e307],[2e307]]),np.array([[3e307],[4e307]]))
    with pytest.raises(ValueError):score(np.array([[1e-307]]),m)
    with pytest.raises(ValueError):
        fit(np.array([[1e308,1e-308],[1e308,2e-308]]),np.array([[1e308,3e-308],[1e308,4e-308]]))
