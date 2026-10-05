"""Population bispectrum amplitude constraints with unknown station gains.

This is complete-array linear algebra on nonzero population visibilities.
It does not take logarithms of observed low-SNR statistics or define a likelihood.
"""
from itertools import combinations
import numpy as np
from .closure import closure_design


def bispectrum_gain_design(station_count):
    if isinstance(station_count,bool) or not isinstance(station_count,(int,np.integer)) or not 3<=station_count<=8:
        raise ValueError('integer complete station count3..8 required')
    n=int(station_count);pairs=np.array(list(combinations(range(n),2)),dtype=int)
    triangles=np.array(list(combinations(range(n),3)),dtype=int)
    lookup={tuple(edge):i for i,edge in enumerate(pairs)}
    amplitude=np.zeros((len(triangles),len(pairs)),dtype=int)
    station=np.zeros((len(pairs),n),dtype=int)
    for row,(i,j) in enumerate(pairs):station[row,[i,j]]=1
    for row,(i,j,k) in enumerate(triangles):
        amplitude[row,[lookup[(i,j)],lookup[(j,k)],lookup[(i,k)]]]=1
    gain=amplitude @ station
    u,s,_=np.linalg.svd(gain.astype(float),full_matrices=True)
    gain_rank=int(np.count_nonzero(s>s[0]*1e-12))
    weights=u[:,gain_rank:].T
    invariant=weights @ amplitude
    design=closure_design(pairs)
    def rank(matrix):
        return 0 if not matrix.size else int(np.linalg.matrix_rank(matrix,tol=1e-10))
    amp_rank=rank(amplitude);invariant_rank=rank(invariant)
    if invariant_rank!=amp_rank-gain_rank or not np.allclose(weights @ gain,0,rtol=0,atol=1e-12):
        raise ValueError('gain invariant design outside numerical tolerance')
    return {'pairs':pairs,'triangles':triangles,'triangle_amplitude_matrix':amplitude,
        'baseline_station_amplitude_matrix':station,'triangle_station_gain_matrix':gain,
        'gain_invariant_triangle_weights':weights,'gain_invariant_baseline_operator':invariant,
        'phase_matrix':design['phase_matrix'],'conventional_logamp_matrix':design['logamp_matrix'],
        'stations':n,'baselines':len(pairs),'triangle_count':len(triangles),
        'triangle_amplitude_rank':amp_rank,'triangle_station_gain_rank':gain_rank,
        'left_null_weight_rows':len(weights),'gain_invariant_amplitude_rank':invariant_rank,
        'zero_identity_directions_in_left_null':len(weights)-invariant_rank,
        'conventional_logamp_rank':rank(design['logamp_matrix']),'closure_phase_rank':rank(design['phase_matrix']),
        'all_population_visibilities_nonzero_assumed':True,'complete_baseline_set_assumed':True,
        'observed_statistic_logarithms_taken':False,'noise_or_likelihood_calculated':False,
        'independent_noisy_constraints_verified':False,'hardware_imaging_feasibility_verified':False,
        'production_rml_noise_model_changed':False,
        'scope':'Population/noiseless mean constraints only, unknown freely varying station gain amplitudes in one cell. Matrix rank is not statistical independence, detectability or image uniqueness. No low-SNR observed logs, hardware or image likelihood.'}
