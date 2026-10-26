"""checkout外から導入済みsolverだけで固定4ケースを再構成する。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import numpy as np
from vsora_formats.spectral import load_spectral
from vsora_imaging.objective_evaluation import evaluate_closure_image
from vsora_imaging.rml import fit_closure_image
from vsora_imaging.experiment import compare_relative
from vsora_imaging.assessment import assess_rml_result


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stable(value):
    if isinstance(value, dict): return {k: stable(v) for k, v in value.items() if k != 'elapsed_s'}
    if isinstance(value, list): return [stable(v) for v in value]
    return value


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--reference', required=True)
    parser.add_argument('--candidates', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); checkout = Path(__file__).resolve().parents[1]
    assert not Path.cwd().resolve().is_relative_to(checkout) and 'PYTHONPATH' not in os.environ
    assert not (Path.cwd()/'tools/run.py').exists()
    out = Path(args.output); out.mkdir(parents=True, exist_ok=False)
    source = json.loads((Path(args.reference)/'summary.json').read_text())
    candidates = json.loads((Path(args.candidates)/'summary.json').read_text())['candidates']
    truth_row = next(r for r in candidates if r['kind'] == 'truth')
    prior_row = next(r for r in candidates if r['kind'] == 'prior')
    truth = np.load(truth_row['image'], allow_pickle=False); prior = np.load(prior_row['image'], allow_pickle=False)
    data = [load_spectral(path) for path in source['spectra']]
    for path, digest in zip(source['spectra'], source['input_sha256'], strict=True): assert sha(path) == digest
    checked = []
    for row in source['cases']:
        root = out/row['case']; root.mkdir()
        selected = [i for i, seed in enumerate((109, 110, 111)) if seed in row['training_seeds']]
        arrays = [np.concatenate([data[i][key] for i in selected], axis=0) for key in ('uvw_lambda', 'visibilities', 'weights')]
        arguments = [*arrays, data[0]['pairs']]
        image, summary = fit_closure_image(*arguments, **row['science']['rml_summary']['settings'])
        np.save(root/'relative-model.npy', image)
        np.testing.assert_array_equal(image, np.load(Path(args.reference)/row['case']/'relative-model.npy', allow_pickle=False))
        assert sha(root/'relative-model.npy') == row['science']['image_sha256']
        costs = {}
        for kind, candidate in [('truth', truth), ('prior', prior), ('fitted', image)]:
            joint = evaluate_closure_image(*arguments, candidate, **source['settings'])
            separate = [evaluate_closure_image(data[i]['uvw_lambda'], data[i]['visibilities'], data[i]['weights'], data[i]['pairs'], candidate, **source['settings']) for i in selected]
            total = sum(r['metrics']['data_loss']*r['metrics']['independent_closure_count'] for r in separate)
            expected = total/sum(r['metrics']['independent_closure_count'] for r in separate)
            costs[kind] = {'combined': joint, 'per_input': separate, 'independent_count_weighted_data_loss': expected}
        metrics, _, _, _ = compare_relative(truth, image, source['settings']['pixel_arcsec'])
        science = {'rml_summary': stable(summary), 'cost_checks': costs,
                   'all_three_input_evaluations': [evaluate_closure_image(d['uvw_lambda'], d['visibilities'], d['weights'], d['pairs'], image, **source['settings']) for d in data],
                   'reference_metrics': metrics, 'assessment': assess_rml_result(summary, reference_metrics=metrics),
                   'image_sha256': sha(root/'relative-model.npy')}
        assert science == row['science']
        (root/'science.json').write_text(json.dumps(science, indent=2, allow_nan=False)+'\n')
        checked.append(row['case'])
    for path, digest in zip(source['spectra'], source['input_sha256'], strict=True): assert sha(path) == digest
    modules = sorted(n for n, m in sys.modules.items() if n.startswith('vsora_') and getattr(m, '__file__', None))
    assert all(Path(sys.modules[n].__file__).is_relative_to(Path(sys.prefix)) for n in modules)
    record = {'state': 'complete', 'all_science_json_and_image_bytes_identical': checked,
              'all_input_sha_unchanged': True, 'outside_checkout': True, 'runner_absent': True,
              'pythonpath_absent': True, 'workflow_not_imported': 'workflows.image_joint_validation' not in sys.modules,
              'project_modules': modules, 'all_project_modules_in_prefix': True,
              'native_solver_calls': 4, 'starts_each': 3, 'no_actual_time_axis_fabricated': True}
    (out/'verification.json').write_text(json.dumps(record, indent=2)+'\n'); print(json.dumps(record))


if __name__ == '__main__': main()
