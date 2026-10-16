from vsora_imaging.window_symmetry import exact_window_sign_flip_test as evaluate
from itertools import product
from fractions import Fraction
import numpy as np
import pytest


def direct_scores(x):
 return [sum(sum(s[a]*int(x[a,b]) for a in range(len(x)))**2 for b in range(x.shape[1])) for s in product((1,-1),repeat=len(x))]


@pytest.mark.parametrize('q',[1,2,5,6,8,12])
def test_constant_vectors_have_exact_minimum_two_sided_p(q):
 r=evaluate(np.ones((q,3)));assert r['tail_count']==2 and r['upper_tail_p_value']==2/(2**q)


@pytest.mark.parametrize('x',[np.array([[1,2],[-3,4],[2,-1]]),np.array([[1,0],[1,0],[0,1],[0,1]]),np.array([[1],[-1],[1],[-1],[2],[-2]])])
def test_exact_integer_orbit_and_conditional_type_one_bound(x):
 scores=direct_scores(x);pvalues=[]
 for n,s in enumerate(product((1,-1),repeat=len(x))):
  result=evaluate(x*np.array(s)[:,None]);tail=sum(v>=scores[n] for v in scores)
  assert result['tail_count']==tail
  pvalues.append(Fraction(tail,len(scores)))
 for alpha in (Fraction(1,100),Fraction(1,20),Fraction(1,4),Fraction(1,2)):
  assert Fraction(sum(p<=alpha for p in pvalues),len(scores))<=alpha


def test_zero_vectors_p_one_and_input_unchanged():
 x=np.zeros((8,4));copy=x.copy();q=evaluate(x)
 assert q['upper_tail_p_value']==1 and q['tail_count']==256
 np.testing.assert_array_equal(x,copy)


def test_orthogonal_rows_have_identical_scores_not_false_rejection():
 q=evaluate(np.eye(8));assert q['upper_tail_p_value']==1


@pytest.mark.parametrize('scale',[1e-300,1e300,-2.7])
def test_scaling_does_not_change_tail(scale):
 x=np.array([[1.,2.],[-3.,4.],[2.,-1.],[.3,-.7],[.5,.6],[-.1,.2]])
 assert evaluate(x)['tail_count']==evaluate(x*scale)['tail_count']


def test_window_and_feature_permutation_and_global_orthogonal_transform():
 rng=np.random.default_rng(86);x=rng.normal(size=(8,5));r=evaluate(x)
 assert r['tail_count']==evaluate(x[::-1,::-1])['tail_count']
 orthogonal,_=np.linalg.qr(rng.normal(size=(5,5)))
 assert r['tail_count']==evaluate(x @ orthogonal)['tail_count']


def test_individual_window_flips_change_observed_statistic():
 x=np.ones((8,3));y=x.copy();y[:4]*=-1
 assert evaluate(x)['upper_tail_p_value']==1/128
 assert evaluate(y)['upper_tail_p_value']==1


def test_assumptions_and_claims_are_explicit():
 q=evaluate(np.ones((3,2)))
 for key in ('null_invariance_verified_from_data','marginal_symmetry_alone_sufficient','triangles_flipped_independently','gaussian_distribution_assumed','physical_voltage_model_validated','source_detection_claimed','production_rml_noise_model_changed'):
  assert q[key] is False


@pytest.mark.parametrize('bad',[None,1.,np.ones(3),np.ones((0,2)),np.ones((13,2)),np.ones((3,0)),np.ones((3,57)),np.ones((3,2),complex),np.ones((3,2),bool),np.array([['a']]),np.full((3,2),np.nan),np.full((3,2),np.inf),np.ma.array(np.ones((3,2)),mask=False)])
def test_invalid_input(bad):
 with pytest.raises(ValueError):evaluate(bad)


def test_near_ties_are_conservative_against_exact_dyadic_scores():
 x=np.array([[1.,2e-16],[0.,1.],[1e-16,-.5],[-.5,1e-16]])
 signs=list(product((1,-1),repeat=4))
 scores=[]
 for sign in signs:
  scores.append(sum(sum(Fraction(float(x[a,b]))*sign[a] for a in range(4))**2 for b in range(2)))
 for n,sign in enumerate(signs):
  result=evaluate(x*np.array(sign)[:,None])
  exact_tail=sum(v>=scores[n] for v in scores)
  assert result['tail_count']>=exact_tail


@pytest.mark.parametrize('value',['1e400','1e-400'])
def test_extended_precision_outside_float64_range_is_rejected(value):
 if np.finfo(np.longdouble).maxexp<=np.finfo(np.float64).maxexp:
  pytest.skip('platform longdouble does not extend float64 range')
 x=np.full((8,2),np.longdouble(value),dtype=np.longdouble)
 with pytest.raises(ValueError,match='float64'):evaluate(x)
