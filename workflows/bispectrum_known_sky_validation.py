"""Known discrete-sky U3 moments and conditional complex-rms scale."""
from copy import deepcopy
import hashlib,json
from pathlib import Path
import numpy as np
import astropy.units as u
from astropy.time import Time
from vsora_observation import validate_config
from vsora_observation.geometry import geometry_at_times
from vsora_observation.reference import reference_path
from vsora_simulator.sky import synthetic_sky
from vsora_simulator.sky_covariance import sky_station_covariance
from vsora_simulator.bispectrum_scale import known_bispectrum_moment_scale
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum
from vsora_simulator.sensitivity import sefd_from_area,dish_area

EXPOSURES=(.1,.3,1.,3.)
BANDWIDTH=64000.
LAYOUTS=('spread','line','ring')
SHAPES=('point','casa')
CONFIGURATION_ROOT=Path(__file__).resolve().parents[1]


def station_layout(stations,kind):
    if isinstance(stations,bool) or not isinstance(stations,(int,np.integer)) or stations not in (4,8) or kind not in LAYOUTS:
        raise ValueError('known4/8station spread/line/ring layout required')
    if kind=='line':return np.c_[np.linspace(-300,300,stations),np.zeros((stations,2))]
    if kind=='ring':
        angle=np.arange(stations)*2*np.pi/stations
        return np.c_[300*np.cos(angle),300*np.sin(angle),np.zeros(stations)]
    points=np.array([[-200,-130,0],[-180,-100,0],[160,-180,0],[220,170,0],[-240,160,0],[-40,40,0],[40,-80,0],[180,20,0]],float)[:stations]
    return points*600/np.linalg.norm(points[:,None]-points[None,:],axis=-1).max()


def moment_comparison(values,mean,covariance):
    if any(np.ma.isMaskedArray(v) for v in (values,mean,covariance)):raise ValueError('unmasked moments required')
    values=np.asarray(values);mean=np.asarray(mean);covariance=np.asarray(covariance)
    if (values.ndim!=2 or len(values)<2 or not np.iscomplexobj(values) or mean.shape!=(values.shape[1],)
        or covariance.shape!=(2*values.shape[1],2*values.shape[1]) or np.iscomplexobj(covariance)
        or not np.isfinite(values).all() or not np.isfinite(mean).all() or not np.isfinite(covariance).all()):raise ValueError('finite complex trial values and matching real covariance required')
    residual=values-mean;parts=np.c_[residual.real,residual.imag];trials=len(parts)
    observed_mean=parts.mean(axis=0);mean_se=parts.std(axis=0,ddof=1)/np.sqrt(trials)
    total=np.zeros_like(covariance);squared=np.zeros_like(covariance)
    for start in range(0,trials,64):
        chunk=parts[start:start+64];products=chunk[:,:,None]*chunk[:,None,:]
        total+=products.sum(axis=0);squared+=(products**2).sum(axis=0)
    observed=total/trials
    variance=np.maximum((squared-total*observed)/(trials-1),0.)
    se=np.sqrt(variance/trials)
    rounding=1e-12*max(1.,float(np.max(abs(covariance))))
    passed=bool(np.all(abs(observed_mean)<=6*mean_se+rounding) and np.all(abs(observed-covariance)<=6*se+rounding))
    return {'trials':trials,'known_mean_real_imag':np.c_[mean.real,mean.imag].tolist(),
        'mean_residual_all_real_then_imag':observed_mean.tolist(),'mean_mc_standard_error':mean_se.tolist(),
        'known_real_covariance':covariance.tolist(),'observed_residual_second_moment':observed.tolist(),
        'covariance_mc_standard_error':se.tolist(),'all_means_and_covariances_within_6se':passed,
        'covariance_product_chunk_trials':64,'full_trial_product_tensor_allocated':False}


def experiment(s,seed,trials=8192):
    if isinstance(trials,bool) or not isinstance(trials,int) or not 1024<=trials<=32768:
        raise ValueError('integer trials1024..32768 required')
    if isinstance(seed,bool) or not isinstance(seed,(int,np.integer)) or not 0<=seed<=2**32-1:raise ValueError('integer seed0..2**32-1 required')
    theory=known_bispectrum_moment_scale(s,128);root=np.linalg.cholesky(s);rng=np.random.default_rng(seed);values=[]
    for start in range(0,trials,64):
        count=min(64,trials-start);shape=(count,128,len(s))
        z=(rng.normal(size=shape)+1j*rng.normal(size=shape))/np.sqrt(2)
        values.append(distinct_sample_bispectrum(z @ root.T)['distinct_sample_bispectrum'])
    return {'seed':seed,'samples':128,'triangles':theory['triangles'].tolist(),
        'normalized_station_covariance_real_imag':np.stack((s.real,s.imag),axis=-1).tolist(),
        **moment_comparison(np.concatenate(values),theory['mean'],theory['real_covariance'])}


def run(output,trials=8192):
    if isinstance(trials,bool) or not isinstance(trials,int) or not 1024<=trials<=32768:
        raise ValueError('integer trials1024..32768 required')
    out=Path(output)
    if out.exists():raise FileExistsError('new known-sky validation output required')
    out.mkdir(parents=True)
    root=CONFIGURATION_ROOT
    base=json.loads((root/'configs/experiments/ideal-point.json').read_text())
    fixture_sha=hashlib.sha256((root/'configs/experiments/ideal-point.json').read_bytes()).hexdigest()
    base['site']={'latitude_deg':35.,'longitude_deg':135.,'height_m':0.,'description':'Assumed public synthetic site'}
    base['source'].update(frame='icrs',ra_deg=350.8664166662,dec_deg=58.8117777793,total_flux_jy=1000.)
    base['observation'].update(start_utc='2026-10-02T08:00:00Z',duration_s=600.,integration_s=60.,frequency_hz=1.42e9,elevation_min_deg=15.)
    base['image']={'pixels':64,'pixel_arcsec':16.}
    reference=json.loads(reference_path('casa-template-jy-pixel.json').read_text())
    actual_sha=hashlib.sha256(reference_path().read_bytes()).hexdigest()
    if actual_sha!=reference['derived_sha256']:raise ValueError('scientific reference SHA mismatch')
    images={}
    for shape in SHAPES:
        config=deepcopy(base);config['source']['model']=shape
        images[shape]=synthetic_sky(config)
    sefd_values=(10000.,100000.,sefd_from_area(100.,dish_area(1.,.6)))
    snapshots=[];cases=[];mc_inputs={};representatives=[]
    for stations in (4,8):
        for layout in LAYOUTS:
            config=deepcopy(base);config['stations']=[{'id':f'ST{i+1:02d}','enu_m':p.tolist(),'sefd_jy':10000.} for i,p in enumerate(station_layout(stations,layout))]
            config=validate_config(config)
            geo=geometry_at_times(config,Time(config['observation']['start_utc'])+np.array([300.])*u.s,filter_elevation=False)
            assert np.array_equal(geo['pairs'][:stations-1],np.c_[np.zeros(stations-1,int),np.arange(1,stations)])
            coords=np.vstack((np.zeros((1,3)),geo['uvw_lambda'][0,:stations-1]))
            for shape in SHAPES:
                snapshot_id=f'{stations}-{layout}-{shape}'
                source=sky_station_covariance(coords,images[shape],config['image']['pixel_arcsec'],np.full(stations,sefd_values[0]))
                skycov=source['source_covariance_jy']
                snapshots.append({'id':snapshot_id,'stations':stations,'layout':layout,'shape_model':shape,
                    'station_enu_m':[s['enu_m'] for s in config['stations']],
                    'station_uvw_lambda':coords.tolist(),'source_covariance_jy_real_imag':np.stack((skycov.real,skycov.imag),axis=-1).tolist(),
                    'times_mjd':geo['times_mjd'].tolist(),'elevation_deg':geo['elevation_deg'].tolist(),'elevation_valid':geo['elevation_valid'].tolist(),
                    'geometry_model':geo['model'],'eop_status':geo['eop_status'],'eop_warnings':geo['eop_warnings']})
                if layout=='spread' and (stations,shape) in ((4,'point'),(4,'casa'),(8,'casa')):
                    mc_inputs[(stations,shape)]=source['normalized_station_covariance']
                for sefd in sefd_values:
                    known=sky_station_covariance(coords,images[shape],config['image']['pixel_arcsec'],np.full(stations,sefd))
                    for exposure in EXPOSURES:
                        samples=int(round(BANDWIDTH*exposure));q=known_bispectrum_moment_scale(known['normalized_station_covariance'],samples)
                        record={'snapshot_id':snapshot_id,'stations':stations,'layout':layout,'shape_model':shape,
                            'assumed_receiver_background_sefd_jy':sefd,'assumed_total_flux_jy':1000.,'window_seconds':exposure,
                            'assumed_channel_bandwidth_hz':BANDWIDTH,'independent_samples_conditional_input':samples,
                            'triangles':q['triangles'].tolist(),'known_mean_real_imag':np.c_[q['mean'].real,q['mean'].imag].tolist(),
                            'known_complex_variance':q['complex_covariance'].diagonal().real.tolist(),
                            'complex_to_null_variance_ratio':q['complex_to_null_variance_ratio'].tolist(),
                            'known_complex_rms_scale':q['known_complex_rms_scale'].tolist(),
                            'required_identical_independent_windows':q['required_identical_independent_windows'],
                            'conditional_window_count_state':q['conditional_window_count_state'],
                            'conditional_recorded_seconds_same_s_and_uv':[None if n is None else n*exposure for n in q['required_identical_independent_windows']],
                            'target_complex_rms_scale':q['target_complex_rms_scale']}
                        cases.append(record)
                        if layout=='spread' and shape=='casa' and sefd==sefd_values[0] and exposure==.3:
                            representatives.append({'snapshot_id':snapshot_id,'samples':samples,'assumed_receiver_background_sefd_jy':sefd,
                                'triangles':q['triangles'].tolist(),'real_parameter_order':q['real_parameter_order'],
                                'known_real_covariance':q['real_covariance'].tolist()})
    mc=[]
    for index,key in enumerate(((4,'point'),(4,'casa'),(8,'casa'))):
        mc.append({'stations':key[0],'shape_model':key[1],**experiment(mc_inputs[key],76+index,trials)})
    passed=all(row['all_means_and_covariances_within_6se'] for row in mc)
    q={'type':'known_sky_bispectrum_scale_validation','state':'complete' if passed else 'failed_validation',
        'conditional_forecasts':cases,'snapshots':snapshots,'representative_joint_covariances':representatives,'monte_carlo_cases':mc,
        'config_fixture_sha256':fixture_sha,'assumed_public_site':{'latitude_deg':35.,'longitude_deg':135.,'height_m':0.},
        'assumed_source_icrs_deg':[350.8664166662,58.8117777793],'snapshot_offset_s':300.,'image_pixels':64,'image_pixel_arcsec':16.,
        'trials_per_mc_case':trials,'assumed_frequency_hz':1.42e9,'assumed_flux_jy':1000.,'channel_bandwidth_hz':BANDWIDTH,
        'scale_definition':'abs(known B)/sqrt(E abs(U3-B)^2); complex rms, not one quadrature SNR',
        'conditional_count_limit':10**18,'nominal_bandwidth_time_count_assumed_independent':True,
        'same_sky_covariance_and_uv_repeated_assumed':True,'gain_constant_and_lo_already_corrected_assumed':True,
        'source_power_added_to_receiver_background':True,'source_self_noise_included_in_known_covariance':True,
        'triangles_statistically_independent_assumed':False,'observed_power_normalization_performed':False,
        'gaussian_detection_probability_calculated':False,'actual_temporal_independence_verified':False,
        'physical_adc_vdif_processed':False,'real_hardware_validation_performed':False,'image_reconstructed':False,'production_rml_noise_model_changed':False,
        'reference':{'derived_sha256':actual_sha,'source_url':reference['source_url'],'paper_doi':reference['paper_doi'],
            'observed_epoch':reference['observed_epoch'],'observed_spectral_windows_mhz':reference['observed_spectral_windows_mhz'],
            'single_reference_frequency_hz':reference['single_reference_frequency_hz'],'use':'Morphology proxy at assumed1.42GHz, total flux1000Jy is independent assumption'},
        'scope':'Known nonnegative discrete sky, independent receiver/background power, iid proper Gaussian voltage and fixed corrected gains. No measured SEFD, observed normalization, actual FFT/clocks, detection probability, varying uv observation time or image confidence.'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n');plot(q,images,out/'known-sky-bispectrum.png')
    if not passed:raise RuntimeError('known sky U3 moments outside fixed6SE criterion')
    return q


def plot(q,images,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(13.5,4.4))
    axes[0].imshow(images['casa'],origin='lower',cmap='inferno');axes[0].set(title='CasA morphology proxy; assumed1000Jy',xlabel='Model pixel',ylabel='Model pixel')
    for shape,style in [('point','-'),('casa','--')]:
        for stations,color in [(4,'C0'),(8,'C1')]:
            rows=[r for r in q['conditional_forecasts'] if r['shape_model']==shape and r['stations']==stations and r['layout']=='spread' and r['window_seconds']==.3]
            x=[r['assumed_receiver_background_sefd_jy'] for r in rows]
            axes[1].loglog(x,[np.median(r['known_complex_rms_scale']) for r in rows],style+'o',color=color,label=f'{stations}stations {shape}')
            axes[2].loglog(x,[np.median(r['complex_to_null_variance_ratio']) for r in rows],style+'o',color=color)
    axes[1].set(title='0.3s,64kHz, known spread layout',xlabel='Assumed receiver/background SEFD(Jy)',ylabel='Median |B| / complex rms, all triangles');axes[1].legend(fontsize=8)
    axes[2].set(title='Source-inclusive / null complex variance',xlabel='Assumed receiver/background SEFD(Jy)',ylabel='Median variance ratio, all triangles')
    for axis in axes[1:]:axis.grid(alpha=.2)
    fig.suptitle('Known iid Gaussian voltage; medians do not count independent information; no detection or image guarantee',fontsize=10)
    fig.tight_layout();fig.savefig(path,dpi=140);plt.close(fig)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--trials',type=int,default=8192)
    q=run(**vars(p.parse_args()));print(json.dumps({'state':q['state'],'forecasts':len(q['conditional_forecasts']),'mc_cases':len(q['monte_carlo_cases'])}))
