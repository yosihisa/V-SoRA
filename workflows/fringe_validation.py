"""Known point calibrator -> inferred gains -> independent Cas A visibility."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from vsora_observation import load_config
from vsora_observation.geometry import observation_geometry
from vsora_simulator.sky import casa_sky
from vsora_simulator.visibility import direct_visibility
from vsora_correlator.fringe import solve_fringe,apply_calibration,save_calibration
from vsora_formats.spectral import save_spectral
from workflows.compare_arrays import layout


def run(output,seeds=5):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1]
    config=load_config(root/'configs/experiments/ideal-point.json')
    config['stations']=[{'id':f'ST{i+1:02d}','enu_m':position,'sefd_jy':1e4}
                        for i,position in enumerate(layout(8,'spread'))]
    g=observation_geometry(config)
    t=np.arange(64)*.02;fc=config['observation']['frequency_hz']
    f=fc+np.arange(-32,32)*32000;nb=len(g['pairs'])
    uvw=g['uvw_lambda'][0][None,None,:,:]*(f[None,:,None,None]/fc)
    uvw=np.broadcast_to(uvw,(len(t),len(f),nb,3)).copy()
    point=np.ones((len(t),len(f),nb),complex)*1000
    image=casa_sky(config)
    target=np.broadcast_to(direct_visibility(uvw[0],image,config['image']['pixel_arcsec']),point.shape).copy()
    truth={'amplitude':np.array([1,.8,1.2,.95,1.05,.9,1.1,.85]),
           'phase_rad':np.array([0,.4,-.7,1.4,-1.8,.8,-.2,2.2]),
           'delay_s':np.array([0,2.3e-6,-1.7e-6,.38e-6,3.1e-6,-2.5e-6,.7e-6,-.9e-6]),
           'rate_hz':np.array([0,2.7,-1.3,4.1,-6.2,.4,1.7,-3.1])}
    # Forward errors expressed here independently of calibration.py application.
    response=truth['amplitude']*np.exp(1j*(truth['phase_rad']+2*np.pi*(
        (t[:,None,None]-t.mean())*truth['rate_hz']+(f[None,:,None]-f.mean())*truth['delay_s'])))
    p=g['pairs'];factor=response[...,p[:,0]]*response[...,p[:,1]].conj()
    sigma=100.;results=[]
    for seed in range(seeds):
        rng=np.random.default_rng(300+seed)
        noise=lambda:rng.normal(size=point.shape)+1j*rng.normal(size=point.shape)
        measured=point*factor+sigma*noise();measured_target=target*factor+sigma*noise()
        weights=np.full(point.shape,1/sigma**2);weights[::7,:8]=0
        cal=solve_fringe(measured,point,weights,p,t,f)
        corrected,cw=apply_calibration(measured_target,weights,p,cal,t,f)
        def averaged(v,w): return np.sum(v*w,axis=(0,1))/np.sum(w,axis=(0,1))
        before=averaged(measured_target,weights);after=averaged(corrected,cw)
        expected=averaged(target,cw)
        row={'seed':300+seed,'sigma_per_component_jy':sigma,
             'delay_max_error_s':float(np.max(abs(np.array(cal['delay_s'])-truth['delay_s']))),
             'rate_max_error_hz':float(np.max(abs(np.array(cal['rate_hz'])-truth['rate_hz']))),
             'amplitude_max_relative_error':float(np.max(abs(np.array(cal['amplitude'])/truth['amplitude']-1))),
             'before_averaged_visibility_relative_error':float(np.linalg.norm(before-expected)/np.linalg.norm(expected)),
             'after_averaged_visibility_relative_error':float(np.linalg.norm(after-expected)/np.linalg.norm(expected)),
             'fit_relative_residual':cal['weighted_fit_relative_residual']}
        if row['after_averaged_visibility_relative_error']>.03 or row['delay_max_error_s']>1e-8 or row['rate_max_error_hz']>.02:
            raise AssertionError('known-model calibration validation failed')
        results.append(row)
        if seed==0:
            save_calibration(out/'calibration.json',cal)
            save_spectral(out/'target-uncorrected.npz',{'vis_jy':measured_target,'weights':weights,
                          'pairs':p,'times_s':t,'frequencies_hz':f,'uvw_lambda':uvw},
                          {'time_origin_utc':config['observation']['start_utc'],'unit':'Jy',
                           'condition':'stationary short-interval geometry, analytic visibility noise'})
            save_spectral(out/'target-corrected.npz',{'vis_jy':corrected,'weights':cw,
                          'pairs':p,'times_s':t,'frequencies_hz':f,'uvw_lambda':uvw},
                          {'time_origin_utc':config['observation']['start_utc'],'unit':'Jy'})
            fig,axes=plt.subplots(1,2,figsize=(10,4))
            axes[0].scatter(expected.real,before.real,label='Before',s=20)
            axes[0].scatter(expected.real,after.real,label='After',s=20)
            lo,hi=expected.real.min(),expected.real.max();axes[0].plot([lo,hi],[lo,hi],'k--')
            axes[0].set(xlabel='Model real visibility (Jy)',ylabel='Measured mean (Jy)');axes[0].legend()
            for values,label in [(measured[...,0],'Before'),(measured[...,0]/factor[...,0],'True correction'),
                                  (apply_calibration(measured,weights,p,cal,t,f)[0][...,0],'Fitted correction')]:
                axes[1].plot(t,np.angle(values[:,32]),'.',label=label)
            axes[1].set(xlabel='Time (s)',ylabel='Point-source phase (rad)');axes[1].legend()
            fig.tight_layout();fig.savefig(out/'comparison.png',dpi=140);plt.close(fig)
    summary={'schema_version':1,'stations':8,'channels':64,'time_samples':64,'time_step_s':.02,
             'duration_span_s':float(np.ptp(t)),'frequency_step_hz':32000,
             'delay_alias_period_s':1/32000,'rate_alias_period_hz':50,
             'calibrator':'Known 1000 Jy phase-center point, separate synthetic observation',
             'target':'Cas A template, identical stable receiver response over this interval',
             'results':results,'limitations':['Analytic visibility errors, not continuous IQ in this stage',
                         'No calibration transfer across different times/directions',
                         'Flux known, constant gain/delay/rate, stationary geometry']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--seeds',type=int,default=5)
    a=p.parse_args();run(a.output,a.seeds)
