"""同じ模擬VDIFから短積分画像経路の律速要因を記録する固定実験。"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from vsora_correlator.closure_pipeline import process_closure_session
from vsora_imaging.assessment import assess_pipeline_result
from vsora_imaging.experiment import compare_relative
from workflows.vdif_synthesis_validation import extended_fixture


# 数値モデルの失敗と実装事故を混同しない。型と全文が一致するものだけ保持して次条件へ進む。
EXPECTED_SCIENTIFIC_FAILURES = {
    'detected rate graph is disconnected; use a longer/stronger pilot or fewer stations': 'rate_graph_disconnected',
    'no high SNR independent closure measurements': 'no_high_snr_closures',
}


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def scientific_failure_code(exc):
    if type(exc) is not ValueError or str(exc) not in EXPECTED_SCIENTIFIC_FAILURES:
        raise exc
    return EXPECTED_SCIENTIFIC_FAILURES[str(exc)]


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def run(output):
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    rows = []; panels = []
    for sefd in (1000., 10000.):
        root = out/f'sefd-{int(sefd)}'; root.mkdir()
        truth, rates, generating = extended_fixture(root/'input', '2026-10-02T10:00:00Z', seed=109,
                                                   model='casa', sefd_jy=sefd, frame_count=520)
        np.save(root/'truth-relative.npy', truth)
        generating['truth_used_by_estimator'] = False
        observed = json.loads((root/'input/observation.json').read_text())
        assert observed['source']['model'] == 'unknown' and 'total_flux_jy' not in observed['source']
        input_sha = {p.name: sha(p) for p in sorted((root/'input').iterdir()) if p.is_file()}
        for integration in (.3, 1.):
            case = f'sefd{int(sefd)}_t{integration:g}'
            case_root = root/f'integration-{integration:g}'; case_root.mkdir()
            began = time.monotonic(); failure = None
            def progress(step, count):
                print(json.dumps({'case': case, 'completed_step': step, 'count': count}), flush=True)
            try:
                summary = process_closure_session(root/'input/manifest.json', root/'input/clock.json', case_root/'pipeline',
                    pilot_integrations=250, integration_s=integration, starts=1, max_iterations=2000, progress=progress)
                pipeline_root = case_root/'pipeline'
            except (ValueError, TypeError) as exc:
                failure = scientific_failure_code(exc)
                pipeline_root = case_root/'pipeline.partial'
                summary = json.loads((pipeline_root/'pipeline.json').read_text())
                assert summary['state'] == 'incomplete'
            reference = None
            if summary.get('rml') is not None:
                model = np.load(pipeline_root/'rml/relative-model.npy')
                reference, a, b, registered = compare_relative(truth, model, 16.)
                dump(case_root/'reference-metrics.json', reference)
                panels.append((case, a, b, registered))
            dump(case_root/'pipeline-input.json', summary)
            assessment = assess_pipeline_result(summary, reference_metrics=reference)
            dump(case_root/'assessment.json', assessment)
            estimate_path = pipeline_root/'rate-only.json'
            rate_error = None
            if estimate_path.exists():
                estimate = json.loads(estimate_path.read_text())
                rate_error = float(np.max(np.abs(np.asarray(estimate['station_rates_hz']) - rates)))
            assert input_sha == {p.name: sha(p) for p in sorted((root/'input').iterdir()) if p.is_file()}
            row = {'case': case, 'assumed_sefd_jy': sefd, 'integration_s': integration,
                   'generating': generating, 'input_sha256': input_sha,
                   'truth_sha256': sha(root/'truth-relative.npy'),
                   'maximum_station_rate_error_hz': rate_error, 'scientific_failure_code': failure,
                   'assessment': assessment, 'reference_metrics': reference,
                   'case_directory': str(case_root.relative_to(out)), 'elapsed_s': time.monotonic() - began}
            rows.append(row); dump(out/'progress.json', rows)
            print(json.dumps({'case_finished': case, 'assessment': assessment, 'maximum_rate_error_hz': rate_error}), flush=True)
    result = {'type': 'fixed_vdif_image_path_acceptance', 'seed': 109, 'rows': rows,
              'truth_used_by_estimator': False, 'same_input_reused_for_integrations': True,
              'pilot_integrations': 250, 'pilot_integration_s': .004, 'starts': 1, 'max_iterations': 2000,
              'nrms_error_limit_declared': False,
              'limits': 'Single 1.04s synthetic snapshot, midpoint covariance, supplied exact sample clocks and station voltage scales, fixed gains and LO rates, 8 stations and three useful RF channels. No full-night uv synthesis, hardware, actual SEFD, GPU benchmark or low-SNR image likelihood validation. Truth is used only after inference; no scientific overall-pass flag.'}
    dump(out/'summary.json', result)
    if panels:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(len(panels), 3, figsize=(10, 3*len(panels)), squeeze=False)
        for row, (label, a, b, registered) in zip(axes, panels):
            for axis, title, image in zip(row, ['Truth', 'RML', 'Translated RML'], [a, b, registered]):
                axis.imshow(image, origin='lower', cmap='inferno', vmin=0, vmax=a.max())
                axis.set_title(title); axis.set_xticks([]); axis.set_yticks([])
            row[0].set_ylabel(label)
        fig.suptitle('Display crops; error metrics use full padded support and 110 arcsec common beam')
        fig.tight_layout(); fig.savefig(out/'comparison.png', dpi=130); plt.close(fig)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    args = parser.parse_args(); run(args.output)
