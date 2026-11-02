"""Conditional high-SNR reference image connection on stored synthetic stations.

No real-data likelihood calibration or new noise model is tested here. All
recordings, arrays, images and numerical reports belong in ignored outputs/.
"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from astropy.io import fits
from vsora_correlator import input_identity
from vsora_correlator.sequence import process_sequence
from vsora_formats.spectral import load_spectral
from vsora_imaging.rml import ClosureObjective
from workflows.sigmf_sequence_validation import compare_legacy, write_json

IMAGE_SETTINGS = dict(starts=1, max_iterations=100, prior_fwhm_arcsec=240., entropy=.01, tsv=.0001)
SEQUENCE_SETTINGS = dict(window_count=2, pilot_integrations=64, integration_s=.1,
                         max_rate_hz=100., save_bispectrum=True, **IMAGE_SETTINGS)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def normalize(value):
    """Remove only predeclared tracking SHA, verification diagnostics and timing.

    verify_tracking checks file digests independently before this is used.
    Scientific fields, byte sizes, optimizer status and regularizers remain.
    """
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items() if k not in {
            'input_sha256', 'input_identity_verification', 'original_files_rehashed',
            'sigmf_identity_scope', 'sigmf_reference_image', 'imaging_validation_scope', 'elapsed_s'}}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return value


def verify_tracking(folder, paths):
    d = load_spectral(folder/'visibility.npz')
    assert [v['input_sha256'] for v in d['metadata']['source_inputs']] == [sha(p) for p in paths]
    assert json.loads((folder/'rml/summary.json').read_text())['input_sha256'] == sha(folder/'visibility.npz')
    with np.load(folder/'closures.npz') as c:
        assert json.loads(c['metadata_json'].item())['input_sha256'] == sha(folder/'visibility.npz')
    image = np.load(folder/'rml/relative-model.npy')
    assert image.shape == (32, 32) and np.isfinite(image).all() and np.all(image >= 0)
    np.testing.assert_allclose(image.sum(), 1., rtol=0, atol=1e-12)
    with fits.open(folder/'rml/relative-model.fits', checksum=True) as hdus:
        hdu = hdus[0]
        assert hdu.verify_checksum() == hdu.verify_datasum() == 1
        assert hdu.header['BUNIT'] == '1/pixel'
        assert hdu.header['FLUXREF'] == 'ARBITRARY' and hdu.header['POSREF'] == 'ASSUMED'
        np.testing.assert_array_equal(hdu.data, image.astype(np.float32))


def compare_images(current, baseline):
    count = 0
    for name in ['visibility.npz', 'closures.npz']:
        with np.load(current/name) as a, np.load(baseline/name) as b:
            assert a.files == b.files
            for key in a.files:
                if key == 'metadata_json':
                    assert normalize(json.loads(a[key].item())) == normalize(json.loads(b[key].item()))
                else:
                    np.testing.assert_array_equal(a[key], b[key])
                count += 1
    np.testing.assert_array_equal(np.load(current/'rml/relative-model.npy'), np.load(baseline/'rml/relative-model.npy'))
    for name in ['summary.json', 'rml/summary.json']:
        assert normalize(json.loads((current/name).read_text())) == normalize(json.loads((baseline/name).read_text()))
    return count + 1


def independent_objective(path):
    """Independent finite pixel sum and covariance solve, conditional on rows.

    Product row selection is deliberately shared. Its Fourier matrix, observed
    closure values, covariance factors and objective implementation are unused.
    """
    data = load_spectral(path)
    v, weight, uvw = [data[k] for k in ('visibilities', 'weights', 'uvw_lambda')]
    obj = ClosureObjective(uvw, v, weight, data['pairs'], pixels=32, pixel_arcsec=16.,
                           prior_fwhm_arcsec=240., entropy=.01, tsv=.0001, centroid=.1)
    axis = (np.arange(32)-16)*16.
    xx, yy = np.meshgrid(axis, axis)
    l, m = xx.ravel()*np.pi/(180*3600), yy.ravel()*np.pi/(180*3600)
    n = np.sqrt(1-l*l-m*m)-1
    prior = np.maximum(np.exp(-4*np.log(2)*(xx*xx+yy*yy)/240.**2), 1e-12).ravel()
    prior /= prior.sum()
    xy = np.stack([xx.ravel(), yy.ravel()])/256.
    observed = v.reshape(-1, v.shape[-1])
    variance = np.zeros(v.shape)
    np.divide(1., abs(v)**2*weight, out=variance, where=(abs(v)*np.sqrt(weight) >= 10.))
    variance = variance.reshape(observed.shape)
    coordinates = uvw.reshape(-1, 3)
    def reference(z):
        q = np.exp(z-z.max()); q /= q.sum()
        model = np.zeros(coordinates.shape[0], complex)
        for index in range(q.size):
            phase = coordinates[:, 0]*l[index]+coordinates[:, 1]*m[index]+coordinates[:, 2]*n[index]
            model += q[index]*np.exp(-2j*np.pi*phase)
        model = model.reshape(observed.shape)
        chi = 0.; count = 0
        for index, cell in enumerate(obj.cells):
            for name, matrix, _, factor in cell:
                if factor is None:
                    continue
                transform = np.angle if name == 'phase' else lambda a: np.log(abs(a))
                residual = matrix @ transform(model[index])-matrix @ transform(observed[index])
                if name == 'phase':
                    residual = np.arctan2(np.sin(residual), np.cos(residual))
                covariance = (matrix*variance[index]) @ matrix.T
                chi += residual @ np.linalg.solve(covariance, residual)
                count += len(matrix)
        image = q.reshape(32, 32)
        entropy = .01*np.sum(q*np.log(q/prior))
        tsv = .0001*q.size*(np.sum(np.diff(image, axis=0)**2)+np.sum(np.diff(image, axis=1)**2))
        centroid = .1*np.sum((xy @ q)**2)
        assert count == obj.count
        return float(.5*chi/count+entropy+tsv+centroid)
    center = np.zeros(1024); center[16*32+16] = 1.
    probes = [.95*center+.05/1024, .90*center+.10*prior]
    directions = []
    for f, trig in [(.37, np.sin), (.37, np.cos), (.61, np.sin), (.61, np.cos)]:
        direction = trig(np.arange(1024)*f); direction -= direction.mean(); direction /= np.linalg.norm(direction)
        directions.append(direction)
    values = []; gradients = []
    for probe in probes:
        z = np.log(probe); value, grad = obj.value_gradient(z); expected = reference(z)
        np.testing.assert_allclose(value, expected, rtol=1e-10, atol=1e-8)
        values.append({'product': float(value), 'independent': expected, 'absolute_error': abs(value-expected)})
        for direction in directions:
            analytic = float(grad @ direction)
            finite = (reference(z+1e-5*direction)-reference(z-1e-5*direction))/2e-5
            np.testing.assert_allclose(analytic, finite, rtol=1e-5, atol=1e-7)
            gradients.append({'analytic': analytic, 'independent_difference': finite, 'absolute_error': abs(analytic-finite)})
    return {'conditional_on_product_selected_rows': True, 'independent_fourier_and_covariance_solve': True,
            'closure_rows': obj.count, 'values': values, 'directions': gradients,
            'statistical_calibration_or_real_data_proved': False, 'MCSE': None}


def run(inputs, saved, baseline, output):
    inputs, saved, baseline, output = map(Path, (inputs, saved, baseline, output))
    if output.exists():
        raise FileExistsError('choose a new output directory')
    before = int(Path('/proc/self/statm').read_text().split()[1])*resource.getpagesize()
    began = time.monotonic(); output.mkdir(parents=True)
    calls = []; digest = input_identity.digest_file
    def count(path):
        calls.append(Path(path)); return digest(path)
    input_identity.digest_file = count
    try:
        result = process_sequence(inputs/'manifest.json', inputs/'clock.json', output/'sigmf',
                                  sigmf_reference_image=True, **SEQUENCE_SETTINGS)
    finally:
        input_identity.digest_file = digest
    process_sequence(inputs/'legacy.json', inputs/'clock.json', output/'legacy', **SEQUENCE_SETTINGS)
    raw = [p for p in calls if p.suffix == '.sigmf-data']
    assert len(raw) == len(set(raw)) == 4 and sum(p.stat().st_size for p in raw) == 9175040
    assert result['input_identity']['sigmf_data_hash_file_reads'] == 4
    assert result['completed_steps'] == result['total_steps'] == 7
    comparisons = {}; optimizers = {}
    for kind in ['sigmf', 'legacy']:
        windows = {}
        for index in [0, 1]:
            name = f'window-{index:04d}'
            windows[name] = compare_legacy(output/kind/name, saved/kind/name)
        current = output/kind/'synthesis'
        paths = [output/kind/f'window-{i:04d}/correlation/shard-00000.npz' for i in [0, 1]]
        oldpaths = [saved/kind/f'window-{i:04d}/correlation/shard-00000.npz' for i in [0, 1]]
        verify_tracking(current, paths); verify_tracking(baseline/kind, oldpaths)
        comparisons[kind] = {'windows': windows, 'image_fields': compare_images(current, baseline/kind)}
        optimizers[kind] = json.loads((current/'rml/summary.json').read_text())['runs']
    independent = independent_objective(output/'sigmf/synthesis/visibility.npz')
    write_json(output/'independent-objective.json', independent)
    summary = {'state': 'complete', 'reference_kind': 'stored distinct synthetic station code units; supplied nominal clocks',
               'real_baselines': 0, 'new_downloads_or_conversions': 0, 'new_MC_trials': 0, 'new_reference_image_invocations': 2,
               'data_full_hash_file_reads': len(raw), 'data_full_hash_bytes': sum(p.stat().st_size for p in raw),
               'derived_data_hash_reads': 0, 'comparison': comparisons, 'optimizers': optimizers,
               'independent_objective': independent, 'wall_s': time.monotonic()-began,
               'import_current_RSS_bytes': before, 'peak_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
               'conservative_additional_peak_bytes': max(0, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024-before)}
    write_json(output/'summary.json', summary)
    write_json(output/'environment.json', {'product_modules': {n: m.__file__ for n, m in sys.modules.items()
               if n.startswith('vsora_') and getattr(m, '__file__', None)}})
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['input', 'saved', 'baseline', 'output']:
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.saved, args.baseline, args.output)))
