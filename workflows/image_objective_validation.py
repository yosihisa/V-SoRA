"""同じ固定9データについて、三つの候補画像の損失を正式評価する。"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import numpy as np
from vsora_formats.spectral import load_spectral
from vsora_imaging.rml import ClosureObjective
from vsora_imaging.objective_evaluation import evaluate_closure_image
from vsora_simulator.sky import synthetic_sky
from vsora_simulator.visibility import direct_visibility


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def independent_losses(data, image, objective, settings):
    """直接Fourierとsolveで照合。選択済みdesignと観測誤差近似は共通。"""
    q = np.asarray(image, float); q = q/q.sum()
    model = direct_visibility(data['uvw_lambda'], q, settings['pixel_arcsec']).reshape(-1, data['pairs'].shape[0])
    observed = data['visibilities'].reshape(model.shape)
    variance = objective.closures['baseline_variance'].reshape(model.shape)
    chisq = 0.
    for index, cell in enumerate(objective.cells):
        for name, matrix, _, _ in cell:
            if not len(matrix): continue
            if name == 'phase':
                measured = np.angle(np.exp(1j*(matrix @ np.angle(observed[index]))))
                residual = np.angle(np.exp(1j*(matrix @ np.angle(model[index]) - measured)))
            else:
                measured = matrix @ np.log(np.where(np.abs(observed[index]) > 0, np.abs(observed[index]), 1.))
                residual = matrix @ np.log(np.abs(model[index])) - measured
            covariance = (matrix*variance[index]) @ matrix.T
            chisq += float(residual @ np.linalg.solve(covariance, residual))
    entropy = settings['entropy']*float(np.sum(q.ravel()*np.log(np.maximum(q.ravel(), 1e-300)/objective.prior)))
    tsv = settings['tsv']*q.size*float(np.sum(np.diff(q, axis=0)**2) + np.sum(np.diff(q, axis=1)**2))
    axis = (np.arange(q.shape[0]) - q.shape[0]//2)*settings['pixel_arcsec']
    yy, xx = np.meshgrid(axis, axis, indexing='ij')
    center = np.array([np.sum(xx*q), np.sum(yy*q)])/(settings['pixel_arcsec']*q.shape[0]/2)
    centroid = settings['centroid']*float(np.sum(center**2))
    data_loss = .5*chisq/objective.count
    return {'objective': data_loss + entropy + tsv + centroid, 'data_loss': data_loss,
            'entropy_loss': entropy, 'tsv_loss': tsv, 'centroid_loss': centroid,
            'closure_chisq_per_measurement': chisq/objective.count}


def run(reference, output):
    reference = Path(reference); out = Path(output); out.mkdir(parents=True, exist_ok=False)
    previous = json.loads((reference/'summary.json').read_text())
    settings = {key: value for key, value in previous['rml_settings'].items() if key not in ('pixels', 'starts', 'max_iterations', 'seed')}
    rows = []; maximum_difference = 0.
    for case in previous['cases']:
        spectrum = Path(case['spectrum']); source_sha = sha(spectrum); data = load_spectral(spectrum)
        config = deepcopy(data['metadata']['config']); assert config['source']['model'] == 'unknown'
        config['source'].update(model=case['generating']['model'], total_flux_jy=case['generating']['assumed_flux_jy'])
        truth = synthetic_sky(config)
        objective = ClosureObjective(data['uvw_lambda'], data['visibilities'], data['weights'], data['pairs'],
                                     pixels=32, **settings)
        fitted = reference/case['case']/'rml/relative-model.npy'; fitted_sha = sha(fitted)
        candidates = {'truth': truth, 'prior': objective.prior.reshape(32, 32), 'fitted': np.load(fitted)}
        for kind, image in candidates.items():
            identity = f"{case['case']}_{kind}"; root = out/identity; root.mkdir()
            image_path = root/'candidate.npy'; np.save(image_path, image)
            result = evaluate_closure_image(data['uvw_lambda'], data['visibilities'], data['weights'], data['pairs'], image, **settings)
            independent = independent_losses(data, image, objective, settings)
            differences = {key: abs(result['metrics'][key] - value) for key, value in independent.items()}
            for key, value in independent.items(): np.testing.assert_allclose(result['metrics'][key], value, rtol=1e-9, atol=1e-10)
            unit = image/image.sum(); softmax_reference = objective.value_gradient(np.log(np.maximum(unit.ravel(), 1e-300)), details=True)
            for key in independent: np.testing.assert_allclose(result['metrics'][key], softmax_reference[key], rtol=1e-9, atol=1e-10)
            if kind == 'fitted':
                summary = case['science']['rml_summary']
                expected = summary['objective'] - summary['parameter_sum_penalty']
                np.testing.assert_allclose(result['metrics']['objective'], expected, rtol=1e-7, atol=1e-8)
            maximum_difference = max(maximum_difference, *differences.values())
            # CLIと同じ来歴キーを追加する。場所はprivate summaryだけに残す。
            result.update(input_sha256=source_sha, candidate_sha256=sha(image_path))
            row = {'candidate_id': identity, 'case': case['case'], 'kind': kind,
                   'spectrum': str(spectrum.resolve()), 'image': str(image_path.resolve()),
                   'generating': case['generating'], 'settings': settings, 'evaluation': result,
                   'independent_losses': independent, 'independent_absolute_differences': differences,
                   'softmax_reference_checked': True, 'original_fitted_npy_sha256': fitted_sha,
                   'original_reference_metrics': case['science']['reference_metrics'] if kind == 'fitted' else None}
            rows.append(row); (root/'evaluation.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
            assert sha(spectrum) == source_sha and sha(fitted) == fitted_sha
            print(json.dumps({'candidate': identity, 'objective': result['metrics']['objective'],
                              'independent_max_abs_difference': max(differences.values())}), flush=True)
    summary = {'type': 'fixed_image_objective_candidates', 'state': 'complete', 'candidates': rows,
               'candidate_count': len(rows), 'maximum_independent_absolute_difference': maximum_difference,
               'optimizer_run_by_this_workflow': False,
               'limits': 'Nine fixed existing visibility inputs, three candidates each. Truth is a diagnostic candidate only. Model Fourier and covariance solve paths independently checked, but selected closure designs and fixed observed high-SNR approximation are shared. Image objective excludes parameter-sum penalty. Comparing different data/grid/weights/regularizers is not a likelihood ranking. No physical cause, uncertainty or global optimum certified.'}
    (out/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n'); return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--reference', required=True); p.add_argument('--output', required=True)
    a = p.parse_args(); run(a.reference, a.output)
