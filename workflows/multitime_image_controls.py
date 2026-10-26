"""現存する8時刻VDIF原本を、推定LO/真値LO/理想モデルの三枝で再処理する。"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import numpy as np
from vsora_correlator.closure_pipeline import process_closure_session
from vsora_correlator.aligned import correlate_aligned
from vsora_formats.spectral import load_spectral, save_spectral
from vsora_imaging.synthesis import merge_spectral
from vsora_imaging.rml import image_closure
from vsora_imaging.objective_evaluation import evaluate_closure_image
from vsora_imaging.experiment import compare_relative
from vsora_imaging.assessment import assess_rml_result
from vsora_imaging.closure import form_closures
from vsora_simulator.sky import synthetic_sky
from vsora_simulator.visibility import direct_visibility
from workflows.image_control_validation import idealize_visibility
from workflows.integration_image_validation import RML_SETTINGS, stable_rml_summary
from workflows.rate_acquisition_validation import arrays_identity, scientific_projection, EXPECTED_FAILURES


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def truth_rate_profile(template, rates):
    """真値を入れた対照に、推定baseline・信頼度を混入させない。"""
    rates = np.asarray(rates)
    if (rates.ndim != 1 or len(rates) != len(template['station_indices']) or np.iscomplexobj(rates)
            or not np.issubdtype(rates.dtype, np.number) or not np.isfinite(rates).all()):
        raise ValueError('matching finite real station rates required')
    keys = ('schema_version', 'type', 'station_ids', 'station_indices', 'time_origin_utc',
            'valid_time_range_s', 'sample_cadence_s', 'time_reference_s')
    known = {key: deepcopy(template[key]) for key in keys}
    known.update(station_rates_hz=rates.tolist(), evaluation_only=True, estimated_from_data=False,
                 origin='simulation_truth_rate_control')
    return known


def correlation_projection(path):
    data = load_spectral(path)
    keys = ('config', 'visibility_unit', 'clock_mapping_applied', 'phase_center_corrected', 'time_origin_utc',
            'rate_applied_hz', 'rate_applied_reference_s', 'rate_applied_slopes_hz_per_s', 'rate_profile_type')
    return {'arrays': arrays_identity(data), 'metadata': {k: data['metadata'][k] for k in keys}}


def run(reference, output):
    reference = Path(reference); out = Path(output); out.mkdir(parents=True, exist_ok=False)
    previous = json.loads((reference/'summary.json').read_text())
    assert previous['snapshots'] == 8 and previous['coherent_integration_s'] == 3.
    raw_hashes = {str(p.relative_to(reference)): sha(p) for p in sorted(reference.glob('shot-*/input/*')) if p.is_file()}
    assert len(raw_hashes) == 152
    settings = {**RML_SETTINGS, 'starts': 3}; shots = []; inputs = {'estimated_rate': [], 'truth_rate_control': []}
    for old in previous['shots']:
        index = old['snapshot']; raw = reference/f'shot-{index:02d}/input'; root = out/f'shot-{index:02d}'; root.mkdir()
        observed = json.loads((raw/'observation.json').read_text()); generating = old['generating']
        assert observed['source']['model'] == 'unknown' and 'total_flux_jy' not in observed['source']
        assert observed['observation']['start_utc'] == old['start_utc'] and generating['input_span_s'] == 3.04
        config = deepcopy(observed); config['source'].update(model=generating['model'], total_flux_jy=generating['assumed_flux_jy'])
        candidate_truth = synthetic_sky(config)
        if index == 0: truth = candidate_truth
        else: np.testing.assert_array_equal(truth, candidate_truth)
        failure = None
        try:
            estimated = process_closure_session(raw/'manifest.json', raw/'clock.json', root/'estimated',
                                               pilot_integrations=750, integration_s=3., correlation_only=True)
            actual = root/'estimated'
        except ValueError as error:
            if str(error) not in EXPECTED_FAILURES: raise
            failure = EXPECTED_FAILURES[str(error)]; actual = root/'estimated.partial'
            estimated = json.loads((actual/'pipeline.json').read_text())
        estimated_science = scientific_projection(estimated, actual, None)
        if failure is None: inputs['estimated_rate'].append(actual/'correlation/shard-00000.npz')
        # 失敗した推定結果に依存させず、旧profileから必要な座標規約だけを使う。
        template = json.loads((reference/f'shot-{index:02d}/pipeline/rate-only.json').read_text())
        known = truth_rate_profile(template, generating['station_rates_hz'])
        (root/'truth-rate-only.json').write_text(json.dumps(known, indent=2)+'\n')
        manifest = json.loads((raw/'manifest.json').read_text())
        manifest['observation_config'] = str((raw/'observation.json').resolve())
        manifest['blocks_per_integration'] = round(3.*manifest['sample_rate_hz']/manifest['fft_length'])
        for station in manifest['stations']: station['vdif'] = str((raw/station['vdif']).resolve())
        (root/'truth-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
        correlate_aligned(root/'truth-manifest.json', raw/'clock.json', root/'truth-correlation', 1, .002, root/'truth-rate-only.json')
        oracle = root/'truth-correlation/shard-00000.npz'; inputs['truth_rate_control'].append(oracle)
        shots.append({'snapshot': index, 'start_utc': old['start_utc'], 'generating': generating,
                      'estimated_failure': failure, 'estimated_science': estimated_science,
                      'truth_correlation': correlation_projection(oracle)})
        print(json.dumps({'snapshot': index, 'estimated_failure': failure}), flush=True)
    np.save(out/'truth.npy', truth)
    branches = []; truth_merge = None
    for branch in ('estimated_rate', 'truth_rate_control', 'ideal_model_true_rate_snr_control'):
        root = out/branch; root.mkdir()
        if branch == 'estimated_rate' and len(inputs[branch]) != 8:
            branches.append({'branch': branch, 'state': 'incomplete', 'reason': 'one_or_more_required_snapshots_failed', 'accepted_snapshots': len(inputs[branch])})
            continue
        if branch != 'ideal_model_true_rate_snr_control':
            merge_spectral(inputs[branch], root/'visibility.npz')
            data = load_spectral(root/'visibility.npz')
            if branch == 'truth_rate_control': truth_merge = data
        else:
            data = {k: truth_merge[k].copy() for k in ('pairs', 'times_s', 'frequencies_hz', 'uvw_lambda', 'integration_s')}
            model = direct_visibility(truth_merge['uvw_lambda'], truth, 16.)
            values, weights = idealize_visibility(truth_merge['visibilities'], truth_merge['weights'], model)
            data.update(visibilities=values, weights=weights)
            metadata = {k: deepcopy(truth_merge['metadata'][k]) for k in ('config', 'time_origin_utc')}
            metadata.update(visibility_unit='Jy', evaluation_only=True, weights_are_artificial_snr_transport=True,
                            control='Ideal sky on aligned supplied uv/time geometry; observed true-rate SNR transported; not radiometric calibration')
            save_spectral(root/'visibility.npz', data, metadata)
            data = load_spectral(root/'visibility.npz')
            original_closure = form_closures(truth_merge['visibilities'], truth_merge['weights'], truth_merge['pairs'], 10.)
            artificial_closure = form_closures(values, weights, data['pairs'], 10.)
            for key in ('baseline_valid', 'phase_valid', 'logamp_valid'): np.testing.assert_array_equal(original_closure[key], artificial_closure[key])
            np.testing.assert_allclose(original_closure['baseline_variance'], artificial_closure['baseline_variance'], rtol=1e-12, atol=0.)
        summary = image_closure(root/'visibility.npz', root/'rml', **settings)
        image = np.load(root/'rml/relative-model.npy', allow_pickle=False)
        metrics, _, _, _ = compare_relative(truth, image, 16.)
        candidates = {'truth': truth, 'prior': None, 'fitted': image}
        from vsora_imaging.rml import ClosureObjective
        objective = ClosureObjective(data['uvw_lambda'], data['visibilities'], data['weights'], data['pairs'],
                                     **{k:v for k,v in settings.items() if k not in ('starts','max_iterations','seed')})
        candidates['prior'] = objective.prior.reshape(32, 32)
        evaluations = {k: evaluate_closure_image(data['uvw_lambda'], data['visibilities'], data['weights'], data['pairs'], value,
                       **{k:v for k,v in settings.items() if k not in ('pixels','starts','max_iterations','seed')}) for k,value in candidates.items()}
        science = {'input_arrays': arrays_identity(data), 'rml_summary': stable_rml_summary(summary),
                   'reference_metrics': metrics, 'assessment': assess_rml_result(summary, reference_metrics=metrics),
                   'candidate_objectives': evaluations, 'image_sha256': sha(root/'rml/relative-model.npy')}
        row = {'branch': branch, 'state': 'complete', 'truth_information': 'none_in_current_pipeline' if branch == 'estimated_rate' else 'evaluation_only', 'science': science}
        branches.append(row); (root/'science.json').write_text(json.dumps(science, indent=2, allow_nan=False)+'\n')
        print(json.dumps({'branch': branch, 'nrmse': metrics['registered_nrmse'], 'numerical': science['assessment']['numerical']['state']}), flush=True)
    assert raw_hashes == {str(p.relative_to(reference)): sha(p) for p in sorted(reference.glob('shot-*/input/*')) if p.is_file()}
    result = {'stage': 118, 'state': 'complete', 'shots': shots, 'branches': branches, 'settings': settings,
              'reference_directory': str(reference.resolve()), 'raw_input_sha256_newly_enrolled': raw_hashes,
              'historical_stage028_raw_bytes_proven_unchanged': False,
              'all_input_sha_unchanged_during_this_stage': True,
              'limits': 'Existing eight 3.04s synthetic raw snapshots, 24s useful exposure spread over four hours, not four continuous hours. Historical raw file hashes were not published in 028; current bytes newly enrolled. Known fixed sky/SEFD generator and exact supplied clocks. Noise/gain/LO vary across snapshots. Truth-rate and ideal-sky/SNR transport are evaluation-only controls, not unknown observation recovery or a noise-only intervention. Local optimizer and high-SNR closure approximation unchanged; no real receiver or GPU/full-night validation.'}
    (out/'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--reference', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); run(args.reference, args.output)
