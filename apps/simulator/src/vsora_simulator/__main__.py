import argparse
import json
from pathlib import Path
import numpy as np
from vsora_observation import load_config
from vsora_observation.geometry import observation_geometry
from vsora_formats.visibility import save_visibility
from .sky import synthetic_sky
from .visibility import direct_visibility, thermal_noise


def simulate(config, output):
    out=Path(output)
    if out.exists():
        raise FileExistsError('output directory already exists; use a new run directory')
    image=synthetic_sky(config)
    geometry=observation_geometry(config)
    vis=direct_visibility(geometry['uvw_lambda'],image,config['image']['pixel_arcsec'])
    noise,sigma=thermal_noise(config,geometry['pairs'],vis.shape)
    if config['noise']['enabled']:
        vis=vis+noise
    weights=1/sigma**2
    out.mkdir(parents=True)
    np.save(out/'truth.npy',image)
    meta={k:v for k,v in geometry.items() if not isinstance(v,np.ndarray)}
    meta.update({'config':config,'frequency_hz':config['observation']['frequency_hz'],
                 'polarization':'ideal single co-polarization flux convention',
                 'sigma_real_imag_jy':sigma[0].tolist(),
                 'assumptions':['single center frequency; no bandwidth averaging',
                                'midpoint samples; no integration smearing',
                                'unit primary beam; no calibration errors']})
    save_visibility(out/'visibility.npz',geometry,vis,weights,meta)
    (out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    (out/'geometry.json').write_text(json.dumps(meta,indent=2)+'\n')
    return out/'visibility.npz'


def main():
    p=argparse.ArgumentParser(description='Ideal visibility simulator')
    p.add_argument('--config',required=True)
    p.add_argument('--output',required=True)
    a=p.parse_args()
    print(simulate(load_config(a.config),a.output))


if __name__=='__main__':
    main()
