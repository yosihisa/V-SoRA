"""Run wheel entrypoints outside the checkout; save no machine/user paths."""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[1];out=Path(a.output).resolve()
    out.mkdir(parents=True,exist_ok=False)
    from vsora_observation.reference import reference_path
    import vsora_simulator,vsora_correlator,vsora_imaging
    if not all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (vsora_simulator,vsora_correlator,vsora_imaging)):
        raise AssertionError('verification must import the installed wheel')
    reference=reference_path()
    if not reference.is_relative_to(Path(sys.prefix)/'share/v-sora/reference'):
        raise AssertionError('reference asset must come from the installed wheel')
    config=json.loads((root/'configs/experiments/ideal-point.json').read_text());config['source']['model']='casa'
    (out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    commands=[]
    with tempfile.TemporaryDirectory(prefix='vsora-wheel-') as directory:
        for name,args in [('vsora-simulate',['--config',str(out/'config.json'),'--output',str(out/'simulation')]),
                          ('vsora-image',['--input',str(out/'simulation/visibility.npz'),'--output',str(out/'imaging'),'--clean-radius-arcsec','220']),
                          ('vsora-correlate',['--help'])]:
            result=subprocess.run([str(Path(sys.prefix)/'bin'/name),*args],cwd=directory,capture_output=True,text=True)
            if result.returncode: raise RuntimeError(f'{name} failed; local stderr inspection required')
            commands.append({'entrypoint':name,'success':True})
    check=subprocess.run([sys.executable,'-m','pip','check'],capture_output=True,text=True)
    if check.returncode: raise AssertionError('installed dependency consistency check failed')
    summary={'python_version':sys.version.split()[0],
             'versions':{name:version(name) for name in ['v-sora','numpy','scipy','astropy','matplotlib','baseband','pytest']},
             'installed_wheel_imports':True,'wheel_reference_asset':True,
             'reference_sha256':hashlib.sha256(reference.read_bytes()).hexdigest(),
             'pip_check_success':True,'entrypoints_outside_checkout':commands,
             'cas_a_smoke_note':'Execution/packaging check only; sparse-array image fidelity evaluated separately',
             'imaging':json.loads((out/'imaging/summary.json').read_text())}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
