"""Small CPU closure-only RML reference; output is relative flux per pixel.

Fixed observed high-SNR covariance, independent closure sets, positive unit
flux image, entropy/TSV priors and an explicit weak centroid penalty.
No generating sky model is accepted by the objective.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import time
import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.optimize import minimize
from scipy.special import softmax
from vsora_observation.geometry import tangent_grid
from .closure import form_closures, independent_closures, wrap_phase, load_visibility_input


class ClosureObjective:
    def __init__(self, uvw, visibilities, weights, pairs, pixels=32, pixel_arcsec=16.,
                 min_snr=10., prior_fwhm_arcsec=240., entropy=0.01, tsv=0.0001, centroid=0.1):
        uvw, v, w = np.asarray(uvw), np.asarray(visibilities), np.asarray(weights)
        if (v.ndim != 3 or uvw.shape != (*v.shape, 3) or not np.isfinite(uvw).all()
                or not isinstance(pixels, int) or not 8 <= pixels <= 64
                or not np.isfinite(pixel_arcsec) or pixel_arcsec <= 0
                or not np.isfinite(prior_fwhm_arcsec) or prior_fwhm_arcsec <= 0
                or any(not np.isfinite(x) or x < 0 for x in (entropy, tsv, centroid))):
            raise ValueError('invalid RML geometry or regularization settings')
        if v.size*pixels*pixels*16 > 128*1024**2:
            raise ValueError('direct Fourier matrix would exceed 128 MiB; select fewer cells or pixels')
        self.pixels, self.pixel_arcsec = pixels, pixel_arcsec
        self.shape = v.shape
        self.closures = c = form_closures(v, w, pairs, min_snr)
        self.cells = []
        self.count = 0
        for t in range(v.shape[0]):
            for f in range(v.shape[1]):
                cell = []
                for name in ['phase', 'logamp']:
                    indices, cov = independent_closures(c[name+'_matrix'], c[name+'_valid'][t, f], c['baseline_variance'][t, f])
                    matrix = c[name+'_matrix'][indices]
                    cell.append((name, matrix, c[name][t, f, indices], cho_factor(cov, lower=True) if len(indices) else None))
                    self.count += len(indices)
                self.cells.append(cell)
        if not self.count: raise ValueError('no high SNR independent closure measurements')
        l, m = tangent_grid(pixels, pixel_arcsec)
        n = np.sqrt(1-l*l-m*m)-1
        directions = np.stack([l.ravel(), m.ravel(), n.ravel()])
        self.fourier = np.exp(-2j*np.pi*uvw.reshape(-1, 3) @ directions)
        axis = (np.arange(pixels)-pixels//2)*pixel_arcsec
        yy, xx = np.meshgrid(axis, axis, indexing='ij')
        self.xy = np.stack([xx.ravel(), yy.ravel()])/(pixel_arcsec*pixels/2)
        self.prior = np.maximum(np.exp(-4*np.log(2)*(xx*xx+yy*yy)/prior_fwhm_arcsec**2), 1e-12).ravel()
        self.prior /= self.prior.sum()
        self.entropy, self.tsv, self.centroid = entropy, tsv, centroid
        self.phase_loss = 'wrapped'

    def value_gradient(self, z, details=False):
        q = softmax(np.asarray(z))
        if q.shape != self.prior.shape or not np.isfinite(q).all(): raise ValueError('invalid image parameters')
        result = self._image_value_gradient(q, details)
        if details: return result
        value, grad = result
        return value, q*(grad-float(grad @ q))

    def intensity_value_gradient(self, x, details=False):
        x = np.asarray(x)
        if x.shape != self.prior.shape or not np.isfinite(x).all() or np.any(x < 0):
            raise ValueError('nonnegative image parameters required')
        positive = x+1e-12; total = positive.sum(); q = positive/total
        result = self._image_value_gradient(q, details)
        # Fix the otherwise redundant scale of the optimization parameters.
        # This has no effect on the unit-flux image at a stationary solution.
        penalty = 50*(total-1)**2
        if details:
            result['parameter_sum_penalty'] = float(penalty)
            result['objective'] += penalty
            return result
        value, grad = result
        return value+penalty, (grad-float(grad @ q))/total+100*(total-1)

    def _image_value_gradient(self, q, details=False):
        model = (self.fourier @ q).reshape(-1, self.shape[-1])
        if np.any(abs(model) < 1e-14): raise ValueError('model visibility at numerical zero; change initial image')
        coefficients = np.zeros(model.shape, complex)
        chisq = 0.
        for index, cell in enumerate(self.cells):
            values = model[index]
            for name, matrix, observed, factor in cell:
                if factor is None: continue
                predicted = matrix  @  (np.angle(values) if name == 'phase' else np.log(abs(values)))
                residual = predicted-observed
                if name == 'phase' and self.phase_loss == 'circular':
                    sine, cosine = np.sin(residual), 1-np.cos(residual)
                    ps, pc = cho_solve(factor, sine), cho_solve(factor, cosine)
                    chisq += float(sine @ ps+cosine @ pc)
                    precision_residual = np.cos(residual)*ps+np.sin(residual)*pc
                else:
                    if name == 'phase': residual = wrap_phase(residual)
                    precision_residual = cho_solve(factor, residual)
                    chisq += float(residual @ precision_residual)
                coefficients[index] += (matrix.T @ precision_residual) * (-1j if name == 'phase' else 1)
        data_loss = .5*chisq/self.count
        grad = np.real((coefficients/model).ravel() @ self.fourier)/self.count
        log_ratio = np.log(np.maximum(q, 1e-300)/self.prior)
        entropy_loss = self.entropy*float(q @ log_ratio)
        grad += self.entropy*(log_ratio+1)
        image = q.reshape(self.pixels, self.pixels)
        dy, dx = np.diff(image, axis=0), np.diff(image, axis=1)
        tsv_loss = self.tsv*q.size*float(np.sum(dx*dx)+np.sum(dy*dy))
        smooth_grad = np.zeros(image.shape)
        smooth_grad[:-1] -= 2*dy; smooth_grad[1:] += 2*dy
        smooth_grad[:, :-1] -= 2*dx; smooth_grad[:, 1:] += 2*dx
        grad += self.tsv*q.size*smooth_grad.ravel()
        center = self.xy @ q
        centroid_loss = self.centroid*float(center @ center)
        grad += 2*self.centroid*(center @ self.xy)
        objective = data_loss+entropy_loss+tsv_loss+centroid_loss
        if details:
            return {'objective': objective, 'closure_chisq_per_measurement': chisq/self.count,
                    'data_loss': data_loss, 'entropy_loss': entropy_loss, 'tsv_loss': tsv_loss,
                    'centroid_loss': centroid_loss, 'independent_closure_count': self.count,
                    'centroid_arcsec': (center*self.pixel_arcsec*self.pixels/2).tolist()}
        return objective, grad


def fit_closure_image(uvw, visibilities, weights, pairs, *, starts=3, max_iterations=800, seed=21, **settings):
    if not isinstance(starts, int) or not 1 <= starts <= 8: raise ValueError('starts must be 1..8')
    if not isinstance(max_iterations, int) or not 1 <= max_iterations <= 5000: raise ValueError('iterations must be 1..5000')
    objective = ClosureObjective(uvw, visibilities, weights, pairs, **settings)
    rng = np.random.default_rng(seed); runs = []; best = None
    for start in range(starts):
        z = np.log(objective.prior) + (0 if start == 0 else rng.normal(0, .5, objective.prior.size))
        began = time.monotonic()
        objective.phase_loss = 'circular'
        bounds = [(0., None)]*objective.prior.size
        warm = minimize(objective.intensity_value_gradient, softmax(z), method='L-BFGS-B', jac=True, bounds=bounds,
                        options={'maxiter': min(300, max_iterations), 'ftol': 1e-9, 'maxls': 40})
        objective.phase_loss = 'wrapped'
        fit = minimize(objective.intensity_value_gradient, warm.x, method='L-BFGS-B', jac=True, bounds=bounds,
                       options={'maxiter': max_iterations, 'ftol': 1e-11, 'gtol': 1e-7, 'maxls': 40})
        metrics = objective.intensity_value_gradient(fit.x, details=True)
        runs.append({**metrics, 'start': start, 'circular_warmup_iterations': int(warm.nit),
                     'iterations': int(fit.nit), 'optimizer_success': bool(fit.success),
                     'optimizer_message': str(fit.message), 'elapsed_s': time.monotonic()-began})
        if best is None or fit.fun < best.fun: best = fit
    positive = best.x+1e-12
    image = (positive/positive.sum()).reshape(objective.pixels, objective.pixels)
    metrics = objective.intensity_value_gradient(best.x, details=True)
    summary = {**metrics, 'selected_start': int(np.argmin([r['objective'] for r in runs])), 'runs': runs,
               'image_sum': float(image.sum()), 'output_unit': 'relative flux/pixel',
               'absolute_flux_measured': False, 'absolute_position_measured': False,
               'centroid_constraint': 'Weak penalty around display center; actual centroid reported; not measured astrometry',
               'settings': {**settings, 'starts': starts, 'max_iterations': max_iterations, 'seed': seed},
               'noise_model': 'Fixed observed high SNR independent-baseline covariance, full within each closure cell',
               'likelihood_limit': 'Wrapped local Gaussian phase residual; low SNR and phase branch boundaries excluded'}
    return image, summary


def image_closure(path, output, **settings):
    out = Path(output)
    if out.exists(): raise FileExistsError('RML output already exists')
    data = load_visibility_input(path)
    config = deepcopy(data['metadata']['config'])
    settings.setdefault('pixels', min(32, config['image']['pixels']))
    settings.setdefault('pixel_arcsec', config['image']['pixel_arcsec'])
    image, summary = fit_closure_image(data['uvw_lambda'], data['visibilities'], data['weights'], data['pairs'], **settings)
    config['image'].update(pixels=settings['pixels'], pixel_arcsec=settings['pixel_arcsec'])
    import hashlib
    with open(path, 'rb') as stream: summary['input_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
    summary['input_unit'] = data['metadata'].get('visibility_unit', 'Jy')
    out.mkdir(parents=True)
    from .__main__ import write_image_fits
    from astropy.io import fits
    write_image_fits(out/'relative-model.fits', image, config, '1/pixel')
    with fits.open(out/'relative-model.fits', mode='update') as f:
        f[0].header['FLUXREF'] = 'ARBITRARY'; f[0].header['POSREF'] = 'ASSUMED'
        f[0].header['HISTORY'] = 'Closure-only RML; coordinates are an assumed display reference, not measured astrometry.'
        f[0].add_checksum()
    np.save(out/'relative-model.npy', image)
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5, 4)); plot = ax.imshow(image, origin='lower', cmap='inferno')
    ax.set(title='Closure RML: relative flux', xlabel='East pixel', ylabel='North pixel')
    fig.colorbar(plot, ax=ax, label='Relative flux/pixel'); fig.tight_layout()
    fig.savefig(out/'rml.png', dpi=140); plt.close(fig)
    return summary


def main():
    p = argparse.ArgumentParser(description='High SNR closure-only CPU RML reference')
    p.add_argument('--input', required=True); p.add_argument('--output', required=True)
    p.add_argument('--pixels', type=int, default=32); p.add_argument('--pixel-arcsec', type=float, default=16.)
    p.add_argument('--min-snr', type=float, default=10.); p.add_argument('--prior-fwhm-arcsec', type=float, default=240.)
    p.add_argument('--entropy', type=float, default=.01); p.add_argument('--tsv', type=float, default=.0001)
    p.add_argument('--centroid', type=float, default=.1); p.add_argument('--starts', type=int, default=3)
    p.add_argument('--max-iterations', type=int, default=800); p.add_argument('--seed', type=int, default=21)
    a = vars(p.parse_args()); path = a.pop('input'); out = a.pop('output')
    print(json.dumps(image_closure(path, out, **a), indent=2))


if __name__ == '__main__': main()
