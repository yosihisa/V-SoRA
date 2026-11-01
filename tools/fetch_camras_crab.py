"""CAMRAS公開原本を容量制限付きで取得する。原本・記録はGit管理外へ置く。"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

BASE = 'https://data.camras.nl/giantpulses/'
FILES = ('crab-giantpulse.sigmf-meta', 'crab-giantpulse.sigmf-data')
MAX_BYTES = 32 * 1024**2
FREE_FLOOR = 10 * 1024**3


def run(directory):
    dest = Path(directory)
    if dest.exists():
        raise FileExistsError('use a new recording directory; do not overwrite originals')
    parent = dest.parent
    parent.mkdir(parents=True, exist_ok=True)
    before = shutil.disk_usage(parent).free
    if before < FREE_FLOOR + MAX_BYTES:
        raise OSError('10 GiB free reserve and 32 MiB transfer budget required')
    dest.mkdir()
    receipt = {'retrieved_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'free_before_bytes': before, 'max_total_bytes': MAX_BYTES,
               'free_floor_bytes': FREE_FLOOR, 'files': [], 'complete': False}
    total = 0
    try:
        for name in FILES:
            url = BASE + name
            partial = dest / (name + '.partial')
            digest = hashlib.sha256()
            size = 0
            with urllib.request.urlopen(url, timeout=30) as response, partial.open('xb') as out:
                advertised = response.headers.get('Content-Length')
                if advertised is not None and total + int(advertised) > MAX_BYTES:
                    raise OSError('advertised payload exceeds transfer budget')
                headers = {k: response.headers.get(k) for k in ('Content-Length', 'ETag', 'Last-Modified')}
                while chunk := response.read(65536):
                    if total + len(chunk) > MAX_BYTES or shutil.disk_usage(dest).free < FREE_FLOOR + len(chunk):
                        raise OSError('transfer or free-space budget exceeded')
                    out.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                    total += len(chunk)
                if advertised is not None and size != int(advertised):
                    raise OSError('incomplete HTTP content')
            partial.rename(dest / name)
            receipt['files'].append({'name': name, 'url': url, 'bytes': size,
                                     'sha256': digest.hexdigest(), 'http_headers': headers})
        receipt['complete'] = True
    finally:
        receipt['total_bytes'] = total
        receipt['free_after_bytes'] = shutil.disk_usage(dest).free
        (dest / 'acquisition.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    run(parser.parse_args().directory)
