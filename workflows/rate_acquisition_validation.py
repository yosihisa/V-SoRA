"""同じ長いVDIF原本の1/2/3秒pilotを既存の補正相関へ通す。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
from workflows.vdif_synthesis_validation import extended_fixture
from vsora_correlator.closure_pipeline import process_closure_session
from vsora_correlator.rate_graph import diagnose_rate_graph
from vsora_formats.spectral import load_spectral
from vsora_imaging.closure import extract_closures


EXPECTED_FAILURES = {
    'detected rate graph is disconnected; use a longer/stronger pilot or fewer stations': 'rate_graph_disconnected',
    'baseline rate estimates inconsistent with station rates': 'rate_inconsistent',
}


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def arrays_identity(data):
    return {key: {'dtype': value.dtype.str, 'shape': list(value.shape),
                  'sha256': hashlib.sha256(value.tobytes(order='C')).hexdigest()}
            for key, value in data.items() if key != 'metadata'}


def scientific_projection(summary, pipeline, closures):
    """配列と科学項目は全て保持。場所とarchiveの来歴は別に照合する。"""
    pilot = load_spectral(pipeline/'pilot/shard-00000.npz')
    graph = diagnose_rate_graph(pilot)
    fit = None if summary.get('rate_estimate') is None else {
        key: value for key, value in summary['rate_estimate'].items() if key != 'input_sha256'}
    correlation = None; metadata = None
    if summary['state'] == 'complete':
        data = load_spectral(pipeline/'correlation/shard-00000.npz'); correlation = arrays_identity(data)
        metadata = {key: data['metadata'][key] for key in (
            'config', 'visibility_unit', 'clock_mapping_applied', 'phase_center_corrected', 'time_origin_utc',
            'rate_applied_hz', 'rate_applied_reference_s', 'rate_applied_slopes_hz_per_s', 'rate_profile_type')}
    return {'state': summary['state'], 'completed_steps': summary['completed_steps'],
            'graph': graph, 'rate_estimate': fit, 'closures': closures,
            'correlation_arrays': correlation, 'correlation_scientific_metadata': metadata}


def run(output, seed109_input):
    out = Path(output); out.mkdir(parents=True, exist_ok=False); rows = []
    previous = Path(seed109_input)
    for seed in (109, 110, 111):
        root = out/f'seed-{seed}'; root.mkdir()
        if seed == 109:
            generating = json.loads((previous/'generating.json').read_text())
            assert generating['seed'] == seed and generating['input_span_s'] == 3.04 and generating['assumed_sefd_jy'] == 10000.
            original = {p.name: sha(p) for p in (previous/'input').iterdir() if p.is_file()}
            shutil.copytree(previous/'input', root/'input')
            assert original == {p.name: sha(p) for p in (root/'input').iterdir() if p.is_file()}
        else:
            _, _, generating = extended_fixture(root/'input', '2026-10-02T10:00:00Z', seed=seed, sefd_jy=10000., frame_count=1520)
        input_sha = {p.name: sha(p) for p in sorted((root/'input').iterdir()) if p.is_file()}
        observed = json.loads((root/'input/observation.json').read_text())
        assert observed['source']['model'] == 'unknown' and 'total_flux_jy' not in observed['source']
        for count in (250, 500, 750):
            case_root = root/f'pilot-{count}'; case_root.mkdir(); failure = None
            try:
                summary = process_closure_session(root/'input/manifest.json', root/'input/clock.json', case_root/'pipeline',
                                                  pilot_integrations=count, integration_s=.3, correlation_only=True)
                pipeline = case_root/'pipeline'
            except ValueError as exc:
                if str(exc) not in EXPECTED_FAILURES: raise
                failure = EXPECTED_FAILURES[str(exc)]; pipeline = case_root/'pipeline.partial'
                summary = json.loads((pipeline/'pipeline.json').read_text())
                assert summary['state'] == 'incomplete'
            closure = None; error = None; bound = None
            if summary['state'] == 'complete':
                closure = extract_closures(pipeline/'correlation/shard-00000.npz', case_root/'closures.npz', min_snr=10.)
                residual = np.asarray(summary['rate_estimate']['station_rates_hz']) - generating['station_rates_hz']
                error = float(np.max(np.abs(residual)))
                pairs = load_spectral(pipeline/'correlation/shard-00000.npz')['pairs']
                bound = float(np.min(np.abs(np.sinc(.3*(residual[pairs[:, 0]] - residual[pairs[:, 1]])))))
            science = scientific_projection(summary, pipeline, closure)
            row = {'case': f'seed{seed}_pilot{count}', 'seed': seed, 'pilot_integrations': count,
                   'input_directory': str((root/'input').relative_to(out)), 'case_directory': str(case_root.relative_to(out)),
                   'input_sha256': input_sha, 'generating': generating, 'scientific_failure_code': failure,
                   'maximum_station_rate_error_hz': error,
                   'calculated_minimum_constant_rate_boxcar_retention': bound,
                   'retention_is_calculation_not_measured_coherence': True,
                   'truth_used_by_estimator': False, 'science': science}
            rows.append(row); (case_root/'science.json').write_text(json.dumps(science, indent=2, allow_nan=False)+'\n')
            (out/'progress.json').write_text(json.dumps(rows, indent=2, allow_nan=False)+'\n')
            assert input_sha == {p.name: sha(p) for p in sorted((root/'input').iterdir()) if p.is_file()}
            print(json.dumps({'case': row['case'], 'state': science['state'], 'edges': science['graph']['accepted_baselines'],
                              'failure': failure, 'max_rate_error_hz': error, 'closures': closure}), flush=True)
    result = {'type': 'fixed_long_vdif_pilot_acquisition', 'fixed_seeds': [109, 110, 111], 'cases': rows,
              'final_integration_s': .3, 'preliminary_outputs_counted_as_formal': False,
              'limits': 'Three fixed synthetic 3.04s raw observations, nested 1/2/3s pilots, exact supplied sample clocks/scales, stable gain/LO, threshold unchanged. Formal processing re-executed for all nine cases. Not a calibrated detection probability, measured OCXO/coherence, RML image or full-night performance. Short stage109 raw has a different noise/gain/LO realization; do not attribute differences across raw files to pilot length.'}
    (out/'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n'); return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True); parser.add_argument('--seed109-input', required=True)
    args = parser.parse_args(); run(args.output, args.seed109_input)
