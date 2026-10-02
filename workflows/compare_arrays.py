"""Reproducible array comparison; no optimum is claimed from this small grid."""
import argparse
import copy
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from vsora_observation import load_config,validate_config
from vsora_observation.geometry import observation_geometry
from vsora_simulator.__main__ import simulate
from vsora_imaging.__main__ import image_visibility,compare_models
from astropy.io import fits


def layout(n,kind):
    if kind=='line':
        return [[float(x),0.,0.] for x in np.linspace(-300,300,n)]
    if kind=='ring':
        a=np.arange(n)*2*np.pi/n
        return np.column_stack([300*np.cos(a),300*np.sin(a),np.zeros(n)]).tolist()
    # Explicit nonregular 2D layout with a short baseline; rescale max to 600m.
    points=np.array([[-200,-130,0],[-180,-100,0],[160,-180,0],[220,170,0],
                     [-240,160,0],[-40,40,0],[40,-80,0],[180,20,0]],float)[:n]
    distances=np.linalg.norm(points[:,None]-points[None,:],axis=-1)
    return (points*600/distances.max()).tolist()


def run(output):
    root=Path(__file__).resolve().parents[1]
    base=load_config(root/'configs/experiments/ideal-point.json')
    target=Path(output)
    if target.exists(): raise FileExistsError('use a new output directory')
    target.mkdir(parents=True)
    cases=[('4-short-ideal',4,'spread',600,False,1e4),
           ('4-long-ideal',4,'spread',14400,False,1e4),
           ('8-long-ideal',8,'spread',14400,False,1e4),
           ('8-line-ideal',8,'line',14400,False,1e4),
           ('8-ring-ideal',8,'ring',14400,False,1e4),
           ('8-long-noise-low',8,'spread',14400,True,1e4),
           ('8-long-noise-high',8,'spread',14400,True,1e6)]
    summaries=[]
    for name,n,kind,duration,noisy,sefd in cases:
        c=copy.deepcopy(base);c['source']['model']='casa'
        c['observation']['duration_s']=duration;c['observation']['integration_s']=120 if duration>600 else 60
        c['noise']['enabled']=noisy
        c['stations']=[{'id':f'ST{i+1:02d}','enu_m':p,'sefd_jy':sefd} for i,p in enumerate(layout(n,kind))]
        c=validate_config(c)
        directory=target/name
        vispath=simulate(c,directory/'simulation')
        result=image_visibility(vispath,directory/'imaging',clean_radius_arcsec=220)
        truth=np.load(directory/'simulation/truth.npy')
        model=fits.getdata(directory/'imaging/model.fits').astype(float)
        metrics,a,b=compare_models(truth,model,16)
        result.update(metrics);result.update({'case':name,'stations':n,'layout':kind,
                                             'duration_s':duration,'noise':noisy,'sefd_jy':sefd})
        g=observation_geometry(c)
        uv=g['uvw_lambda'].reshape(-1,3)
        lengths=np.linalg.norm(np.array(layout(n,kind))[:,None]-np.array(layout(n,kind))[None,:],axis=-1)
        result['shortest_baseline_m']=float(lengths[lengths>0].min())
        result['longest_baseline_m']=float(lengths.max())
        fig,axes=plt.subplots(1,4,figsize=(14,3.5))
        axes[0].scatter(uv[:,0],uv[:,1],s=.5);axes[0].scatter(-uv[:,0],-uv[:,1],s=.5)
        axes[0].set_aspect('equal');axes[0].set_title('uv (wavelengths)')
        vmax=a.max()
        for ax,title,image in zip(axes[1:],['Truth, common beam','CLEAN model, common beam','Difference'],[a,b,b-a]):
            im=ax.imshow(image,origin='lower',cmap='inferno',vmin=0 if title!='Difference' else -vmax,vmax=vmax)
            ax.set_title(title);fig.colorbar(im,ax=ax,shrink=.7)
        fig.suptitle(name+f" | NRMSE={metrics['nrmse']:.3f}, corr={metrics['correlation']:.3f}")
        fig.tight_layout();fig.savefig(directory/'comparison.png',dpi=120);plt.close(fig)
        (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        summaries.append(result)
        print(name,json.dumps({k:result[k] for k in ['nrmse','correlation','model_flux_ratio','converged','thermal_image_sigma_jy']}),flush=True)
    (target/'summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
    return summaries


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    a=p.parse_args();run(a.output)
