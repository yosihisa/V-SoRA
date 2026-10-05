"""Compare installed known-population APIs outside the source checkout."""
import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path


def run(output,reference):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    script='''
import hashlib,json,sys
from pathlib import Path
import numpy as np
from vsora_observation import layouts,reference as asset
from vsora_simulator import sky,array_shape,sky_covariance,bispectrum_scale
prefix=Path(sys.prefix)
assert all(Path(m.__file__).is_relative_to(prefix) for m in (layouts,asset,sky,array_shape,sky_covariance,bispectrum_scale))
assert asset.reference_path().is_relative_to(prefix)
q=json.loads(Path(sys.argv[1]).read_text())
assert hashlib.sha256(asset.reference_path().read_bytes()).hexdigest()==q['reference']['derived_sha256']
config={'source':{'ra_deg':q['assumed_source_icrs_deg'][0],'dec_deg':q['assumed_source_icrs_deg'][1],'model':'casa','total_flux_jy':q['assumed_flux_jy']},'image':{'pixels':q['image_pixels'],'pixel_arcsec':q['image_pixel_arcsec']}}
image=sky.synthetic_sky(config)
snapshots={r['id']:r for r in q['snapshots']}
for row in q['snapshots']:
 np.testing.assert_array_equal(layouts.reference_layout(8,row['layout'],row['maximum_baseline_m']),row['station_enu_m'])
 values=np.asarray(row['known_visibility_jy_real_imag']);vis=values[:,0]+1j*values[:,1]
 assert array_shape.population_closure_signature(vis,np.asarray(row['pairs']),q['assumed_flux_jy'])==row['population_signature']
for case in q['conditional_scale_cases']:
 row=snapshots[case['snapshot_id']]
 s=sky_covariance.sky_station_covariance(row['station_uvw_lambda'],image,q['image_pixel_arcsec'],np.full(8,case['assumed_receiver_background_sefd_jy']))
 theory=bispectrum_scale.known_bispectrum_moment_scale(s['normalized_station_covariance'],case['independent_samples_conditional_input'])
 np.testing.assert_array_equal(theory['triangles'],case['triangles'])
 np.testing.assert_array_equal(np.c_[theory['mean'].real,theory['mean'].imag],case['known_mean_real_imag'])
 np.testing.assert_array_equal(theory['complex_covariance'].diagonal().real,case['known_complex_variance'])
 np.testing.assert_array_equal(theory['known_complex_rms_scale'],case['known_complex_rms_scale'])
print(json.dumps({'state':'complete','installed_modules_verified':True,'outside_checkout':True,'packaged_reference_sha_verified':True,'station_layouts_and_population_signatures_identical':len(snapshots),'known_mean_variance_scale_cases_identical':len(q['conditional_scale_cases']),'geometry_at_epoch_recomputed':False,'image_inference_performed':False,'actual_hardware_data':False}))
'''
    env=os.environ.copy();env.pop('PYTHONPATH',None)
    with tempfile.TemporaryDirectory(prefix='vsora-array-api-') as folder:
        result=subprocess.run([sys.executable,'-c',script,str(Path(reference).resolve())],cwd=folder,env=env,capture_output=True,text=True,check=True)
    q=json.loads(result.stdout);(out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--reference',required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
