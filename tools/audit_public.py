"""Audit tracked/staged text and FITS metadata before a public commit.

Heuristic checks complement manual review; they do not prove absence of every
possible personal detail. No unknown value is printed when a match is found.
"""
from pathlib import Path
import re
import subprocess
import sys


def audit():
    failures = []
    names = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    for name in filter(None, names):
        p = Path(name)
        if not p.is_file():
            continue
        if p.suffix == ".fits":
            from astropy.io import fits
            with fits.open(p) as hdus:
                text = "\n".join(str(h.header) for h in hdus)
                if any(k in h.header for h in hdus for k in ("OBSERVER", "AUTHOR")):
                    failures.append((name, "personal FITS fields"))
        elif p.suffix in (".png", ".npz", ".pdf"):
            continue
        else:
            try:
                text = p.read_text()
            except UnicodeDecodeError:
                failures.append((name, "unreviewed binary"))
                continue
        text = text.replace("contributors@vsora.invalid", "")
        patterns = {
            "private email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            "local user path": r"/(?:home|Users)/[A-Za-z0-9_.-]+/|[A-Z]:\\Users\\[A-Za-z0-9_.-]+",
            "credential": r"github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----",
        }
        for label, pattern in patterns.items():
            if re.search(pattern, text):
                failures.append((name, label))
    for name, label in failures:
        print(f"REVIEW: {name}: {label}")
    print(f"Public audit: {len(failures)} findings")
    return bool(failures)


if __name__ == "__main__":
    sys.exit(audit())
