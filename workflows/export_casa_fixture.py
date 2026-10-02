"""Export an off-center point to reveal any baseline/conjugation mismatch."""
import argparse
from pathlib import Path
import numpy as np
from vsora_observation import load_config
from vsora_observation.geometry import observation_geometry
from vsora_simulator.visibility import direct_visibility
from vsora_formats.fitsidi import write_fitsidi


def run(output,channels=1):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1]
    c=load_config(root/'configs/experiments/ideal-point.json');g=observation_geometry(c)
    image=np.zeros((64,64));image[34,29]=1000  # west48", north32"
    frequency=None;geometry=g['uvw_lambda']
    if channels>1:
        frequency=c['observation']['frequency_hz']+(np.arange(channels)-channels//2)*c['observation']['bandwidth_hz']/channels
        geometry=g['uvw_lambda'][:,None,:,:]*(frequency[None,:,None,None]/c['observation']['frequency_hz'])
    vis=direct_visibility(geometry,image,16);weights=np.ones(vis.shape)
    if channels>1:
        weights*=np.linspace(1,2,channels)[None,:,None];weights[0,0,0]=0
    write_fitsidi(out/'point.fits',g,vis,weights,c,frequencies_hz=frequency)
    np.savez_compressed(out/'expected.npz',vis_jy=vis,
                        uvw_m=g['uvw_lambda']*299792458/c['observation']['frequency_hz'],
                        times_mjd=g['times_mjd'],pairs=g['pairs'],weights=weights,
                        frequencies_hz=np.array([c['observation']['frequency_hz']]) if frequency is None else frequency,
                        expected_dirty_peak_xy=np.array([67,66]),expected_flux_jy=np.array(1000.))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--channels',type=int,default=1)
    a=p.parse_args();run(a.output,a.channels)
