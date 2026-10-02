import argparse
import json
from pathlib import Path
from vsora_observation import load_config
from vsora_imaging.experiment import run_simulation
from workflows.compare_arrays import layout


def run(output, model='shell', noise=False, seed=21, prior_fwhm_arcsec=240., starts=3, max_iterations=800, integration_s=.3):
    c = load_config(Path(__file__).resolve().parents[1]/'configs/experiments/ideal-point.json')
    c['source']['model'] = model; c['noise']['enabled'] = noise; c['seed'] = seed
    c['observation'].update(duration_s=14400, integration_s=integration_s)
    c['stations'] = [{'id':f'ST{i+1:02d}', 'enu_m':p, 'sefd_jy':10000.} for i,p in enumerate(layout(8,'spread'))]
    return run_simulation(c, output, prior_fwhm_arcsec=prior_fwhm_arcsec, starts=starts, max_iterations=max_iterations)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True)
    p.add_argument('--model', choices=['double','shell','casa'], default='shell'); p.add_argument('--noise', action='store_true')
    p.add_argument('--seed', type=int, default=21); p.add_argument('--prior-fwhm-arcsec', type=float, default=240.)
    p.add_argument('--integration-s', type=float, default=.3)
    p.add_argument('--starts', type=int, default=3); p.add_argument('--max-iterations', type=int, default=800); a = p.parse_args()
    print(json.dumps(run(**vars(a)), indent=2))
