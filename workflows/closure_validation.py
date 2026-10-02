"""Independent algebra/noise checks and actual FX integration-loss experiment."""
from itertools import combinations
import argparse
import json
from pathlib import Path
import numpy as np
from vsora_imaging.closure import form_closures, independent_closures, wrap_phase
from vsora_correlator.fx import fx_correlate, remove_fringe_rate


def run(output):
    out = Path(output)
    if out.exists(): raise FileExistsError('output already exists')
    out.mkdir(parents=True)
    rng = np.random.default_rng(20020)
    pairs = np.array(list(combinations(range(4), 2)))
    v = np.exp(1j*rng.uniform(-3, 3, (20, 6))) * rng.uniform(.4, 1.5, (20, 6))
    gain = np.exp(rng.uniform(-2, 2, (20, 4)) + 1j*rng.uniform(-10, 10, (20, 4)))
    pairgain = gain[:, pairs[:, 0]]*gain[:, pairs[:, 1]].conj()
    a = form_closures(v, np.ones(v.shape)*1e6, pairs)
    b = form_closures(v*pairgain, np.ones(v.shape)*1e6/abs(pairgain)**2, pairs)
    invariance = {'phase_max_error_rad': float(np.max(abs(wrap_phase(a['phase']-b['phase'])))),
                  'logamp_max_error': float(np.max(abs(a['logamp']-b['logamp'])))}
    noise_v = 1 + .01*(rng.normal(size=(40000, 6))+1j*rng.normal(size=(40000, 6)))
    noise = form_closures(noise_v, np.ones(noise_v.shape)*1e4, pairs)
    covariance = {}
    for name in ['phase', 'logamp']:
        matrix = noise[name+'_matrix']; expected = matrix@matrix.T*1e-4
        measured = np.cov(noise[name], rowvar=False)
        selected, cov = independent_closures(matrix, np.ones(len(matrix), bool), np.ones(6)*1e-4)
        covariance[name] = {'relative_frobenius_error': float(np.linalg.norm(measured-expected)/np.linalg.norm(expected)),
                            'independent_count': len(selected), 'covariance': cov.tolist()}
    rates = np.array([0., 1.31, -.67, 2.23]); delta = rates[pairs[:, 0]]-rates[pairs[:, 1]]
    analytic = []
    for duration in [.128, .3, 1., 3.]:
        factors = np.sinc(delta*duration)*np.exp(2j*np.pi*delta*duration/2)
        c = form_closures(factors, np.ones(6)*1e12, pairs)
        analytic.append({'integration_s': duration, 'minimum_coherence': float(abs(factors).min()),
                         'maximum_abs_closure_phase_rad': float(abs(c['phase']).max()),
                         'maximum_abs_logcamp_bias': float(abs(c['logamp']).max())})
    fs = 2048000.; duration = .3; ns = int(fs*duration); t = np.arange(ns)/fs
    signal = (rng.normal(size=ns)+1j*rng.normal(size=ns))/np.sqrt(2)
    station_gain = np.array([.4, 3., 1.5, .75])*np.exp(1j*np.array([0., .7, -1.1, 2.]))
    iq = station_gain[:, None]*signal[None, :]*np.exp(2j*np.pi*rates[:, None]*t)
    before = fx_correlate(iq, fs, fft_length=128)
    after = fx_correlate(remove_fringe_rate(iq, fs, rates), fs, fft_length=128)
    # Equal-channel average uses Parseval here; constant station response only.
    raw = before['vis_jy'].mean(axis=0); corrected = after['vis_jy'].mean(axis=0)
    ideal = station_gain[pairs[:, 0]]*station_gain[pairs[:, 1]].conj()*np.mean(abs(signal)**2)
    expectation = np.sinc(delta*duration)*np.exp(2j*np.pi*delta*(duration-1/fs)/2)
    cb = form_closures(raw, np.ones(6)*1e10, pairs)
    ca = form_closures(corrected, np.ones(6)*1e10, pairs)
    iq_metrics = {'sample_rate_hz': fs, 'integration_s': duration, 'samples_per_station': ns,
                  'station_rates_hz': rates.tolist(),
                  'analytic_factor_max_error': float(abs(raw/ideal-expectation).max()),
                  'uncorrected_max_logcamp_bias': float(abs(cb['logamp']).max()),
                  'corrected_max_logcamp_error': float(abs(ca['logamp']).max()),
                  'corrected_max_phase_error_rad': float(abs(ca['phase']).max()),
                  'rate_source': 'Supplied generating rates; blind estimation NOT tested',
                  'signal': 'Strong shared complex Gaussian, no independent receiver noise, constant gain/bandpass'}
    assert invariance['phase_max_error_rad'] < 1e-12 and invariance['logamp_max_error'] < 1e-12
    assert all(c['relative_frobenius_error'] < .03 for c in covariance.values())
    assert iq_metrics['analytic_factor_max_error'] < .005
    assert iq_metrics['corrected_max_logcamp_error'] < 1e-12
    summary = {'type': 'closure_validation', 'station_gain_invariance': invariance,
               'high_snr_covariance': covariance, 'finite_integration_calculation': analytic,
               'actual_iq_fx': iq_metrics,
               'residual_rate_for_at_least_90pct_coherence_hz': {'0.3s': .25/.3, '3s': .25/3},
               'limits': 'High SNR independent baseline Gaussian covariance only; no RTL-SDR/OCXO measurement or RML recovery'}
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))
    x = np.linspace(0, 3, 600)
    for d in delta: axes[0].plot(x, abs(np.sinc(d*x)))
    axes[0].set(xlabel='Integration (s)', ylabel='Coherence fraction', title='Constant LO differences')
    axes[1].bar(np.arange(2)-.15, cb['logamp'], width=.3, label='Before rate correction')
    axes[1].bar(np.arange(2)+.15, ca['logamp'], width=.3, label='After supplied rate correction')
    axes[1].set(xlabel='Closure amplitude choice', ylabel='Log closure amplitude', title='Actual IQ -> FX, 0.3 s')
    axes[1].legend();fig.tight_layout();fig.savefig(out/'closure.png', dpi=140);plt.close(fig)
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True); a = p.parse_args()
    print(json.dumps(run(a.output), indent=2))
