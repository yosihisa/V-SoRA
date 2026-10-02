"""Time/channel/baseline development profile, preserving fringe information."""
import json
from pathlib import Path
import numpy as np


def validate_spectral(data):
    key='visibilities' if 'visibilities' in data else 'vis_jy'
    v,w,p,t,f,uvw=(np.asarray(data[k]) for k in (key,'weights','pairs','times_s','frequencies_hz','uvw_lambda'))
    if v.ndim!=3 or w.shape!=v.shape or uvw.shape!=(*v.shape,3): raise ValueError('invalid spectral shape')
    if t.shape!=(v.shape[0],) or f.shape!=(v.shape[1],) or p.shape!=(v.shape[2],2): raise ValueError('invalid spectral axes')
    if any(not np.isfinite(a).all() for a in (v,w,t,f,uvw)) or np.any(w<0): raise ValueError('invalid spectral values')
    if np.any(np.diff(t)<=0) or np.any(np.diff(f)<=0) or np.any(f<=0): raise ValueError('spectral axes must increase')
    if not np.issubdtype(p.dtype,np.integer) or np.any(p<0) or np.any(p[:,0]>=p[:,1]): raise ValueError('invalid spectral pairs')
    if len(np.unique(p,axis=0))!=len(p): raise ValueError('duplicate spectral pairs')
    if not np.iscomplexobj(v): raise ValueError('complex visibility required')
    return data


def save_spectral(path,data,metadata):
    validate_spectral(data);p=Path(path)
    if p.exists(): raise FileExistsError(p.name)
    p.parent.mkdir(parents=True,exist_ok=True)
    unit=metadata.get('visibility_unit',metadata.get('unit'))
    if unit not in ('Jy','ADC^2'): raise ValueError('visibility_unit must be Jy or ADC^2')
    values=data.get('visibilities',data.get('vis_jy'))
    stored={k:v for k,v in data.items() if k not in ('visibilities','vis_jy')}
    np.savez_compressed(p,schema_version=np.array(2),metadata_json=np.array(json.dumps({**metadata,'visibility_unit':unit})),
                        visibilities=values,**stored)


def load_spectral(path):
    with np.load(path,allow_pickle=False) as f: data={k:f[k] for k in f.files}
    version=int(data.pop('schema_version'))
    if version not in (1,2): raise ValueError('unsupported spectral profile')
    data['metadata']=json.loads(str(data.pop('metadata_json')))
    if version==1:
        data['visibilities']=data.pop('vis_jy');data['metadata']['visibility_unit']='Jy'
    unit=data['metadata']['visibility_unit']
    if unit not in ('Jy','ADC^2'): raise ValueError('unsupported visibility unit')
    if unit=='Jy': data['vis_jy']=data['visibilities']
    return validate_spectral(data)
