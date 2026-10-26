"""疎なuv・補正・雑音を評価専用の二つの対照で切り分ける。"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import numpy as np
from vsora_correlator.aligned import correlate_aligned
from vsora_formats.spectral import load_spectral, save_spectral
from vsora_simulator.sky import synthetic_sky
from vsora_simulator.visibility import direct_visibility
from vsora_imaging.closure import form_closures, extract_closures
from vsora_imaging.rml import image_closure
from vsora_imaging.experiment import compare_relative
from vsora_imaging.assessment import assess_rml_result
from workflows.rate_acquisition_validation import arrays_identity
from workflows.integration_image_validation import RML_SETTINGS, stable_rml_summary


def idealize_visibility(observed, weights, model):
    """理想visibilityへ置換しSNRを保つ。物理的なJy較正ではない。"""
    v, w, m = (np.asarray(x) for x in (observed, weights, model))
    if (v.ndim != 3 or w.shape != v.shape or m.shape != v.shape
            or not np.iscomplexobj(v) or not np.iscomplexobj(m) or np.iscomplexobj(w)
            or not np.issubdtype(w.dtype, np.number) or any(not np.isfinite(x).all() for x in (v, w, m)) or np.any(w < 0)):
        raise ValueError('matching finite complex visibilities and real nonnegative weights required')
    v = np.asarray(v, dtype=np.complex128); w = np.asarray(w, dtype=np.float64)
    m = np.asarray(m, dtype=np.complex128)
    valid = w > 0
    if np.any(valid & (np.abs(m) == 0)): raise ValueError('nonzero model required where weights are positive')
    with np.errstate(over='ignore', under='ignore', invalid='ignore', divide='ignore'):
        ratio = np.zeros_like(w, dtype=float)
        np.divide(np.abs(v), np.abs(m), out=ratio, where=valid)
        transported = w*ratio**2
        before = np.abs(v)*np.sqrt(w); after = np.abs(m)*np.sqrt(transported)
    if (not np.isfinite(transported).all() or not np.isfinite(before).all() or not np.isfinite(after).all()
            or not np.allclose(before, after, rtol=1e-12, atol=0.)):
        raise ValueError('SNR-preserving transport is outside finite numerical range')
    return m.copy(), transported


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(reference, output):
    reference = Path(reference); out = Path(output); out.mkdir(parents=True, exist_ok=False)
    previous = json.loads((reference/'summary.json').read_text()); rows = []; panels = []
    settings = {**RML_SETTINGS, 'starts': 3}
    for seed in (109, 110, 111):
        old = next(row for row in previous['cases'] if row['seed'] == seed and row['integration_s'] == 3.)
        raw = Path(old['raw_directory']); profile = Path(old['profile']); base_path = reference/old['case_directory']/'correlation/shard-00000.npz'
        observed = load_spectral(base_path); config = deepcopy(observed['metadata']['config'])
        assert config['source']['model'] == 'unknown'; config['source'].update(model=old['generating']['model'], total_flux_jy=old['generating']['assumed_flux_jy'])
        truth = synthetic_sky(config)
        for branch in ('estimated_rate', 'truth_rate_control', 'ideal_model_observed_snr_control'):
            case = f'seed{seed}_{branch}'; root = out/case; root.mkdir(); used = 'none'; mask_preserved = None
            if branch == 'estimated_rate':
                spectrum = base_path; used_profile = profile
            elif branch == 'truth_rate_control':
                template = json.loads(profile.read_text())
                known = {key: template[key] for key in ('schema_version', 'type', 'station_ids', 'station_indices', 'time_origin_utc',
                    'valid_time_range_s', 'sample_cadence_s', 'time_reference_s')}
                known.update(station_rates_hz=old['generating']['station_rates_hz'], evaluation_only=True,
                             estimated_from_data=False, origin='simulation_truth_rate_control', original_estimated_profile_sha256=sha(profile))
                used_profile = root/'truth-rate-only.json'; used_profile.write_text(json.dumps(known, indent=2)+'\n')
                correlate_aligned(old['manifest'], raw/'clock.json', root/'correlation', 1, .002, used_profile)
                spectrum = root/'correlation/shard-00000.npz'; used = 'true_station_rates_for_evaluation_only'
            else:
                model = direct_visibility(observed['uvw_lambda'], truth, 16.)
                values, weights = idealize_visibility(observed['visibilities'], observed['weights'], model)
                data = {key: observed[key].copy() for key in ('pairs', 'times_s', 'frequencies_hz', 'uvw_lambda', 'integration_s')}
                data.update(visibilities=values, weights=weights)
                a = form_closures(observed['visibilities'], observed['weights'], observed['pairs'], 10.)
                b = form_closures(values, weights, observed['pairs'], 10.)
                for key in ('baseline_valid', 'phase_valid', 'logamp_valid'): np.testing.assert_array_equal(a[key], b[key])
                np.testing.assert_allclose(a['baseline_variance'], b['baseline_variance'], rtol=1e-12, atol=0.)
                metadata = {'schema_version': 1, 'config': deepcopy(observed['metadata']['config']),
                    'time_origin_utc': observed['metadata']['time_origin_utc'],
                    'visibility_unit': 'Jy', 'evaluation_only': True, 'weights_are_artificial_snr_transport': True,
                    'control': 'Ideal forward model with artificially transported observed SNR; not radiometric calibration',
                    'original_observed_sha256': sha(base_path)}
                spectrum = root/'ideal-visibility.npz'; save_spectral(spectrum, data, metadata)
                used_profile = profile; used = 'true_sky_forward_model_for_evaluation_only'; mask_preserved = True
            data = load_spectral(spectrum); closure = extract_closures(spectrum, root/'closures.npz', min_snr=10.)
            failure = None; summary = metrics = image_sha = None
            try: summary = image_closure(spectrum, root/'rml', **settings)
            except ValueError as exc:
                if str(exc) != 'no high SNR independent closure measurements': raise
                failure = 'no_high_snr_independent_closures'
            if summary is not None:
                image = np.load(root/'rml/relative-model.npy'); metrics, a, b, registered = compare_relative(truth, image, 16.)
                image_sha = sha(root/'rml/relative-model.npy'); panels.append((seed, branch, a, registered))
                if branch == 'estimated_rate':
                    assert stable_rml_summary(summary['runs'][0]) == old['science']['rml_summary']['runs'][0]
            science = {'correlation_arrays': arrays_identity(data), 'closures': closure, 'rml_failure_code': failure,
                       'rml_summary': stable_rml_summary(summary), 'assessment': assess_rml_result(summary,
                           processing_state='complete' if summary is not None else 'incomplete', reference_metrics=metrics),
                       'reference_metrics': metrics, 'image_npy_sha256': image_sha,
                       'observed_snr_masks_and_approx_variance_preserved': mask_preserved}
            row = {'case': case, 'seed': seed, 'branch': branch, 'truth_information_used': used,
                   'raw_directory': str(raw.resolve()), 'input_sha256': old['input_sha256'],
                   'original_profile': str(profile.resolve()), 'original_profile_sha256': old['profile_sha256'],
                   'used_profile': str(used_profile.resolve()), 'used_profile_sha256': sha(used_profile),
                   'base_spectrum': str(base_path.resolve()), 'base_spectrum_sha256': sha(base_path),
                   'manifest': old['manifest'], 'spectrum': str(spectrum.resolve()),
                   'generating': old['generating'], 'science': science}
            rows.append(row); (root/'science.json').write_text(json.dumps(science, indent=2, allow_nan=False)+'\n')
            (out/'progress.json').write_text(json.dumps(rows, indent=2, allow_nan=False)+'\n')
            assert sha(profile) == old['profile_sha256'] and old['input_sha256'] == {p.name: sha(p) for p in raw.iterdir() if p.is_file()}
            print(json.dumps({'case': case, 'truth_information': used, 'numerical': science['assessment']['numerical']['state'],
                              'selected_start': science['assessment']['numerical']['selected_start'],
                              'registered_nrmse': science['assessment']['reference_fidelity']['registered_nrmse']}), flush=True)
    result = {'type': 'fixed_snapshot_image_controls', 'cases': rows, 'rml_settings': settings,
              'limits': 'Fixed three noisy observations and one snapshot uv per seed. Truth-rate and ideal-model branches are evaluation controls, not unknown-data recovery. Ideal model removes noise and forward approximations while retaining observed SNR/masks and approximate baseline variance, not a noise-only intervention. Three local starts do not guarantee a global optimum. Prior, likelihood and thresholds unchanged.'}
    (out/'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    if panels:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(3, 4, figsize=(12, 9))
        branches = ('estimated_rate', 'truth_rate_control', 'ideal_model_observed_snr_control')
        for axis_row, seed in zip(axes, (109, 110, 111)):
            matches = [panel for panel in panels if panel[0] == seed]
            if not matches: continue
            truth = matches[0][2]; axis_row[0].imshow(truth, origin='lower', cmap='inferno', vmin=0, vmax=truth.max())
            axis_row[0].set_title('Truth'); axis_row[0].set_ylabel(f'seed{seed}')
            for axis, branch in zip(axis_row[1:], branches):
                found = [panel for panel in matches if panel[1] == branch]
                if found: axis.imshow(found[0][3], origin='lower', cmap='inferno', vmin=0, vmax=truth.max())
                axis.set_title(branch.replace('_', '\n'), fontsize=9)
            for axis in axis_row: axis.set_xticks([]); axis.set_yticks([])
        fig.suptitle('Evaluation controls, three local starts. Display crops; metrics use full support and 110 arcsec common beam')
        fig.tight_layout(); fig.savefig(out/'comparison.png', dpi=125); plt.close(fig)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--reference', required=True); p.add_argument('--output', required=True)
    a = p.parse_args(); run(a.reference, a.output)
