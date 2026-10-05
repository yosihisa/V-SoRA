"""Known-sky APIs and scientific reference checked outside source checkout."""
import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path


def run(output,reference):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False);record=Path(reference).resolve()
    script='''
import hashlib,json,sys
from pathlib import Path
import numpy as np
from vsora_simulator import sky_covariance,bispectrum_scale,sky
from vsora_observation import reference as asset
prefix=Path(sys.prefix)
assert all(Path(m.__file__).is_relative_to(prefix) for m in (sky_covariance,bispectrum_scale,sky,asset))
assert asset.reference_path().is_relative_to(prefix)
q=json.loads(Path(sys.argv[1]).read_text())
assert hashlib.sha256(asset.reference_path().read_bytes()).hexdigest()==q['reference']['derived_sha256']
config={'source':{'ra_deg':q['assumed_source_icrs_deg'][0],'dec_deg':q['assumed_source_icrs_deg'][1],'model':'point','total_flux_jy':1000.},'image':{'pixels':q['image_pixels'],'pixel_arcsec':q['image_pixel_arcsec']}}
images={}
for shape in ('point','casa'):
 config['source']['model']=shape;images[shape]=sky.synthetic_sky(config)
snapshots={s['id']:s for s in q['snapshots']};checked=0
for case in q['conditional_forecasts']:
 snapshot=snapshots[case['snapshot_id']];n=case['stations']
 known=sky_covariance.sky_station_covariance(snapshot['station_uvw_lambda'],images[case['shape_model']],q['image_pixel_arcsec'],np.full(n,case['assumed_receiver_background_sefd_jy']))
 theory=bispectrum_scale.known_bispectrum_moment_scale(known['normalized_station_covariance'],case['independent_samples_conditional_input'])
 np.testing.assert_array_equal(np.c_[theory['mean'].real,theory['mean'].imag],case['known_mean_real_imag'])
 np.testing.assert_array_equal(theory['complex_covariance'].diagonal().real,case['known_complex_variance'])
 np.testing.assert_array_equal(theory['known_complex_rms_scale'],case['known_complex_rms_scale'])
 assert theory['required_identical_independent_windows']==case['required_identical_independent_windows']
 assert theory['conditional_window_count_state']==case['conditional_window_count_state'];checked+=1
for mc in q['monte_carlo_cases']:
 values=np.asarray(mc['normalized_station_covariance_real_imag']);s=values[:,:,0]+1j*values[:,:,1]
 theory=bispectrum_scale.known_bispectrum_moment_scale(s,128)
 np.testing.assert_array_equal(theory['real_covariance'],mc['known_real_covariance'])
print(json.dumps({'state':'complete','installed_modules_verified':True,'outside_checkout':True,'packaged_scientific_reference_used':True,'template_sha_verified':True,'forecasts_with_mean_variance_scale_count_checked':checked,'mc_full_covariances_checked':len(q['monte_carlo_cases']),'station_counts':[4,8],'source_normalized_coordinates_used':True,'uv_snapshot_recomputed':False,'observed_normalization_or_detection_test_performed':False}))
'''
    env=os.environ.copy();env.pop('PYTHONPATH',None)
    with tempfile.TemporaryDirectory(prefix='vsora-known-sky-api-') as folder:
        result=subprocess.run([sys.executable,'-c',script,str(record)],cwd=folder,env=env,capture_output=True,text=True,check=True)
    q=json.loads(result.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--reference',required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
