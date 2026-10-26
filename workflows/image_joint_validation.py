"""同一幾何の別生成原本を、時刻を捏造せず独立Closureセルとして併用する。"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from vsora_formats.spectral import load_spectral, validate_spectral
from vsora_imaging.objective_evaluation import evaluate_closure_image
from vsora_imaging.rml import fit_closure_image
from vsora_imaging.experiment import compare_relative
from vsora_imaging.assessment import assess_rml_result


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stack_replicates(data):
    """同じ幾何・単位の別実験をcell軸で併用し、原本の配列を保持する。"""
    if len(data) < 2:
        raise ValueError('at least two distinct replicate inputs required')
    for item in data: validate_spectral(item)
    first = data[0]
    unit = first['metadata']['visibility_unit']
    for item in data[1:]:
        for key in ('pairs', 'times_s', 'frequencies_hz', 'uvw_lambda'):
            if not np.array_equal(first[key], item[key]):
                raise ValueError('replicate axes differ: '+key)
        if item['metadata']['visibility_unit'] != unit:
            raise ValueError('replicate visibility units differ')
    return (*[np.concatenate([item[key] for item in data], axis=0) for key in ('uvw_lambda', 'visibilities', 'weights')], first['pairs'].copy())


def stable(value):
    if isinstance(value, dict): return {k: stable(v) for k, v in value.items() if k != 'elapsed_s'}
    if isinstance(value, list): return [stable(v) for v in value]
    return value


def weighted_check(arguments, training, image, settings):
    combined = evaluate_closure_image(*arguments, image, **settings)
    separate = [evaluate_closure_image(d['uvw_lambda'], d['visibilities'], d['weights'], d['pairs'], image, **settings) for d in training]
    counts = [v['metrics']['independent_closure_count'] for v in separate]
    expected = sum(v['metrics']['data_loss']*n for v, n in zip(separate, counts, strict=True))/sum(counts)
    np.testing.assert_allclose(combined['metrics']['data_loss'], expected, rtol=1e-11, atol=1e-12)
    assert combined['metrics']['independent_closure_count'] == sum(counts)
    for name in ('entropy_loss', 'tsv_loss', 'centroid_loss'):
        for result in separate: np.testing.assert_allclose(combined['metrics'][name], result['metrics'][name], rtol=1e-13, atol=1e-15)
    return {'combined': combined, 'per_input': separate, 'independent_count_weighted_data_loss': expected}


def run(reference, output):
    reference = Path(reference); out = Path(output); out.mkdir(parents=True, exist_ok=False)
    source = json.loads((reference/'summary.json').read_text())
    rows = [r for r in source['candidates'] if r['kind'] == 'truth' and r['case'].endswith('_truth_rate_control')]
    assert [r['generating']['seed'] for r in rows] == [109, 110, 111]
    spectra = [r['spectrum'] for r in rows]; hashes = [sha(p) for p in spectra]
    assert len(set(hashes)) == 3
    data = [load_spectral(p) for p in spectra]
    settings = rows[0]['settings']; assert all(r['settings'] == settings for r in rows)
    truth = np.load(rows[0]['image'], allow_pickle=False)
    prior_row = next(r for r in source['candidates'] if r['kind'] == 'prior')
    prior = np.load(prior_row['image'], allow_pickle=False)
    image_hashes = {r['image']: sha(r['image']) for r in (*rows, prior_row)}
    cases = []
    for omitted in (None, 109, 110, 111):
        selected = [i for i, r in enumerate(rows) if r['generating']['seed'] != omitted]
        arguments = stack_replicates([data[i] for i in selected])
        identity = 'all3' if omitted is None else f'omit{omitted}'
        root = out/identity; root.mkdir()
        # 真の天空・除外入力はこの呼び出しへ渡さない。
        image, summary = fit_closure_image(*arguments, pixels=32, starts=3, max_iterations=2000, seed=21, **settings)
        np.save(root/'relative-model.npy', image)
        cost = {name: weighted_check(arguments, [data[i] for i in selected], value, settings)
                for name, value in [('truth', truth), ('prior', prior), ('fitted', image)]}
        np.testing.assert_allclose(cost['fitted']['combined']['metrics']['objective'], summary['objective'] - summary['parameter_sum_penalty'], rtol=1e-7, atol=1e-8)
        metrics, _, _, _ = compare_relative(truth, image, settings['pixel_arcsec'])
        evaluations = [evaluate_closure_image(d['uvw_lambda'], d['visibilities'], d['weights'], d['pairs'], image, **settings) for d in data]
        science = {'rml_summary': stable(summary), 'cost_checks': cost, 'all_three_input_evaluations': evaluations,
                   'reference_metrics': metrics, 'assessment': assess_rml_result(summary, reference_metrics=metrics),
                   'image_sha256': sha(root/'relative-model.npy')}
        row = {'case': identity, 'training_seeds': [rows[i]['generating']['seed'] for i in selected],
               'excluded_from_fit_seed': omitted, 'science': science}
        (root/'science.json').write_text(json.dumps(science, indent=2, allow_nan=False)+'\n'); cases.append(row)
        print(json.dumps({'case': identity, 'nrmse': metrics['registered_nrmse'], 'selected_converged': science['assessment']['numerical']['state']}), flush=True)
    assert all(sha(p) == h for p, h in zip(spectra, hashes, strict=True))
    assert all(sha(p) == h for p, h in image_hashes.items())
    result = {'stage': 117, 'state': 'complete', 'cases': cases, 'spectra': spectra, 'input_sha256': hashes,
              'settings': settings, 'generating_conditions': [r['generating'] for r in rows],
              'all_input_sha_preserved': True, 'no_spectral_time_axis_fabricated': True,
              'limits': 'Same time/uv, three independently seeded voltage/gain/LO realizations; true LO supplied for evaluation controls. Cells stacked without visibility averaging or intersection-mask deletion. Excluded input and truth not supplied to fit. Post-hoc diagnostic after previous results were inspected, not blind holdout or a calibrated generalization estimate. No new uv coverage, unknown-LO recovery, low-SNR likelihood or actual observation certified.'}
    (out/'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--reference', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); run(args.reference, args.output)
