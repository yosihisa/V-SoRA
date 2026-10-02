"""Export an off-center point to reveal any baseline/conjugation mismatch."""
import argparse
from pathlib import Path
import numpy as np
from vsora_observation import load_config
from vsora_observation.geometry import observation_geometry
from vsora_simulator.visibility import direct_visibility
from vsora_formats.fitsidi import write_fitsidi


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1]
    c=load_config(root/'configs/experiments/ideal-point.json');g=observation_geometry(c)
    image=np.zeros((64,64));image[34,29]=1000  # west48", north32"
    vis=direct_visibility(g['uvw_lambda'],image,16)
    write_fitsidi(out/'point.fits',g,vis,np.ones(vis.shape),c)
    np.savez_compressed(out/'expected.npz',vis_jy=vis,
                        uvw_m=g['uvw_lambda']*299792458/c['observation']['frequency_hz'],
                        times_mjd=g['times_mjd'],pairs=g['pairs'],weights=np.ones(vis.shape),expected_dirty_peak_xy=np.array([67,66]),expected_flux_jy=np.array(1000.))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    run(p.parse_args().output)
