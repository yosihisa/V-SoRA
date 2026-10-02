"""Assumption-based short-exposure sensitivity; not measured receiver performance."""
from copy import deepcopy
import json
from pathlib import Path
import numpy as np
import astropy.units as u
from astropy.time import Time
from scipy.optimize import brentq
from vsora_observation import validate_config
from vsora_observation.geometry import geometry_at_times
from .sky import synthetic_sky
from .visibility import direct_visibility


BOLTZMANN_JY_M2_K=1.380649e3


def sefd_from_area(system_temperature_k,effective_area_m2):
    if not np.isfinite([system_temperature_k,effective_area_m2]).all() or min(system_temperature_k,effective_area_m2)<=0:
        raise ValueError('positive finite temperature and effective area required')
    return 2*BOLTZMANN_JY_M2_K*system_temperature_k/effective_area_m2


def dish_area(diameter_m,aperture_efficiency):
    if not np.isfinite([diameter_m,aperture_efficiency]).all() or diameter_m<=0 or not 0<aperture_efficiency<=1:
        raise ValueError('positive finite diameter and aperture efficiency <=1 required')
    return aperture_efficiency*np.pi*diameter_m**2/4


def baseline_sigma(sefd_jy,pairs,bandwidth_hz,integration_s,efficiency=1.,source_flux_jy=0.):
    sefd=np.asarray(sefd_jy,float)
    if (not np.isfinite(sefd).all() or np.any(sefd<=0)
        or not np.isfinite([bandwidth_hz,integration_s,efficiency,source_flux_jy]).all()
        or min(bandwidth_hz,integration_s,efficiency)<=0 or efficiency>1 or source_flux_jy<0):
        raise ValueError('invalid sensitivity parameters')
    power=sefd+source_flux_jy
    return np.sqrt(power[pairs[:,0]]*power[pairs[:,1]]/(2*bandwidth_hz*integration_s))/efficiency


def connected(edges,station_count):
    reached={0}
    while True:
        more={int(j) for i,j in edges if int(i) in reached}|{int(i) for i,j in edges if int(j) in reached}
        if more<=reached:return len(reached)==station_count
        reached|=more


def information_plan(config,integration_s=.3,bandwidth_hz=256000.,snapshots=16,min_snr=10.):
    from vsora_imaging.closure import form_closures,independent_closures
    c=validate_config(deepcopy(config))
    if not .1<=integration_s<=3 or not 0<bandwidth_hz<=2048000 or not isinstance(snapshots,int) or not 4<=snapshots<=32 or not 5<=min_snr<=100:
        raise ValueError('reference exposure/bandwidth/snapshot/SNR range exceeded')
    c['image']['pixels']=32
    offsets=(np.arange(snapshots)+.5)*c['observation']['duration_s']/snapshots
    geometry=geometry_at_times(c,Time(c['observation']['start_utc'])+offsets*u.s)
    sky=synthetic_sky(c);v=direct_visibility(geometry['uvw_lambda'],sky,c['image']['pixel_arcsec'])
    pairs=geometry['pairs'];sefd=np.array([s['sefd_jy'] for s in c['stations']])
    sigma=baseline_sigma(sefd,pairs,bandwidth_hz,integration_s,c['noise']['efficiency'],float(sky.sum()))
    closures=form_closures(v,np.broadcast_to(1/sigma**2,v.shape),pairs,min_snr=min_snr)
    rows=[]
    for t in range(len(v)):
        counts={}
        for kind in ('phase','logamp'):
            selected,_=independent_closures(closures[kind+'_matrix'],closures[kind+'_valid'][t],closures['baseline_variance'][t])
            counts[kind]=len(selected)
        rows.append({'offset_s':float((Time(geometry['times_mjd'][t],format='mjd')-Time(c['observation']['start_utc'])).sec),'independent_phase':counts['phase'],'independent_logamp':counts['logamp'],
                     'baselines_above_threshold':int(closures['baseline_valid'][t].sum()),
                     'high_snr_graph_connected':connected(pairs[closures['baseline_valid'][t]],len(sefd))})
    allowed=float(brentq(lambda x:np.sinc(x)-.9,0.,.5)/integration_s)
    return {'type':'sensitivity_plan','config':c,'assumptions':{'integration_s':integration_s,'bandwidth_per_closure_channel_hz':bandwidth_hz,
        'snapshots':snapshots,'min_baseline_snr':min_snr,'station_sefd_jy':sefd.tolist(),
        'assumed_source_total_flux_jy':float(sky.sum()),'gain_and_lo':'Gain constant within exposure; LO/clock already corrected',
        'noise':'Gaussian quadrature-average including source total power; inter-baseline self-noise covariance excluded'},
        'baseline_noise_jy':{'minimum':float(sigma.min()),'maximum':float(sigma.max())},
        'expected_correlated_flux_jy':{'minimum':float(abs(v).min()),'median':float(np.median(abs(v))),'maximum':float(abs(v).max())},
        'expected_baseline_snr':{'minimum':float(closures['baseline_snr'].min()),'median':float(np.median(closures['baseline_snr'])),'maximum':float(closures['baseline_snr'].max())},
        'independent_closure_counts':{'phase':sum(x['independent_phase'] for x in rows),'logamp':sum(x['independent_logamp'] for x in rows)},
        'high_snr_connected_snapshots':sum(x['high_snr_graph_connected'] for x in rows),
        'retained_snapshots':len(v),'recorded_exposure_per_station_s':len(v)*integration_s,
        'maximum_residual_baseline_rate_hz_for_90pct_coherence':allowed,'rows':rows,
        'limits':'Expected noiseless SNR counts, not random detection probabilities or rate-search success. No image reconstructed. Assumed SEFD/beam/sky; single coherent closure channel; no measured RTL-SDR performance.'}


def write_plan(config,output,**settings):
    out=Path(output)
    if out.exists():raise FileExistsError('new sensitivity output required')
    result=information_plan(config,**settings);out.mkdir(parents=True)
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=result['rows'];t=[x['offset_s']/3600 for x in rows]
    fig,ax=plt.subplots(figsize=(8,3.8))
    ax.plot(t,[x['independent_phase'] for x in rows],'o-',label='Closure phase')
    ax.plot(t,[x['independent_logamp'] for x in rows],'s-',label='Log closure amplitude')
    ax.set(xlabel='Hours from start',ylabel='Expected independent constraints / channel')
    ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(out/'sensitivity.png',dpi=130);plt.close(fig)
    return result


def main():
    import argparse
    from vsora_observation import load_config
    p=argparse.ArgumentParser(description='Expected short-exposure Closure information from assumed SEFD')
    p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    p.add_argument('--integration-s',type=float,default=.3);p.add_argument('--bandwidth-hz',type=float,default=256000.)
    a=p.parse_args();print(json.dumps(write_plan(load_config(a.config),a.output,integration_s=a.integration_s,bandwidth_hz=a.bandwidth_hz),indent=2))


if __name__=='__main__':main()
