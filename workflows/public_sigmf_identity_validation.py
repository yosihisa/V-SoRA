"""Closed public SigMF pair: fresh byte identity, supplied fields and API check."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

from vsora_correlator.input_identity import SigMFInputIdentity
from vsora_correlator.sigmf_inspect import inspect_sigmf


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(directory, output):
    began = time.monotonic()
    baseline = int(Path('/proc/self/statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE')
    root, out = Path(directory), Path(output)
    if out.exists():
        raise FileExistsError('use a new validation output directory')
    receipt = json.loads((root / 'acquisition.json').read_text())
    assert receipt['complete']
    expected = {x['name']: x['sha256'] for x in receipt['files']}
    assert all(sha(root / n) == h for n, h in expected.items())
    metadata = root / 'crab-giantpulse.sigmf-meta'
    data = metadata.with_suffix('.sigmf-data')
    pair = {'metadata': {'sha256': sha(metadata), 'bytes': metadata.stat().st_size},
            'data': {'sha256': sha(data), 'bytes': data.stat().st_size}}
    supplied = json.loads(metadata.read_text())
    out.mkdir(parents=True)
    inspection = inspect_sigmf(metadata, out / 'inspection.json',
                               expected_data_sha256=pair['data']['sha256'],
                               expected_metadata_sha256=pair['metadata']['sha256'])
    assert inspection['identity'] == pair
    assert inspection['sample_count'] == data.stat().st_size // 4 == 4000000
    assert inspection['supplied_sample_rate_hz'] == supplied['global']['core:sample_rate'] == 20000000
    assert inspection['supplied_capture_datetime'] == supplied['captures'][0]['core:datetime']
    assert inspection['supplied_center_frequency_hz'] == supplied['captures'][0]['core:frequency']
    assert inspection['station_id'] is None and not inspection['actual_clock_measured']
    assert not inspection['producer_checksum_verified'] and inspection['expected_sha256_pair_matched']
    assert inspection['identity_diagnostics']['data_hash_file_reads'] == 1
    identity = SigMFInputIdentity(metadata)
    for _ in range(3):
        identity.assert_current(metadata)
    assert identity.public_identity == pair and identity.diagnostics['data_hash_file_reads'] == 1
    assert all(sha(root / n) == h for n, h in expected.items())
    summary = {'stage': 169, 'state': 'complete', 'pair': pair, 'sample_count': 4000000,
               'fresh_identity_instances': 2, 'data_full_hash_passes_per_instance': 1,
               'metadata_rehashed_at_boundaries': True,
               'identity_metadata_boundary_checks': 3,
               'comparison': 'fresh independent hashlib and provided JSON fields',
               'raw_download_bytes': 0, 'new_waveform_decode': False,
               'new_MC_trials': 0, 'MCSE': None, 'new_real_correlation_or_image': False}
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    environment = {'product_modules': {n: str(m.__file__) for n, m in sys.modules.items()
                                      if n.startswith('vsora_') and getattr(m, '__file__', None)},
                   'wall_s': time.monotonic() - began, 'import_current_rss_bytes': baseline,
                   'final_lifetime_peak_bytes': peak,
                   'conservative_peak_minus_import_current_bytes': max(0, peak - baseline)}
    (out / 'environment.json').write_text(json.dumps(environment, indent=2) + '\n')
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.output), indent=2))


if __name__ == '__main__':
    main()
