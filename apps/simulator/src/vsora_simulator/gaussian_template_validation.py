"""Two supplied sky/receiver covariance models: voltage likelihood reference.

This study knows station phases, powers and SEFD. It does not estimate them,
define a closure image likelihood, or claim actual Cas A imaging success.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from vsora_correlator.gaussian_likelihood import (
    gaussian_log_likelihood_ratio, sample_second_moment,
)
from vsora_observation.reference import reference_path
from .casa_window_symmetry import _config, _known_model
from .known_template_validation import empirical_auc, error_rate_summary
from .sensitivity import dish_area, sefd_from_area


def known_model_error_summary(errors, trials):
    """Binomial interval conditional on fixed supplied models, no training."""
    value = error_rate_summary(errors, trials)
    level = value.pop('conditional_fixed_training_binomial_confidence_level')
    value['conditional_fixed_models_binomial_confidence_level'] = level
    value['training_used'] = False
    value['actual_observation_confidence_interval'] = False
    return value


def case_plan(profile='full'):
    if profile not in ('full', 'smoke'):
        raise ValueError('full or smoke profile required')
    large = float(sefd_from_area(100., dish_area(1., .6)))
    rows = [(m, s, s, s, False) for m in (512, 19200) for s in (1000., 10000., large)]
    rows += [(19200, 1000., 10000., 1000., False),
             (19200, 10000., 1000., 10000., False), (512, 1000., 1000., 1000., True)]
    plan = []
    for index, (m, assumed, point, casa, zero) in enumerate(rows):
        plan.append({'case_id': f'g{index:02d}', 'profile': 'full', 'modes': m,
            'assumed_receiver_sefd_jy': assumed, 'point_generated_sefd_jy': point,
            'casa_generated_sefd_jy': casa, 'zero_sky_control': zero,
            'receiver_model_matches_generation': assumed == point == casa,
            'test_per_label': 512, 'seed': 101000+index,
            'maximum_baseline_m': 600., 'formal_mc_precision': True})
    if profile == 'smoke':
        plan = [dict(plan[i], case_id=f'smoke-{i}', profile='smoke', modes=16,
                     test_per_label=16, seed=plan[i]['seed']+10000,
                     formal_mc_precision=False) for i in (0, 6, 8)]
    return plan


def _matrix_json(a):
    return np.stack((a.real, a.imag), axis=-1).tolist()


def _draw(mode, sefd, windows, modes, seed, role, c0, c1):
    covariance, root, _, _ = _known_model(mode, 600., (float(sefd),)*8)
    rng = np.random.default_rng(np.random.SeedSequence([seed, role]))
    gain_rng = np.random.default_rng(np.random.SeedSequence([seed, role, 99]))
    batch = min(16, max(1, 1000000//(modes*8)))
    scores = []; direct_errors = []; gain_errors = []; predictions_equal = True
    for start in range(0, windows, batch):
        count = min(batch, windows-start); shape = (count, modes, 8)
        z = (rng.normal(size=shape)+1j*rng.normal(size=shape))/np.sqrt(2)
        x = z @ root.T
        for local, voltage in enumerate(x):
            moment = sample_second_moment(voltage)
            score = gaussian_log_likelihood_ratio(c0, c1, moment, modes)
            if not np.isfinite(score):
                raise ValueError('nonfinite likelihood score')
            scores.append(score)
            if start+local < 2:
                # Independent raw-voltage quadratic forms. No S-based API.
                solved0 = np.linalg.solve(c0, voltage.T)
                solved1 = np.linalg.solve(c1, voltage.T)
                direct = modes*(np.linalg.slogdet(c0)[1]-np.linalg.slogdet(c1)[1])
                direct += float(np.sum((voltage.conj().T*(solved0-solved1)).real))
                if not np.isclose(score, direct, rtol=2e-10, atol=2e-7):
                    raise RuntimeError('raw-voltage likelihood reference mismatch')
                direct_errors.append(abs(score-direct))
                gain = np.exp(gain_rng.uniform(-.8,.8,size=8)+1j*gain_rng.uniform(-np.pi,np.pi,size=8))
                changed = sample_second_moment(voltage*gain)
                transform = lambda c: gain[:,None]*c*gain.conj()[None,:]
                transported = gaussian_log_likelihood_ratio(transform(c0),transform(c1),changed,modes)
                if not np.isclose(score, transported, rtol=2e-10, atol=2e-7):
                    raise RuntimeError('known-gain likelihood transport mismatch')
                gain_errors.append(abs(score-transported))
                predictions_equal = predictions_equal and (score > 0) == (transported > 0)
    return np.asarray(scores), {
        'station_covariance_jy_real_imag': _matrix_json(covariance),
        'direct_voltage_checks': len(direct_errors), 'known_gain_checks': len(gain_errors),
        'maximum_direct_voltage_likelihood_abs_difference': max(direct_errors),
        'maximum_known_gain_likelihood_abs_difference': max(gain_errors),
        'known_gain_predictions_identical': bool(predictions_equal),
        'unknown_station_gain_estimated': False,
        'maximum_generated_array_complex_values': min(batch,windows)*modes*8,
        'rng_seed_sequence': [seed,role], 'independent_gaussian_modes_assumed': True,
        'same_modes_used_for_all_stations': True,
        'expected_log_likelihood_ratio_per_window': gaussian_log_likelihood_ratio(c0,c1,covariance,modes),
    }


def experiment(case):
    if not isinstance(case, dict):
        raise ValueError('unmodified fixed case dictionary required')
    supplied = json.dumps(case, sort_keys=True, allow_nan=False)
    if not any(supplied == json.dumps(c,sort_keys=True,allow_nan=False) for c in case_plan(case.get('profile'))):
        raise ValueError('unmodified fixed case dictionary required')
    mode0, mode1 = ('zero','zero') if case['zero_sky_control'] else ('point','casa')
    sefd = case['assumed_receiver_sefd_jy']; m = case['modes']; n = case['test_per_label']
    c0 = _known_model(mode0,600.,(sefd,)*8)[0]
    c1 = _known_model(mode1,600.,(sefd,)*8)[0]
    point, pc = _draw(mode0,case['point_generated_sefd_jy'],n,m,case['seed'],0,c0,c1)
    casa, cc = _draw(mode1,case['casa_generated_sefd_jy'],n,m,case['seed'],1,c0,c1)
    false = known_model_error_summary(int(np.count_nonzero(point > 0)),n)
    missed = known_model_error_summary(int(np.count_nonzero(casa <= 0)),n)
    zero_ok = not case['zero_sky_control'] or (np.array_equal(point,np.zeros(n)) and np.array_equal(casa,np.zeros(n)))
    ok = zero_ok and pc['known_gain_predictions_identical'] and cc['known_gain_predictions_identical']
    return {**case, 'state': 'complete' if ok else 'failed_validation',
        'candidate0_mode': mode0, 'candidate1_mode': mode1,
        'candidate0_covariance_jy_real_imag': _matrix_json(c0),
        'candidate1_covariance_jy_real_imag': _matrix_json(c1),
        'point_test_log_likelihood_ratios': point.tolist(),
        'casa_test_log_likelihood_ratios': casa.tolist(),
        'false_casa_on_point': false, 'missed_casa': missed,
        'balanced_accuracy': 1-(false['fraction']+missed['fraction'])/2,
        'empirical_auroc': empirical_auc(point,casa),
        'auc_pairs_treated_as_independent': False,
        'point_generation': pc, 'casa_generation': cc,
        'threshold_score': 0., 'threshold_ties_assigned_to': 'point',
        'training_used': False, 'test_used_for_threshold_or_model_selection': False,
        'zero_control_all_scores_exactly_zero': bool(zero_ok) if case['zero_sky_control'] else None,
        'station_phases_powers_and_sefd_supplied': True, 'unknown_gain_sefd_lo_estimated': False,
        'actual_fft_independence_verified': False, 'image_likelihood_defined': False,
        'image_reconstructed': False, 'real_hardware_validation_performed': False,
        'production_rml_noise_model_changed': False}


def run(output, profile='full', progress=None):
    plan = case_plan(profile)
    out = Path(output); out.mkdir(parents=True,exist_ok=False); (out/'cases').mkdir()
    cases = []
    for index, case in enumerate(plan):
        if progress:progress(index,len(plan),case['case_id'])
        q = experiment(case)
        (out/'cases'/f"{case['case_id']}.json").write_text(json.dumps(q,indent=2,allow_nan=False)+'\n')
        if q['state'] != 'complete':
            raise RuntimeError('known covariance reference checks failed')
        cases.append(q)
    cfg = _config()
    q = {'state': 'complete', 'type': 'known_covariance_template_discrimination',
        'profile': profile, 'cases': cases, 'independent_voltage_windows_generated': sum(2*c['test_per_label'] for c in cases),
        'assumed_frequency_hz': 1.42e9, 'maximum_baseline_m': 600., 'assumed_source_total_flux_jy': 1000.,
        'zero_sky_control_source_flux_jy': 0., 'reference': cfg['reference'],
        'fixed_geometry': next(g for g in cfg['geometry'] if g['maximum_baseline_m'] == 600.),
        'configuration_asset_sha256': hashlib.sha256(reference_path('known-casa-window-symmetry.json').read_bytes()).hexdigest(),
        'template_fits_sha256': hashlib.sha256(reference_path().read_bytes()).hexdigest(),
        'training_used': False, 'station_phases_powers_and_sefd_supplied': True,
        'unknown_gain_sefd_lo_estimated': False, 'mode_count_is_adc_fft_measurement': False,
        'image_likelihood_defined': False, 'general_sky_reconstructed': False,
        'actual_hardware_data': False, 'production_rml_noise_model_changed': False,
        'software_smoke_only': profile == 'smoke',
        'scope': 'Two supplied sky/receiver covariances only. No unknown calibration, closure likelihood, '
                 'actual source detection, image confidence, observing time guarantee or hardware feasibility bound.'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n')
    plot(q,out/'known-covariance-template.png')
    return q


def plot(summary, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cases = summary['cases']; x = np.arange(len(cases))
    fig, axes = plt.subplots(2,1,figsize=(10,7),sharex=True)
    for key, label in [('balanced_accuracy','Balanced accuracy'),('empirical_auroc','Empirical AUROC')]:
        axes[0].plot(x,[c[key] for c in cases],'o-',label=label)
    axes[0].axhline(.5,color='grey',linestyle='--'); axes[0].set_ylabel('Metric'); axes[0].legend()
    for key,offset,label in [('false_casa_on_point',-.08,'False Cas A on point'),('missed_casa',.08,'Missed Cas A')]:
        fractions=np.array([c[key]['fraction'] for c in cases]); ci=np.array([c[key]['clopper_pearson_interval'] for c in cases])
        axes[1].errorbar(x+offset,fractions,yerr=[fractions-ci[:,0],ci[:,1]-fractions],fmt='o',capsize=4,label=label)
    axes[1].legend();axes[1].set(xticks=x,xticklabels=[c['case_id'] for c in cases],
        xlabel='Fixed supplied-model condition',ylabel='Conditional error rate; 95% interval')
    for ax in axes:ax.set_ylim(-.05,1.05);ax.grid(alpha=.25)
    fig.suptitle('Known covariance reference; no unknown calibration or image confidence')
    fig.tight_layout();fig.savefig(path,dpi=140);plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--profile',choices=('full','smoke'),default='full');a=p.parse_args()
    q=run(a.output,a.profile,lambda i,n,label:print(f'condition {i+1}/{n}: {label}',flush=True))
    print(json.dumps({'state':q['state'],'cases':len(q['cases'])}))


if __name__ == '__main__':main()
