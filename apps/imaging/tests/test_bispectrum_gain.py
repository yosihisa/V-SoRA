from fractions import Fraction
import numpy as np
import pytest
from vsora_imaging.bispectrum_gain import bispectrum_gain_design


def exact_rank(matrix):
    if not matrix.size:return 0
    rows=[[Fraction(int(x)) for x in row] for row in matrix];rank=0
    for column in range(matrix.shape[1]):
        pivot=next((i for i in range(rank,len(rows)) if rows[i][column]),None)
        if pivot is None:continue
        rows[rank],rows[pivot]=rows[pivot],rows[rank];value=rows[rank][column]
        rows[rank]=[x/value for x in rows[rank]]
        for i in range(rank+1,len(rows)):
            value=rows[i][column]
            if value:rows[i]=[x-value*y for x,y in zip(rows[i],rows[rank])]
        rank+=1
    return rank


@pytest.mark.parametrize('n,amp,gain,invariant,conventional,phase',[
    (3,1,1,0,0,1),(4,4,4,0,2,3),(5,10,5,5,5,6),
    (6,15,6,9,9,10),(7,21,7,14,14,15),(8,28,8,20,20,21)])
def test_exact_integer_ranks_and_closure_span(n,amp,gain,invariant,conventional,phase):
    q=bispectrum_gain_design(n)
    assert exact_rank(q['triangle_amplitude_matrix'])==q['triangle_amplitude_rank']==amp
    assert exact_rank(q['triangle_station_gain_matrix'])==q['triangle_station_gain_rank']==gain
    assert exact_rank(q['conventional_logamp_matrix'])==q['conventional_logamp_rank']==conventional
    assert exact_rank(q['phase_matrix'])==q['closure_phase_rank']==phase
    assert q['gain_invariant_amplitude_rank']==invariant
    assert q['left_null_weight_rows']==q['triangle_count']-gain
    assert q['zero_identity_directions_in_left_null']==q['left_null_weight_rows']-invariant
    if n>=5:
        stacked=np.vstack([q['gain_invariant_baseline_operator'],q['conventional_logamp_matrix']])
        assert np.linalg.matrix_rank(stacked,tol=1e-10)==invariant
    assert not q['observed_statistic_logarithms_taken'] and not q['noise_or_likelihood_calculated']
    assert not q['independent_noisy_constraints_verified'] and not q['production_rml_noise_model_changed']


@pytest.mark.parametrize('n',range(3,9))
def test_population_gain_invariance(n):
    q=bispectrum_gain_design(n);rng=np.random.default_rng(n)
    log_visibility=rng.normal(size=q['baselines']);log_gain=rng.normal(size=n)
    triangle=q['triangle_amplitude_matrix'] @ log_visibility
    changed=triangle+q['triangle_station_gain_matrix'] @ log_gain
    w=q['gain_invariant_triangle_weights']
    np.testing.assert_allclose(w @ triangle,w @ changed,rtol=1e-12,atol=1e-12)
    h=q['conventional_logamp_matrix'];e=q['baseline_station_amplitude_matrix']
    np.testing.assert_array_equal(h @ e,0)
    oriented=np.zeros_like(e)
    for row,(i,j) in enumerate(q['pairs']):oriented[row,i]=1;oriented[row,j]=-1
    np.testing.assert_array_equal(q['phase_matrix'] @ oriented,0)


@pytest.mark.parametrize('n',[True,False,2,9,4.,'4',None])
def test_invalid_station_count(n):
    with pytest.raises(ValueError):bispectrum_gain_design(n)


def test_numpy_integer_and_fresh_design():
    first=bispectrum_gain_design(np.int64(4));first['triangle_amplitude_matrix'][:]=0
    assert bispectrum_gain_design(4)['triangle_amplitude_matrix'].sum()==12


def test_eight_station_null_rows_include_identities():
    q=bispectrum_gain_design(8)
    assert q['left_null_weight_rows']==48 and q['gain_invariant_amplitude_rank']==20
    assert q['zero_identity_directions_in_left_null']==28


def test_four_station_positive_covariances_same_bispectra_different_closure_amplitudes():
    q=bispectrum_gain_design(4);base=np.ones((4,4));np.fill_diagonal(base,10)
    changed=base.copy();changed[0,1]=changed[1,0]=2
    v0=base[tuple(q['pairs'].T)];v1=changed[tuple(q['pairs'].T)]
    log_gain=np.linalg.solve(q['triangle_station_gain_matrix'],-q['triangle_amplitude_matrix'] @ np.log(v1/v0))
    gain=np.exp(log_gain);matched=changed*gain[:,None]*gain[None,:]
    for s in (base,changed,matched):assert np.linalg.eigvalsh(s).min()>0
    v2=matched[tuple(q['pairs'].T)];a=q['triangle_amplitude_matrix'];h=q['conventional_logamp_matrix']
    np.testing.assert_allclose(np.exp(a @ np.log(v2)),np.exp(a @ np.log(v0)),rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(h @ np.log(v2),h @ np.log(v1),rtol=1e-12,atol=1e-12)
    assert np.max(abs(h @ np.log(v2)-h @ np.log(v0)))>.5
    assert q['gain_invariant_amplitude_rank']==0 and q['conventional_logamp_rank']==2
