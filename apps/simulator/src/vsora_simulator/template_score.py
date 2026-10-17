"""Experimental fixed two-template mean score; no image likelihood."""
import numpy as np

def _features(values):
    if np.ma.isMaskedArray(values):
        raise ValueError("unmasked real feature matrix required")
    raw=np.asarray(values)
    if (raw.ndim!=2 or not 1<=raw.shape[1]<=112 or not 1<=len(raw)<=8192
        or not np.issubdtype(raw.dtype,np.number) or np.iscomplexobj(raw)
        or not np.isfinite(raw).all()):
        raise ValueError("finite real [N,D], N1..8192 D1..112 required")
    with np.errstate(over='ignore',invalid='ignore',under='ignore'):
        x=raw.astype(float)
    if not np.isfinite(x).all() or np.any((raw!=0)&(x==0)):
        raise ValueError("float64 must not overflow or erase a nonzero feature")
    return x


def fit_template_mean_score(point_training,casa_training):
    """Fit the midpoint and mean-difference direction from training only.

    Euclidean features are a specified baseline, not an optimal classifier,
    fitted Gaussian density, covariance model or source detection probability.
    """
    point=_features(point_training);casa=_features(casa_training)
    if min(len(point),len(casa))<2 or point.shape[1]!=casa.shape[1]:
        raise ValueError("at least2 training rows per label with identical feature dimension required")
    scale=float(max(np.max(abs(point)),np.max(abs(casa))))
    if scale:
        normalized_point=point/scale;normalized_casa=casa/scale
        if np.any((point!=0)&(normalized_point==0)) or np.any((casa!=0)&(normalized_casa==0)):
            raise ValueError("training scaling must not erase nonzero features")
        means=np.stack((normalized_point.mean(axis=0),normalized_casa.mean(axis=0)))
    else:means=np.zeros((2,point.shape[1]))
    difference=means[1]-means[0];direction_scale=float(np.max(abs(difference)))
    direction=np.zeros_like(difference) if direction_scale==0 else difference/direction_scale
    return {'state':'identified_training_direction' if direction_scale>0 else 'unidentifiable_training_means',
        'feature_count':point.shape[1],'point_training_count':len(point),'casa_training_count':len(casa),
        'training_global_scale':scale,'scaled_training_means':means.tolist(),
        'scaled_midpoint':(means.mean(axis=0)).tolist(),'mean_difference_direction':direction.tolist(),
        'direction_scale':direction_scale,'positive_score_label':'casa','zero_score_label':'point',
        'test_data_required_separately':True,'gaussian_density_fitted':False,'image_likelihood_defined':False,
        'unknown_receiver_sefd_estimated':False,'real_hardware_validation_performed':False}


def score_template_features(values,model):
    x=_features(values)
    if not isinstance(model,dict) or model.get('state')!='identified_training_direction':
        raise ValueError("identified training direction required; no prediction from equal means")
    count=model.get('feature_count');scale=model.get('training_global_scale')
    if isinstance(count,bool) or not isinstance(count,int) or count!=x.shape[1]:
        raise ValueError("matching trained feature dimension required")
    if isinstance(scale,bool) or not isinstance(scale,(float,int)) or not np.isfinite(scale) or scale<=0:
        raise ValueError("positive finite training scale required")
    vectors=[]
    for key in ('scaled_midpoint','mean_difference_direction'):
        if np.ma.isMaskedArray(model.get(key)):raise ValueError("unmasked trained vector required")
        raw=np.asarray(model.get(key))
        if (raw.shape!=(count,) or np.iscomplexobj(raw)
            or not np.issubdtype(raw.dtype,np.number) or not np.isfinite(raw).all()):
            raise ValueError("finite real trained center and direction required")
        with np.errstate(over='ignore',under='ignore',invalid='ignore'):v=raw.astype(float)
        if not np.isfinite(v).all() or np.any((raw!=0)&(v==0)):
            raise ValueError("trained vectors must fit float64 without erasing nonzero values")
        vectors.append(v)
    center,direction=vectors
    if not np.any(direction!=0):raise ValueError("nonzero training direction required")
    with np.errstate(over='raise',invalid='raise',divide='raise',under='ignore'):
        try:
            normalized=x/scale
            if np.any((x!=0)&(normalized==0)):raise ValueError("test scaling must not erase a nonzero feature")
            score=(normalized-center) @ direction
        except FloatingPointError:raise ValueError("test score outside finite numerical range") from None
    if not np.isfinite(score).all():raise ValueError("finite test scores required")
    return score
