"""Conditional Cas A array scale: known population shape and exact U3 rms."""
from copy import deepcopy
import hashlib,json
from pathlib import Path
import numpy as np
import astropy.units as u
from astropy.time import Time
from vsora_observation import validate_config
from vsora_observation.layouts import reference_layout
from vsora_observation.geometry import geometry_at_times
from vsora_observation.reference import reference_path
from vsora_simulator.sky import synthetic_sky
from vsora_simulator.visibility import direct_visibility
from vsora_simulator.sky_covariance import sky_station_covariance
from vsora_simulator.bispectrum_scale import known_bispectrum_moment_scale
from vsora_simulator.array_shape import population_closure_signature
from vsora_simulator.sensitivity import sefd_from_area,dish_area

MAXIMUM_BASELINES=(25.,50.,100.,200.,400.,600.)
LAYOUTS=('spread','line','ring')
EXPOSURES=(.3,3.)
BANDWIDTH=64000.


def run(output):
    out=Path(output)
    if out.exists():raise FileExistsError('new array tradeoff output required')
    out.mkdir(parents=True)
    config_asset=reference_path('known-array-scale-config.json')
    base=json.loads(config_asset.read_text())
    fixture_sha=hashlib.sha256(config_asset.read_bytes()).hexdigest()
    base['site']={'latitude_deg':35.,'longitude_deg':135.,'height_m':0.,'description':'Assumed public synthetic site'}
    base['source'].update(model='casa',frame='icrs',ra_deg=350.8664166662,dec_deg=58.8117777793,total_flux_jy=1000.)
    base['observation'].update(start_utc='2026-10-02T08:00:00Z',duration_s=600.,integration_s=60.,frequency_hz=1.42e9,elevation_min_deg=15.)
    base['image']={'pixels':64,'pixel_arcsec':16.}
    sky=synthetic_sky(base)
    point_config=deepcopy(base);point_config['source']['model']='point';point=synthetic_sky(point_config)
    reference=json.loads(reference_path('casa-template-jy-pixel.json').read_text())
    actual_sha=hashlib.sha256(reference_path().read_bytes()).hexdigest()
    if actual_sha!=reference['derived_sha256']:raise ValueError('scientific reference SHA mismatch')
    sefd_values=(1000.,10000.,sefd_from_area(100.,dish_area(1.,.6)))
    snapshots=[];cases=[];max_visibility_difference=0.;max_point_signature=0.
    for kind in LAYOUTS:
        for maximum in MAXIMUM_BASELINES:
            config=deepcopy(base)
            enu=reference_layout(8,kind,maximum)
            config['stations']=[{'id':f'ST{i+1:02d}','enu_m':p.tolist(),'sefd_jy':10000.} for i,p in enumerate(enu)]
            config=validate_config(config)
            geo=geometry_at_times(config,Time(config['observation']['start_utc'])+np.array([300.])*u.s,filter_elevation=False)
            pairs=geo['pairs'];coords=np.vstack((np.zeros((1,3)),geo['uvw_lambda'][0,:7]))
            assert np.array_equal(pairs[:7],np.c_[np.zeros(7,int),np.arange(1,8)])
            vis=direct_visibility(geo['uvw_lambda'],sky,16.)[0]
            point_vis=direct_visibility(geo['uvw_lambda'],point,16.)[0]
            sig=population_closure_signature(vis,pairs,1000.)
            point_sig=population_closure_signature(point_vis,pairs,1000.)
            max_point_signature=max(max_point_signature,point_sig['phase_maximum_abs_from_point'],point_sig['logamp_maximum_abs_from_point'])
            if max_point_signature>1e-12:raise RuntimeError('point source population closures failed')
            source=sky_station_covariance(coords,sky,16.,np.full(8,10000.))
            reconstructed=source['source_covariance_jy'][pairs[:,0],pairs[:,1]]
            difference=float(np.max(abs(reconstructed-vis)));max_visibility_difference=max(max_visibility_difference,difference)
            np.testing.assert_allclose(reconstructed,vis,rtol=1e-12,atol=1e-9)
            actual=float(np.linalg.norm(enu[:,None]-enu[None,:],axis=-1).max())
            if not np.isclose(actual,maximum,rtol=1e-14,atol=1e-12):raise RuntimeError('configured maximum pair distance failed')
            projected=float(np.linalg.norm(geo['uvw_lambda'][0,:,:2],axis=-1).max())
            snapshot_id=f'8-{kind}-{maximum:g}m'
            snapshots.append({'id':snapshot_id,'stations':8,'layout':kind,'maximum_baseline_m':maximum,
                'actual_maximum_pair_distance_m':actual,'station_enu_m':enu.tolist(),'station_uvw_lambda':coords.tolist(),
                'pairs':pairs.tolist(),'known_visibility_jy_real_imag':np.c_[vis.real,vis.imag].tolist(),
                'population_signature':sig,'point_population_signature_max_abs':max(point_sig['phase_maximum_abs_from_point'],point_sig['logamp_maximum_abs_from_point']),
                'maximum_projected_baseline_lambda':projected,'smallest_projected_fringe_period_arcsec':206264.80624709636/projected,
                'fringe_period_is_fitted_beam_resolution':False,
                'correlated_flux_fraction_minimum':float(np.min(abs(vis)/1000.)),
                'correlated_flux_fraction_median':float(np.median(abs(vis)/1000.)),
                'correlated_flux_fraction_maximum':float(np.max(abs(vis)/1000.)),
                'times_mjd':geo['times_mjd'].tolist(),'elevation_deg':geo['elevation_deg'].tolist(),
                'elevation_valid':geo['elevation_valid'].tolist(),'geometry_model':geo['model'],
                'eop_status':geo['eop_status'],'eop_warnings':geo['eop_warnings']})
            for sefd in sefd_values:
                known=sky_station_covariance(coords,sky,16.,np.full(8,sefd))
                for exposure in EXPOSURES:
                    samples=int(round(BANDWIDTH*exposure))
                    q=known_bispectrum_moment_scale(known['normalized_station_covariance'],samples)
                    scale=q['known_complex_rms_scale']
                    cases.append({'snapshot_id':snapshot_id,'maximum_baseline_m':maximum,'layout':kind,
                        'assumed_receiver_background_sefd_jy':sefd,'window_seconds':exposure,
                        'independent_samples_conditional_input':samples,'triangles':q['triangles'].tolist(),
                        'known_mean_real_imag':np.c_[q['mean'].real,q['mean'].imag].tolist(),
                        'known_complex_variance':q['complex_covariance'].diagonal().real.tolist(),
                        'known_complex_rms_scale':scale.tolist(),
                        'complex_rms_scale_minimum':float(scale.min()),'complex_rms_scale_median':float(np.median(scale)),
                        'complex_rms_scale_maximum':float(scale.max())})
    q={'type':'array_scale_known_sky_comparison','state':'complete','snapshots':snapshots,'conditional_scale_cases':cases,
        'config_fixture_sha256':fixture_sha,'reference':{'derived_sha256':actual_sha,'source_url':reference['source_url'],
            'paper_doi':reference['paper_doi'],'observed_epoch':reference['observed_epoch'],
            'observed_spectral_windows_mhz':reference['observed_spectral_windows_mhz'],
            'use':'2017 morphology proxy at assumed1.42GHz;1000Jy is separate assumption'},
        'assumed_public_site':base['site'],'assumed_source_icrs_deg':[350.8664166662,58.8117777793],
        'assumed_start_utc':base['observation']['start_utc'],'snapshot_offset_s':300.,'image_pixels':64,'image_pixel_arcsec':16.,
        'assumed_frequency_hz':1.42e9,'assumed_flux_jy':1000.,'assumed_channel_bandwidth_hz':BANDWIDTH,
        'maximum_sky_gram_vs_direct_visibility_difference_jy':max_visibility_difference,
        'maximum_point_population_signature_abs':max_point_signature,
        'independent_samples_equal_bandwidth_times_exposure_assumed':True,
        'known_source_self_noise_included':True,'gain_constant_and_lo_already_corrected_assumed':True,
        'population_closure_rms_is_image_information_rank':False,'triangles_assumed_independent':False,
        'detection_probability_calculated':False,'image_reconstructed':False,'optimal_array_selected':False,
        'actual_hardware_data':False,'actual_clock_or_temporal_independence_verified':False,
        'scope':'Single known epoch and known sky. Population point departures and exact known-S iid Gaussian U3 complex-rms scales use different statistics; no finite-sample closure likelihood, detection probability, image confidence or actual observation time.'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n')
    plot(q,out/'array-scale-tradeoff.png')
    return q


def plot(q,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(13.8,4.2))
    for kind,color in zip(LAYOUTS,('C0','C1','C2')):
        rows=[r for r in q['snapshots'] if r['layout']==kind];x=[r['maximum_baseline_m'] for r in rows]
        axes[0].plot(x,[r['correlated_flux_fraction_median'] for r in rows],'o-',label=kind,color=color)
        axes[1].plot(x,[r['population_signature']['logamp_rms_from_point'] for r in rows],'o-',color=color)
        rows=[r for r in q['conditional_scale_cases'] if r['layout']==kind and r['window_seconds']==.3 and r['assumed_receiver_background_sefd_jy']==10000.]
        axes[2].semilogy(x,[r['complex_rms_scale_median'] for r in rows],'o-',color=color)
    for ax in axes:ax.set_xlabel('Maximum all-pair baseline (m)');ax.grid(alpha=.2)
    axes[0].set(title='Known CasA: correlated fraction',ylabel='Median |V| / assumed1000Jy');axes[0].legend(fontsize=8)
    axes[1].set(title='Population departure from point',ylabel='All-row log closure amplitude RMS')
    axes[2].set(title='0.3s /64kHz /SEFD10000Jy',ylabel='Median |known B| /complex rms')
    fig.tight_layout();fig.savefig(path,dpi=130);plt.close(fig)


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    a=p.parse_args();q=run(a.output);print(json.dumps({'state':q['state'],'snapshots':len(q['snapshots']),'scale_cases':len(q['conditional_scale_cases'])}))


if __name__=='__main__':main()
