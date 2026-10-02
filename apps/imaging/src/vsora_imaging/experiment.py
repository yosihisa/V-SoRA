"""Sparse short-exposure closure simulation, distinct from observation span."""
from copy import deepcopy
import json
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter, shift
from scipy.signal import fftconvolve
from scipy.optimize import minimize
import astropy.units as u
from astropy.time import Time
from vsora_observation.geometry import geometry_at_times
from vsora_simulator.sky import synthetic_sky
from vsora_simulator.visibility import direct_visibility
from vsora_formats.spectral import save_spectral
from .rml import image_closure, ClosureObjective


def compare_relative(truth, recovered, pixel_arcsec, common_beam_arcsec=110.):
    # Flux normalization is the explicitly chosen closure gauge, not Jy calibration.
    truth = truth/truth.sum(); recovered = recovered/recovered.sum()
    sigma = common_beam_arcsec/(np.sqrt(8*np.log(2))*pixel_arcsec)
    a, b = gaussian_filter(truth, sigma, mode='constant'), gaussian_filter(recovered, sigma, mode='constant')
    correlation = fftconvolve(a, b[::-1, ::-1], mode='full')
    peak = np.array(np.unravel_index(np.argmax(correlation), correlation.shape))-(np.array(a.shape)-1)
    def error(offset): return float(np.sum((shift(b, offset, order=1, mode='constant')-a)**2))
    fit = minimize(error, peak.astype(float), method='Powell', bounds=[(v-1., v+1.) for v in peak], options={'xtol':1e-5})
    registered = shift(b, fit.x, order=1, mode='constant')
    metrics = {'raw_nrmse': float(np.linalg.norm(b-a)/np.linalg.norm(a)),
               'registered_nrmse': float(np.linalg.norm(registered-a)/np.linalg.norm(a)),
               'registered_correlation': float(np.corrcoef(a.ravel(), registered.ravel())[0, 1]),
               'registration_shift_yx_arcsec': (fit.x*pixel_arcsec).tolist(),
               'common_beam_arcsec': common_beam_arcsec,
               'comparison': 'Unit-flux gauge, Gaussian common beam, explicit translation only; no calibrated Jy or astrometry'}
    return metrics, a, b, registered


def run_simulation(config, output, snapshots=16, starts=3, max_iterations=800,
                   prior_fwhm_arcsec=240., entropy=.01, tsv=.0001):
    out = Path(output)
    if out.exists(): raise FileExistsError('output already exists')
    if not isinstance(snapshots, int) or not 2 <= snapshots <= 64: raise ValueError('snapshots must be 2..64')
    c = deepcopy(config)
    from vsora_observation import validate_config
    c = validate_config(c)
    c['image']['pixels'] = 32
    duration = c['observation']['duration_s']; exposure = c['observation']['integration_s']
    if not .1 <= exposure <= 3: raise ValueError('closure exposure must be 0.1..3 seconds')
    offsets = (np.arange(snapshots)+.5)*duration/snapshots
    geometry = geometry_at_times(c, Time(c['observation']['start_utc'])+offsets*u.s)
    v = direct_visibility(geometry['uvw_lambda'], synthetic_sky(c), c['image']['pixel_arcsec'])[:, None]
    p = geometry['pairs']; rng = np.random.default_rng(c['seed'])
    sefd = np.array([s['sefd_jy'] for s in c['stations']])
    sigma = np.sqrt(sefd[p[:, 0]]*sefd[p[:, 1]]/(2*c['observation']['bandwidth_hz']*exposure))/c['noise']['efficiency']
    if c['noise']['enabled']: v += sigma[None, None, :]*(rng.normal(size=v.shape)+1j*rng.normal(size=v.shape))
    gains = np.exp(rng.uniform(-1.8, 1.8, (len(v), 1, len(c['stations'])))
                   +1j*rng.uniform(-np.pi, np.pi, (len(v), 1, len(c['stations']))))
    pairgain = gains[..., p[:, 0]]*gains[..., p[:, 1]].conj()
    weights = np.broadcast_to(1/sigma**2, v.shape).copy()
    measured = v*pairgain; measured_weights = weights/abs(pairgain)**2
    data = {'visibilities': measured, 'weights': measured_weights, 'pairs': p,
            'uvw_lambda': geometry['uvw_lambda'][:, None],
            'times_s': (geometry['times_mjd']-Time(c['observation']['start_utc']).mjd)*86400,
            'frequencies_hz': np.array([c['observation']['frequency_hz']]),
            'integration_s': np.full((len(v), len(p)), exposure)}
    out.mkdir(parents=True)
    metadata = {'config': c, 'visibility_unit': 'ADC^2', 'time_origin_utc': c['observation']['start_utc'],
                'simulation': 'Sparse independent midpoint visibilities; station gains constant within each short exposure; LO corrected',
                'observation_span_s': duration, 'recorded_exposure_per_station_s': len(v)*exposure}
    save_spectral(out/'uncalibrated.npz', data, metadata)
    settings = dict(pixels=32, pixel_arcsec=c['image']['pixel_arcsec'], starts=starts, max_iterations=max_iterations,
                    prior_fwhm_arcsec=prior_fwhm_arcsec, entropy=entropy, tsv=tsv, min_snr=10.)
    rml = image_closure(out/'uncalibrated.npz', out/'rml', **settings)
    truth = synthetic_sky(c); model = np.load(out/'rml/relative-model.npy')
    metrics, a, b, registered = compare_relative(truth, model, c['image']['pixel_arcsec'])
    # Same candidate image must have the same objective under arbitrary gains.
    objective_settings = {k: val for k, val in settings.items() if k not in ('starts', 'max_iterations')}
    before = ClosureObjective(data['uvw_lambda'], v, weights, p, **objective_settings)
    after = ClosureObjective(data['uvw_lambda'], measured, measured_weights, p, **objective_settings)
    x = np.maximum(model.ravel(), 1e-12)
    oa, ga = before.intensity_value_gradient(x); ob, gb = after.intensity_value_gradient(x)
    invariance = {'objective_absolute_difference': abs(oa-ob), 'gradient_max_absolute_difference': float(abs(ga-gb).max())}
    summary = {'type': 'closure_rml_simulation', 'config': c, 'snapshots_retained': len(v),
               'observation_span_s': duration, 'coherent_integration_s': exposure,
               'recorded_exposure_per_station_s': len(v)*exposure, 'rml': rml, 'metrics': metrics,
               'gain_invariance': invariance, 'geometry': {k:geometry[k] for k in ['model','eop_status','eop_warnings']},
               'limits': 'Synthetic visibility, not IQ/VDIF; single RF channel, assumed SEFD, sparse exposures, supplied noise weights; LO already corrected; truth excluded from prior'}
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    np.save(out/'truth-relative.npy', truth/truth.sum())
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.3))
    for ax, title, value in zip(axes, ['Truth: relative','RML: raw','RML: 110 arcsec','RML: translated'], [a, model, b, registered]):
        ax.imshow(value, origin='lower', cmap='inferno'); ax.set_title(title)
    fig.tight_layout(); fig.savefig(out/'comparison.png', dpi=140); plt.close(fig)
    return summary
