"""固定画像を別の有限模擬観測へ移し、共通基線だけの対照も記録する。"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import numpy as np
from vsora_formats.spectral import load_spectral, save_spectral, validate_spectral
from vsora_imaging.objective_evaluation import evaluate_closure_image


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def common_baseline_weights(training, evaluation, min_snr=10.):
    """軸の一致を要求し、元入力で未採用だった基線の評価重みだけを0にする。"""
    validate_spectral(training)
    validate_spectral(evaluation)
    if not np.isfinite(min_snr) or min_snr <= 0:
        raise ValueError('positive finite SNR threshold required')
    for name in ('pairs', 'times_s', 'frequencies_hz', 'uvw_lambda'):
        if not np.array_equal(training[name], evaluation[name]):
            raise ValueError('training/evaluation axes differ: '+name)
    training_snr = np.abs(training['visibilities'])*np.sqrt(training['weights'])
    return np.where(training_snr >= min_snr, evaluation['weights'], 0.)


def evaluate_candidate(data, image, settings):
    """情報不足だけを明示的な未評価へ変換し、他の入力異常は伝播する。"""
    try:
        return evaluate_closure_image(data['uvw_lambda'], data['visibilities'], data['weights'], data['pairs'], image, **settings)
    except ValueError as error:
        if str(error) != 'no high SNR independent closure measurements':
            raise
        return {'state': 'not_evaluable', 'reason': str(error)}


def run(reference, output):
    reference = Path(reference)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    previous = json.loads((reference/'summary.json').read_text())
    rows = previous['candidates']
    fitted = [r for r in rows if r['kind'] == 'fitted']
    truth_rows = [r for r in rows if r['kind'] == 'truth']
    prior_rows = [r for r in rows if r['kind'] == 'prior']
    assert len(fitted) == 9 and len(truth_rows) == len(prior_rows) == 9
    for group in (truth_rows, prior_rows):
        assert len({sha(r['image']) for r in group}) == 1
    candidates = [truth_rows[0], prior_rows[0], *fitted]
    evaluation_rows = [r for r in truth_rows if r['case'].endswith('_truth_rate_control')]
    assert len(evaluation_rows) == 3
    originals = {r[k]: sha(r[k]) for r in rows for k in ('spectrum', 'image')}
    full = []
    common = []

    def evaluate(identity, row, spectrum):
        data = load_spectral(spectrum)
        image = np.load(row['image'], allow_pickle=False)
        result = evaluate_candidate(data, image, row['settings'])
        result.update(input_sha256=sha(spectrum), candidate_sha256=sha(row['image']))
        (out/(identity+'.json')).write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
        return {'id': identity, 'image': row['image'], 'spectrum': str(Path(spectrum).resolve()),
                'settings': row['settings'], 'evaluation': result}

    for evaluation in evaluation_rows:
        data = load_spectral(evaluation['spectrum'])
        settings = evaluation['settings']
        seed = evaluation['generating']['seed']
        for candidate in candidates:
            assert candidate['settings'] == settings
            # 全データ評価でも、周波数・uvの対応を一度も暗黙に変更しない。
            common_baseline_weights(load_spectral(candidate['spectrum']), data, settings['min_snr'])
            identity = f"{candidate['candidate_id']}_on_seed{seed}"
            result = evaluate(identity, candidate, evaluation['spectrum'])
            if candidate['kind'] in ('truth', 'prior') or candidate['case'] == evaluation['case']:
                expected = next(r for r in rows if r['case'] == evaluation['case'] and r['kind'] == candidate['kind'])
                assert result['evaluation'] == expected['evaluation']
            result.update(candidate_id=candidate['candidate_id'], candidate_kind=candidate['kind'],
                          training_seed=candidate['generating']['seed'] if candidate['kind'] == 'fitted' else None,
                          evaluation_seed=seed,
                          distinct_generated_noise_seed=candidate['kind'] == 'fitted' and candidate['generating']['seed'] != seed)
            full.append(result)
        for candidate in fitted:
            training = load_spectral(candidate['spectrum'])
            weights = common_baseline_weights(training, data, settings['min_snr'])
            # 元のpower/rate等の来歴を新しい採用集合へ引き継がない。
            masked = {k: data[k] for k in ('visibilities', 'pairs', 'times_s', 'frequencies_hz', 'uvw_lambda')}
            masked['weights'] = weights
            identity = f"common_{candidate['candidate_id']}_on_seed{seed}"
            spectrum = out/(identity+'.npz')
            metadata = {k: deepcopy(data['metadata'][k]) for k in ('config', 'visibility_unit', 'time_origin_utc') if k in data['metadata']}
            metadata.update(evaluation_only=True, mask_policy='evaluation high-SNR selection restricted to training high-SNR baselines',
                            min_snr=settings['min_snr'], training_sha256=sha(candidate['spectrum']), evaluation_sha256=sha(evaluation['spectrum']))
            save_spectral(spectrum, masked, metadata)
            train_mask = np.abs(training['visibilities'])*np.sqrt(training['weights']) >= settings['min_snr']
            eval_mask = np.abs(data['visibilities'])*np.sqrt(data['weights']) >= settings['min_snr']
            result = {'candidate_id': candidate['candidate_id'], 'training_seed': candidate['generating']['seed'],
                      'evaluation_seed': seed, 'distinct_generated_noise_seed': candidate['generating']['seed'] != seed,
                      'training_spectrum': candidate['spectrum'], 'evaluation_spectrum': evaluation['spectrum'],
                      'training_input_sha256': sha(candidate['spectrum']), 'evaluation_input_sha256': sha(evaluation['spectrum']),
                      'training_selected_baseline_cells': int(train_mask.sum()), 'evaluation_selected_baseline_cells': int(eval_mask.sum()),
                      'intersection_selected_baseline_cells': int((train_mask & eval_mask).sum()),
                      'candidate': evaluate(identity+'_candidate', candidate, spectrum),
                      'truth': evaluate(identity+'_truth', truth_rows[0], spectrum)}
            common.append(result)
        print(json.dumps({'evaluation_seed': seed, 'full': len(full), 'common_pairs': len(common)}), flush=True)
    assert all(sha(path) == digest for path, digest in originals.items())
    count = len(full) + 2*len(common)
    assert count == 87
    summary = {'stage': 116, 'state': 'complete', 'full_evaluations': full, 'common_mask_pairs': common,
               'evaluation_count': count, 'optimizer_executed': False, 'all_original_sha_unchanged': True,
               'generating_conditions': [r['generating'] for r in evaluation_rows],
               'receiver_realization': 'extended_fixture uses each seed for voltage noise, station gain amplitude/phase, and LO; true LO correction does not make this a noise-only intervention. Gains were not saved as fitted calibration inputs.',
               'limits': 'Post-hoc fixed-candidate transfer diagnostic under the same synthetic sky/geometry; evaluation true LO supplied. Different seeds regenerate noise, gain and LO jointly, not noise alone; independence is only under the generator assumptions, and same-seed fits are not independent. Full and common-mask objectives use different constraints: do not subtract them as additive losses or claim prediction improvement from removing unseen baselines. No blind model selection, probability calibration, or real observation certified.'}
    (out/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(args.reference, args.output)
