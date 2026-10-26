"""同じ名目視野の8/16/32格子を、原本・基線を変えず比較する。"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from vsora_formats.spectral import load_spectral
from vsora_imaging.rml import image_closure
from vsora_imaging.objective_evaluation import evaluate_closure_image
from vsora_imaging.experiment import compare_relative
from vsora_simulator.visibility import direct_visibility
from workflows.integration_image_validation import stable_rml_summary
from workflows.rate_acquisition_validation import arrays_identity


def embed_on_32(image):
    """点pixelモデルの同じ座標へfluxを置く。補間・追加のfitはしない。"""
    q = np.asarray(image)
    if (q.ndim != 2 or q.shape[0] != q.shape[1] or q.shape[0] not in (8, 16, 32)
            or not np.issubdtype(q.dtype, np.number) or np.iscomplexobj(q)
            or not np.isfinite(q).all() or np.any(q < 0)):
        raise ValueError('finite nonnegative positive-flux square 8/16/32 image required')
    q = np.asarray(q, dtype=float)
    with np.errstate(over='ignore'):
        total = q.sum()
    if not np.isfinite(total) or total <= 0:
        raise ValueError('finite positive image flux required')
    result = np.zeros((32, 32), dtype=float)
    result[::32//len(q), ::32//len(q)] = q
    return result


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(reference, output):
    reference = Path(reference); out = Path(output); out.mkdir(parents=True, exist_ok=False)
    source = json.loads((reference/'summary.json').read_text())
    assert source['stage'] == 118 and len(source['branches']) == 3
    assert all(x['state'] == 'complete' for x in source['branches'])
    truth = np.load(reference/'truth.npy', allow_pickle=False); truth_sha = sha(reference/'truth.npy')
    rows = []
    for branch in source['branches']:
        name = branch['branch']; spectrum = reference/name/'visibility.npz'; digest = sha(spectrum); data = load_spectral(spectrum)
        assert arrays_identity(data) == branch['science']['input_arrays']
        root = out/name; root.mkdir()
        for pixels in (8, 16, 32):
            case = root/f'pixels{pixels}'; case.mkdir()
            settings = {**source['settings'], 'pixels': pixels, 'pixel_arcsec': 512./pixels}
            if pixels == 32:
                image_path = reference/name/'rml/relative-model.npy'
                summary = json.loads((reference/name/'rml/summary.json').read_text()); reused = True
            else:
                summary = image_closure(spectrum, case/'rml', **settings)
                image_path = case/'rml/relative-model.npy'; reused = False
            image = np.load(image_path, allow_pickle=False); embedded = embed_on_32(image)
            np.save(case/'embedded-model.npy', embedded)
            a = direct_visibility(data['uvw_lambda'], image, settings['pixel_arcsec'])
            b = direct_visibility(data['uvw_lambda'], embedded, 16.)
            np.testing.assert_allclose(a, b, rtol=1e-12, atol=1e-14)
            cost_settings = {k:v for k,v in settings.items() if k not in ('pixels','starts','max_iterations','seed')}
            coarse_cost = evaluate_closure_image(data['uvw_lambda'], data['visibilities'], data['weights'], data['pairs'], image, **cost_settings)
            fine_cost = evaluate_closure_image(data['uvw_lambda'], data['visibilities'], data['weights'], data['pairs'], embedded, **{**cost_settings,'pixel_arcsec':16.})
            for key in ('data_loss','centroid_loss'):
                np.testing.assert_allclose(coarse_cost['metrics'][key], fine_cost['metrics'][key], rtol=1e-9, atol=1e-11)
            assert coarse_cost['metrics']['independent_closure_counts'] == branch['science']['rml_summary']['independent_closure_counts']
            metrics, _, _, _ = compare_relative(truth, embedded, 16.)
            if reused: assert metrics == branch['science']['reference_metrics']
            science = {'rml_summary':stable_rml_summary(summary),'coarse_objective':coarse_cost,
                       'embedded_reference_grid_objective':fine_cost,'reference_metrics':metrics,
                       'maximum_complex_visibility_embedding_difference':float(np.max(np.abs(a-b))),
                       'coarse_image_sha256':sha(image_path),'embedded_image_sha256':sha(case/'embedded-model.npy')}
            rows.append({'branch':name,'pixels':pixels,'pixel_arcsec':settings['pixel_arcsec'],
                         'nominal_extent_arcsec':512.,'fit_reused_from_118':reused,
                         'spectrum':str(spectrum.resolve()),'input_sha256':digest,'science':science})
            (case/'science.json').write_text(json.dumps(science,indent=2,allow_nan=False)+'\n')
            print(json.dumps({'branch':name,'pixels':pixels,'reused_fit':reused,'nrmse':metrics['registered_nrmse']}),flush=True)
        assert sha(spectrum)==digest
    assert sha(reference/'truth.npy')==truth_sha
    result={'stage':119,'state':'complete','cases':rows,'source_reference':str(reference.resolve()),
            'new_fits':6,'cited_118_fits':3,'starts_each':3,'all_input_sha_preserved':True,
            'limits':'Fixed 8/16/32 point-pixel grids with nominal N*spacing=512 arcsec. Existing centered-pixel convention changes edge-center sampling; regularizer discretization and magnitude also change. Not a pure degree-of-freedom intervention. Zero embedding preserves point locations/flux and model visibilities, not a continuous-cell response assumption. No interpolation or post-fit optimization. Do not rank total objectives across grids or choose a grid using truth and claim blind performance. True-LO/ideal branches remain evaluation-only.'}
    (out/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--reference',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();run(args.reference,args.output)
