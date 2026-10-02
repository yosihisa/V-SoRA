"""Locate the sanitized scientific reference asset in a checkout or wheel."""
from pathlib import Path
import sys


def reference_path(name='casa-template-jy-pixel.fits'):
    if name not in ('casa-template-jy-pixel.fits','casa-template-jy-pixel.json'):
        raise ValueError('unknown scientific reference asset')
    repo=Path(__file__).resolve().parents[4]
    candidates=[repo/'data/reference'/name,Path(sys.prefix)/'share/v-sora/reference'/name]
    for path in candidates:
        if path.is_file(): return path
    raise FileNotFoundError('V-SoRA scientific reference missing; reinstall the wheel with its data files')
