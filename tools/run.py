"""Run source modules or pytest without an editable installation."""
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
for parent in ("apps", "packages"):
    for path in sorted((root / parent).glob("*/src")):
        sys.path.insert(0, str(path))
if len(sys.argv) < 2:
    raise SystemExit("Usage: python tools/run.py MODULE [arguments]; MODULE=pytest for tests")
module = sys.argv.pop(1)
sys.argv[0] = module
runpy.run_module(module, run_name="__main__", alter_sys=True)
