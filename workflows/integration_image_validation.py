"""同じ取得済みrateと原本のまま、最終積分と画像を比較する。"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import numpy as np
from vsora_correlator.aligned import correlate_aligned
from vsora_formats.spectral import load_spectral
from vsora_imaging.closure import extract_closures
from vsora_imaging.rml import image_closure
from vsora_imaging.assessment import assess_rml_result
from vsora_imaging.experiment import compare_relative
from vsora_simulator.sky import synthetic_sky
from workflows.rate_acquisition_validation import arrays_identity


RML_SETTINGS = {'pixels': 32, 'pixel_arcsec': 16., 'min_snr': 10., 'prior_fwhm_arcsec': 240.,
                'entropy': .01, 'tsv': .0001, 'centroid': .1, 'starts': 1, 'max_iterations': 2000, 'seed': 21}


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def stable_rml_summary(value):
    """数値・設定は残し、経過秒と入力archive来歴SHAだけを分ける。"""
    if isinstance(value, dict):
        return {key: stable_rml_summary(item) for key, item in value.items() if key not in ('elapsed_s', 'input_sha256')}
    if isinstance(value, list): return [stable_rml_summary(item) for item in value]
    return value


def run(reference, seed109_truth, output):
    reference = Path(reference); out = Path(output); out.mkdir(parents=True, exist_ok=False)
    source = json.loads((reference/'summary.json').read_text()); rows = []; panels = []
    for seed in (109, 110, 111):
        raw = reference/f'seed-{seed}/input'; previous = reference/f'seed-{seed}/pilot-750/pipeline'
        generating = next(row['generating'] for row in source['cases'] if row['seed'] == seed)
        profile = previous/'rate-only.json'; identity = {p.name: sha(p) for p in sorted(raw.iterdir()) if p.is_file()}
        profile_sha = sha(profile); observed = json.loads((raw/'observation.json').read_text())
        assert observed['source']['model'] == 'unknown' and 'total_flux_jy' not in observed['source']
        evaluation_config = deepcopy(observed)
        evaluation_config['source'].update(model=generating['model'], total_flux_jy=generating['assumed_flux_jy'])
        truth = synthetic_sky(evaluation_config)
        np.testing.assert_array_equal(truth, np.load(seed109_truth))
        for duration in (.3, 1., 3.):
            case = f'seed{seed}_t{duration:g}'; root = out/case; root.mkdir()
            manifest = json.loads((raw/'manifest.json').read_text())
            manifest['observation_config'] = str((raw/'observation.json').resolve())
            manifest['blocks_per_integration'] = round(duration*manifest['sample_rate_hz']/manifest['fft_length'])
            for station in manifest['stations']: station['vdif'] = str((raw/station['vdif']).resolve())
            path = root/'manifest.json'; path.write_text(json.dumps(manifest, indent=2)+'\n')
            correlate_aligned(path, raw/'clock.json', root/'correlation', 1, .002, profile)
            spectrum = root/'correlation/shard-00000.npz'; data = load_spectral(spectrum)
            closure = extract_closures(spectrum, root/'closures.npz', min_snr=10.)
            if duration == .3:
                old = load_spectral(previous/'correlation/shard-00000.npz'); assert set(data) == set(old)
                for key in data:
                    if key != 'metadata': np.testing.assert_array_equal(data[key], old[key])
            failure = None; summary = None; metrics = None; image_sha = None
            try:
                summary = image_closure(spectrum, root/'rml', **RML_SETTINGS)
            except ValueError as exc:
                if str(exc) != 'no high SNR independent closure measurements': raise
                failure = 'no_high_snr_independent_closures'; assert not (root/'rml').exists()
            if summary is not None:
                recovered = np.load(root/'rml/relative-model.npy')
                metrics, a, b, registered = compare_relative(truth, recovered, 16.)
                image_sha = sha(root/'rml/relative-model.npy'); panels.append((case, a, b, registered))
            assessment = assess_rml_result(summary, processing_state='complete' if summary is not None else 'incomplete', reference_metrics=metrics)
            science = {'correlation_arrays': arrays_identity(data), 'closures': closure,
                       'rml_failure_code': failure, 'rml_summary': stable_rml_summary(summary),
                       'assessment': assessment, 'reference_metrics': metrics, 'recovered_npy_sha256': image_sha}
            row = {'case': case, 'seed': seed, 'integration_s': duration,
                   'raw_directory': str(raw.resolve()), 'profile': str(profile.resolve()),
                   'input_sha256': identity, 'profile_sha256': profile_sha,
                   'manifest': str(path.resolve()), 'case_directory': case,
                   'generating': generating, 'truth_used_by_estimator': False, 'science': science}
            rows.append(row); (root/'science.json').write_text(json.dumps(science, indent=2, allow_nan=False)+'\n')
            (out/'progress.json').write_text(json.dumps(rows, indent=2, allow_nan=False)+'\n')
            assert identity == {p.name: sha(p) for p in sorted(raw.iterdir()) if p.is_file()} and sha(profile) == profile_sha
            print(json.dumps({'case': case, 'closures': closure, 'rml_failure': failure,
                              'numerical_state': assessment['numerical']['state'],
                              'registered_nrmse': assessment['reference_fidelity']['registered_nrmse']}), flush=True)
    result = {'type': 'same_rate_final_integration_imaging', 'fixed_seeds': [109, 110, 111],
              'integrations_s': [.3, 1., 3.], 'rml_settings': RML_SETTINGS, 'cases': rows,
              'truth_npy_sha256': sha(seed109_truth), 'all_generated_truth_arrays_identical_to_seed109_saved_array': True,
              'limits': 'Fixed simulated 3.04s inputs, same three-second acquired rate profile per seed. Final durations overlap, not independent replicates. Exact supplied sample clocks/scales, constant gains and LO, snapshot uv only, high-SNR likelihood unchanged. Truth only used after estimation. No real observation, low-SNR likelihood, absolute flux/astrometry or global optimizer guarantee.'}
    (out/'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    if panels:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(len(panels), 3, figsize=(9, 2.6*len(panels)), squeeze=False)
        for axes_row, (label, a, b, registered) in zip(axes, panels):
            for axis, title, array in zip(axes_row, ('Truth', 'RML', 'Translated RML'), (a, b, registered)):
                axis.imshow(array, origin='lower', cmap='inferno', vmin=0, vmax=a.max())
                axis.set_title(title); axis.set_xticks([]); axis.set_yticks([])
            axes_row[0].set_ylabel(label)
        fig.suptitle('Display crops; comparisons use full support, unit flux and 110 arcsec common beam')
        fig.tight_layout(); fig.savefig(out/'comparison.png', dpi=120); plt.close(fig)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--reference', required=True)
    p.add_argument('--seed109-truth', required=True); p.add_argument('--output', required=True)
    a = p.parse_args(); run(a.reference, a.seed109_truth, a.output)
