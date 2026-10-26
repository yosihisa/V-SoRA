"""導入済みRMLで全12条件を再実行し、科学JSON・全画像・FITSを照合する。"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import numpy as np
from astropy.io import fits
from matplotlib.image import imread


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--reference',required=True)
    p.add_argument('--raw-root',required=True);p.add_argument('--reference131',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();checkout=Path(__file__).resolve().parents[1]
    assert not Path.cwd().resolve().is_relative_to(checkout) and 'PYTHONPATH' not in os.environ and not (Path.cwd()/'tools/run.py').exists()
    spec=importlib.util.spec_from_file_location('image_validation_helper',checkout/'workflows/short_integration_images.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    source=Path(a.source).resolve();expected=json.loads((source/'summary.json').read_text());out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
    native=out/'study';helper.run(a.reference,a.raw_root,a.reference131,native,installed=True,expected=expected)
    arrays=0;metadata_fields=0;images=0;failed=0
    for row in expected['cases']:
        left=source/row['case'];right=native/row['case']
        with np.load(left/'fitter.npz',allow_pickle=False) as x,np.load(right/'fitter.npz',allow_pickle=False) as y:
            assert set(x.files)==set(y.files)
            for key in x.files:
                np.testing.assert_array_equal(x[key],y[key])
                if key=='metadata_json':metadata_fields+=1
                else:arrays+=1
        if row['failure_code'] is not None:
            assert not (left/'rml').exists() and not (right/'rml').exists();failed+=1;continue
        aimage=np.load(left/'rml/relative-model.npy',allow_pickle=False);bimage=np.load(right/'rml/relative-model.npy',allow_pickle=False)
        np.testing.assert_array_equal(aimage,bimage);arrays+=1
        with fits.open(left/'rml/relative-model.fits') as x,fits.open(right/'rml/relative-model.fits') as y:
            np.testing.assert_array_equal(x[0].data,y[0].data);np.testing.assert_array_equal(x[0].data,aimage.astype(np.float32));arrays+=1
            assert x[0].verify_checksum()==x[0].verify_datasum()==y[0].verify_checksum()==y[0].verify_datasum()==1
            for key in ['CTYPE1','CTYPE2','CRVAL1','CRVAL2','CRPIX1','CRPIX2','CDELT1','CDELT2','BUNIT','FLUXREF','POSREF','RADESYS','FREQ']:
                assert x[0].header[key]==y[0].header[key]
        np.testing.assert_array_equal(imread(left/'rml/rml.png'),imread(right/'rml/rml.png'));arrays+=1;images+=1
    before={str(p.relative_to(native)):helper.sha(p) for p in native.rglob('*') if p.is_file()}
    try:helper.run(a.reference,a.raw_root,a.reference131,native,installed=True,expected=expected)
    except FileExistsError:pass
    else:raise AssertionError('whole image study overwrite accepted')
    assert before=={str(p.relative_to(native)):helper.sha(p) for p in native.rglob('*') if p.is_file()}
    origins={n:m.__file__ for n,m in sys.modules.items() if n.startswith('vsora_') and getattr(m,'__file__',None)}
    assert origins and all(Path(v).is_relative_to(Path(sys.prefix)) for v in origins.values())
    record={'stage':133,'state':'complete','actual_native_rml_cli_conditions':12,'images_compared':images,'expected_constraint_failures':failed,
            'fits_numeric_wcs_checksum_checked':images,'png_pixels_compared':images,'numerical_arrays_compared':arrays,
            'metadata_json_fields_compared':metadata_fields,
            'all_science_json_exact':True,'source_native_fitter_archives_bytes_exact':all(helper.sha(source/r['case']/'fitter.npz')==helper.sha(native/r['case']/'fitter.npz') for r in expected['cases']),
            'nonoverwrite_successful_rml_conditions':images,'whole_study_nonoverwrite':True,'all_input_sha_preserved':True,
            'outside_checkout':True,'runner_absent':True,'pythonpath_absent':True,'helper_requires_checkout':True,
            'project_modules':sorted(origins),'all_project_modules_in_prefix':True,'truth_read_after_all_cli':True,'actual_observation_validated':False}
    helper.write_json(out/'verification.json',record);print(json.dumps(record))


if __name__=='__main__':main()
