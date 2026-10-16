"""Finite whole-window sign-flip test; validity requires joint invariance."""
from functools import lru_cache
import numpy as np


@lru_cache(maxsize=12)
def _patterns(windows):
    bits=((np.arange(1 << windows)[:,None] >> np.arange(windows)) & 1).astype(np.int8)
    signs=1-2*bits;signs.setflags(write=False);return signs


def exact_window_sign_flip_test(window_vectors):
    """Enumerate every whole-row sign flip for a squared mean-vector norm.

    H0 requires the joint law to be invariant under each independent row
    sign flip. Marginal symmetry alone is insufficient. Columns may be
    dependent; a complete row is flipped together. No distribution fitting,
    Gaussian errors, empirical noise estimates or data selection is used.
    """
    if np.ma.isMaskedArray(window_vectors):raise ValueError('unmasked real window vectors required')
    raw=np.asarray(window_vectors)
    if (raw.ndim!=2 or not 1<=raw.shape[0]<=12 or not 1<=raw.shape[1]<=56
        or np.iscomplexobj(raw) or not np.issubdtype(raw.dtype,np.number) or not np.isfinite(raw).all()):
        raise ValueError('finite real [Q,D], Q1..12, D1..56 required')
    with np.errstate(over='ignore',invalid='ignore',under='ignore'):x=raw.astype(np.float64)
    if not np.isfinite(x).all() or np.any((raw!=0)&(x==0)):
        raise ValueError('float64 conversion must not overflow or erase a nonzero component')
    windows,features=x.shape;scale=float(np.max(abs(x)))
    normalized=x/scale if scale else x.copy()
    means=(_patterns(windows) @ normalized)/windows
    scores=np.sum(means*means,axis=1)
    observed=float(scores[0]);tolerance=float(4096*np.finfo(float).eps*scores.max())
    tail=int(np.count_nonzero(scores>=observed-tolerance));count=1 << windows
    return {'windows':windows,'features':features,'input_global_scale':scale,
            'observed_squared_mean_norm_scaled':observed,'comparison_absolute_tolerance_scaled':tolerance,
            'comparison_epsilon_multiplier':4096,'tail_count':tail,'group_size':count,'upper_tail_p_value':tail/count,
            'minimum_two_sided_resolution':2/count,'all_whole_window_signs_enumerated':True,
            'joint_window_sign_invariance_assumed':True,'null_invariance_verified_from_data':False,
            'marginal_symmetry_alone_sufficient':False,'triangles_flipped_independently':False,
            'gaussian_distribution_assumed':False,'physical_voltage_model_validated':False,
            'source_detection_claimed':False,'production_rml_noise_model_changed':False,
            'scope':'Conditional finite-group p value for whole-window sign invariance only. '
                    'Tie tolerance is conservative; zero or identical scores give p=1. No source '
                    'detection, extent/asymmetry inference, image confidence or actual independence guarantee.'}
