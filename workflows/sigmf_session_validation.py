"""Saved, distinct simulated stations: bounded SigMF session/finite-operator check.

Only methods/code are published. All fixture bytes and numerical results belong
under ignored outputs/. This does not provide a real multi-station observation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import astropy.units as u
from astropy.time import Time
import numpy as np

from vsora_correlator.aligned import correlate_aligned
from vsora_formats.spectral import load_spectral
from vsora_observation import load_config
from vsora_observation.geometry import geometry_at_times


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def prepare(saved, destination):
    """One-time byte derivation from seven stored EDV0/8bit VDIF frames per station.

    2*byte-255 is a fixed integer code scale, not the supplied physical scale.
    The separate old-VDIF control retains its original files with scale 71.
    """
    saved = Path(saved).resolve(); destination = Path(destination)
    if destination.exists():
        raise FileExistsError('choose a new fixture directory')
    manifest = json.loads((saved/'manifest.json').read_text())
    observation = json.loads((saved/'observation.json').read_text())
    clock = json.loads((saved/'clock.json').read_text())
    destination.mkdir(parents=True)
    write_json(destination/'observation.json', observation)
    write_json(destination/'clock.json', clock)
    manifest['blocks_per_integration'] = 128
    legacy = json.loads(json.dumps(manifest))
    sigmf = []
    for number, station in enumerate(manifest['stations']):
        path = saved/station['vdif']
        payloads = []
        with path.open('rb') as stream:
            for _ in range(7):
                header = stream.read(32)
                if len(header) != 32:
                    raise ValueError('insufficient saved frames')
                words = np.frombuffer(header, '<u4')
                if int(words[2] & 0xffffff)*8 != 8224 or words[0] >> 30 or words[3] >> 26 != 39:
                    raise ValueError('saved fixture frame profile differs')
                payload = stream.read(8192)
                if len(payload) != 8192:
                    raise ValueError('short saved payload')
                payloads.append(np.frombuffer(payload, np.uint8).astype(np.int16)*2-255)
        stem = f'station-{number+1}'
        np.concatenate(payloads).astype('<i2').tofile(destination/(stem+'.sigmf-data'))
        metadata = {'global': {'core:version': '1.2.0', 'core:datatype': 'ci16_le',
                               'core:sample_rate': manifest['sample_rate_hz']},
                    'captures': [{'core:sample_start': 0,
                                  'core:frequency': observation['observation']['frequency_hz'],
                                  'core:datetime': observation['observation']['start_utc']}],
                    'annotations': []}
        write_json(destination/(stem+'.sigmf-meta'), metadata)
        sigmf.append({'id': station['id'], 'sigmf': stem+'.sigmf-meta'})
        legacy['stations'][number].update(vdif=str(path), decoded_voltage_scale=71.)
    manifest.update(input_format='sigmf_ci16_le', stations=sigmf)
    write_json(destination/'manifest.json', manifest)
    write_json(destination/'legacy.json', legacy)


def independent_visibility(manifest, clock):
    """Direct finite convolution/interpolation/DFT; shared supplied geometry only."""
    root = Path(manifest).parent
    c = json.loads(Path(manifest).read_text()); k = json.loads(Path(clock).read_text())
    config = load_config(root/c['observation_config'])
    fs = c['sample_rate_hz']; nfft = c['fft_length']; blocks = c['blocks_per_integration']
    count = nfft*blocks; span = 2*count/fs; start = .002
    fc = config['observation']['frequency_hz']
    edges = np.array([start, start+span])
    delays = geometry_at_times(config, Time(config['observation']['start_utc'])+edges*u.s,
                               filter_elevation=False)['station_delay_s']
    samples = []
    for station, measured in zip(c['stations'], k['stations']):
        data_path = (root/station['sigmf']).with_suffix('.sigmf-data')
        raw = np.fromfile(data_path, '<i2').reshape(-1, 2)
        samples.append(raw[:, 0].astype(float)+1j*raw[:, 1])
    values = []
    for integration in range(2):
        t = start+(integration*count+np.arange(count))/fs
        spectra = []
        for station, (raw, measured) in enumerate(zip(samples, k['stations'])):
            ratio = fs/measured['actual_sample_rate_hz']
            n = np.arange(-32, 33)
            h = .7*ratio*np.sinc(.7*ratio*n)*np.kaiser(65, 8.6); h /= h.sum()
            filtered = np.convolve(raw, h)[:len(raw)]
            delay = np.interp(t, edges, delays[:, station])
            q = (t-delay-measured['input_start_offset_s'])*measured['actual_sample_rate_hz']+32
            indices = np.floor(q).astype(int)[:, None]+n
            assert indices.min() >= 64 and indices.max() < len(raw)
            d = q[:, None]-indices
            coefficients = np.sinc(d)*np.where(abs(d) <= 32, .5*(1+np.cos(np.pi*d/32)), 0)
            coefficients /= coefficients.sum(axis=1)[:, None]
            interpolated = (filtered[indices]*coefficients).sum(axis=1)
            corrected = interpolated*np.exp(-2j*np.pi*fc*delay)
            spectra.append(np.fft.fft(corrected.reshape(blocks, nfft), axis=1)/np.sqrt(nfft))
        pairs = [(i, j) for i in range(len(samples)) for j in range(i+1, len(samples))]
        order = np.argsort(fc+np.fft.fftfreq(nfft, 1/fs))
        values.append(np.array([np.mean(spectra[i]*spectra[j].conj(), axis=0)[order]
                                for i, j in pairs]).T)
    return np.array(values)


def run(inputs, output):
    inputs = Path(inputs).resolve(); output = Path(output)
    if output.exists():raise FileExistsError('choose a new output directory')
    started = time.monotonic(); output.mkdir(parents=True)
    import_current = int(Path('/proc/self/statm').read_text().split()[1])*resource.getpagesize()
    manifest = inputs/'manifest.json'; clock = inputs/'clock.json'
    correlate_aligned(manifest, clock, output/'sigmf', 2, collect_bispectrum=True)
    correlate_aligned(inputs/'legacy.json', clock, output/'legacy', 2, collect_bispectrum=True)
    actual = load_spectral(output/'sigmf/shard-00000.npz')
    reference = independent_visibility(manifest, clock)
    np.testing.assert_allclose(actual['visibilities'], reference, rtol=1e-10, atol=1e-7)
    assert actual['metadata']['visibility_unit'] == 'ADC^2'
    assert np.all(actual['valid_fft_count'] == 128)
    assert 'vdif_read_mode' not in actual['metadata']
    np.savez(output/'independent.npz', visibilities=reference)
    summary = {'state': 'complete', 'input_kind': 'distinct stored simulated station code units',
               'independent_visibility_max_abs_error': float(abs(actual['visibilities']-reference).max()),
               'rtol': 1e-10, 'atol_ADC2': 1e-7, 'real_baselines': 0,
               'shared_reference': 'supplied observation geometry; no independent EOP verification',
               'wall_s': time.monotonic()-started,
               'peak_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
               'import_current_RSS_bytes': import_current,
               'conservative_additional_peak_bytes': max(0, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024-import_current)}
    write_json(output/'summary.json', summary)
    modules = {n:m.__file__ for n,m in sys.modules.items()
               if n.startswith('vsora_') and getattr(m,'__file__',None)}
    write_json(output/'environment.json', {'product_modules': modules})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True); parser.add_argument('--output', required=True)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if args.prepare:prepare(args.input, args.output)
    else:print(json.dumps(run(args.input, args.output)))


if __name__ == '__main__':main()
