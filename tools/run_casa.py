"""Run optional CASA tools with project-local configuration and libraries."""
from pathlib import Path
import os
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
python=root/'.casa-venv/bin/python'
if not python.exists(): raise SystemExit('Create the optional .casa-venv first; see docs/design/casa-environment.md')
env=os.environ.copy()
env['CASASITECONFIG']=str(root/'.casa-venv/casasiteconfig.py')
crypto=root/'.casa-ssl/lib/libcrypto.so.3';ssl=root/'.casa-ssl/lib/libssl.so.3'
if crypto.exists() and ssl.exists():
    env['LD_PRELOAD']=str(crypto)+':'+str(ssl)
if len(sys.argv)<2: raise SystemExit('Usage: python tools/run_casa.py SCRIPT [arguments]')
sys.exit(subprocess.call([str(python),*sys.argv[1:]],cwd=root,env=env))
