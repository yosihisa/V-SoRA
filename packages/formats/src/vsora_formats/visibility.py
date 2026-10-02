"""Development visibility interchange. Explicitly not FITS-IDI."""
import json
from pathlib import Path
import numpy as np


def save_visibility(path, geometry, vis, weights, metadata):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        raise FileExistsError(path.name)
    if vis.shape != geometry['uvw_lambda'].shape[:-1] or weights.shape != vis.shape:
        raise ValueError('visibility shape mismatch')
    np.savez_compressed(path, schema_version=np.array(1), uvw_lambda=geometry['uvw_lambda'],
                        vis_jy=vis, weights=weights, pairs=geometry['pairs'],
                        time_mjd=geometry['times_mjd'], metadata_json=np.array(json.dumps(metadata)))


def load_visibility(path):
    with np.load(path,allow_pickle=False) as f:
        result={k:f[k] for k in f.files}
    if int(result['schema_version'])!=1:
        raise ValueError('unsupported visibility schema')
    result['metadata']=json.loads(str(result.pop('metadata_json')))
    v,w,uvw=result['vis_jy'],result['weights'],result['uvw_lambda']
    if uvw.shape != (*v.shape,3) or w.shape!=v.shape or v.ndim!=2:
        raise ValueError('visibility shape mismatch')
    if any(not np.isfinite(x).all() for x in (v,w,uvw,result['time_mjd'])) or np.any(w<0):
        raise ValueError('nonfinite visibility or invalid weights')
    if result['pairs'].shape!=(v.shape[1],2) or result['time_mjd'].shape!=(v.shape[0],):
        raise ValueError('time/baseline shape mismatch')
    if np.any(result['pairs'][:,0]>=result['pairs'][:,1]) or np.any(np.diff(result['time_mjd'])<=0):
        raise ValueError('invalid baseline/time order')
    return result
