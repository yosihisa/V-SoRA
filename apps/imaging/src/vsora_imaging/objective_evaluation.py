"""単位flux画像の目的関数を、最適化せずに分解して評価する。"""
import argparse
import hashlib
import json
from numbers import Real
from pathlib import Path
import numpy as np
from .rml import ClosureObjective
from .closure import load_visibility_input


def evaluate_closure_image(uvw, visibilities, weights, pairs, image, *, pixel_arcsec,
                           min_snr=10., prior_fwhm_arcsec=240., entropy=.01, tsv=.0001, centroid=.1):
    """画像をunit fluxへ正規化し、パラメータ総和penaltyを除いて評価する。"""
    supplied = dict(pixel_arcsec=pixel_arcsec, min_snr=min_snr, prior_fwhm_arcsec=prior_fwhm_arcsec,
                    entropy=entropy, tsv=tsv, centroid=centroid)
    if any(isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not np.isfinite(value)
           for value in supplied.values()):
        raise ValueError('finite real objective settings required; booleans are not settings')
    candidate = np.asarray(image)
    if (candidate.ndim != 2 or candidate.shape[0] != candidate.shape[1]
            or not 8 <= candidate.shape[0] <= 64 or np.iscomplexobj(candidate)
            or not np.issubdtype(candidate.dtype, np.number) or not np.isfinite(candidate).all() or np.any(candidate < 0)):
        raise ValueError('finite real nonnegative square image with 8..64 pixels required')
    candidate = np.asarray(candidate, dtype=float)
    with np.errstate(over='ignore'): total = float(candidate.sum())
    if not np.isfinite(total) or total <= 0: raise ValueError('finite positive candidate image sum required')
    unit_image = candidate/total
    settings = dict(pixels=candidate.shape[0], **{key: float(value) for key, value in supplied.items()})
    objective = ClosureObjective(uvw, visibilities, weights, pairs, **settings)
    metrics = objective._image_value_gradient(unit_image.ravel(), details=True)
    components = {key: metrics[key] for key in ('data_loss', 'entropy_loss', 'tsv_loss', 'centroid_loss')}
    if not np.isfinite(list(components.values()) + [metrics['objective']]).all():
        raise ValueError('image objective is outside finite numerical range')
    if not np.isclose(sum(components.values()), metrics['objective'], rtol=1e-12, atol=1e-14):
        raise ValueError('image objective components are inconsistent')
    return {'schema_version': 1, 'type': 'unit_flux_closure_image_objective', 'settings': settings,
            'candidate_sum_before_normalization': total, 'unit_flux_sum': float(unit_image.sum()),
            'metrics': metrics, 'optimizer_executed': False,
            'optimizer_parameter_sum_penalty_included': False,
            'absolute_flux_measured': False, 'absolute_position_measured': False,
            'actual_observation_success_certified': False,
            'limits': 'Same fixed observed high-SNR Gaussian closure approximation as current RML; wrapped phase loss. Unit-flux image cost excludes the optimizer parameter-scale penalty. Lower objective is not a certificate of true morphology, global optimality, or a calibrated image probability.'}


def main():
    p = argparse.ArgumentParser(description='候補画像の目的関数を最適化せず評価')
    p.add_argument('--input', required=True); p.add_argument('--image', required=True); p.add_argument('--output', required=True)
    p.add_argument('--pixel-arcsec', required=True, type=float)
    p.add_argument('--min-snr', type=float, default=10.); p.add_argument('--prior-fwhm-arcsec', type=float, default=240.)
    p.add_argument('--entropy', type=float, default=.01); p.add_argument('--tsv', type=float, default=.0001)
    p.add_argument('--centroid', type=float, default=.1)
    args = vars(p.parse_args()); source = args.pop('input'); image = args.pop('image'); output = args.pop('output')
    data = load_visibility_input(source); candidate = np.load(image, allow_pickle=False)
    result = evaluate_closure_image(data['uvw_lambda'], data['visibilities'], data['weights'], data['pairs'], candidate, **args)
    for name, path in (('input_sha256', source), ('candidate_sha256', image)):
        with Path(path).open('rb') as stream: result[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
    with Path(output).open('x') as stream: json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps(result, allow_nan=False))


if __name__ == '__main__': main()
