"""checkout外の導入済みRML CLIで粗い格子6件を再生成する。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
from astropy.io import fits
from vsora_formats.spectral import load_spectral
from vsora_imaging.objective_evaluation import evaluate_closure_image
from vsora_imaging.experiment import compare_relative
from vsora_simulator.visibility import direct_visibility


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stable(value):
    if isinstance(value,dict): return {k:stable(v) for k,v in value.items() if k not in ('elapsed_s','input_sha256')}
    if isinstance(value,list): return [stable(v) for v in value]
    return value


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reference',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();checkout=Path(__file__).resolve().parents[1]
    assert not Path.cwd().resolve().is_relative_to(checkout) and 'PYTHONPATH' not in os.environ and not (Path.cwd()/'tools/run.py').exists()
    reference=Path(args.reference);source=json.loads((reference/'summary.json').read_text());parent=Path(source['source_reference'])
    original=json.loads((parent/'summary.json').read_text());truth=np.load(parent/'truth.npy',allow_pickle=False)
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False);new=[];cited=[];fits_checked=0
    for row in source['cases']:
        root=out/row['branch']/f"pixels{row['pixels']}";root.mkdir(parents=True)
        data=load_spectral(row['spectrum']);assert sha(row['spectrum'])==row['input_sha256']
        settings={**original['settings'],'pixels':row['pixels'],'pixel_arcsec':row['pixel_arcsec']}
        if row['fit_reused_from_118']:
            image_path=parent/row['branch']/'rml/relative-model.npy';summary=json.loads((parent/row['branch']/'rml/summary.json').read_text())
            cited.append(row['branch'])
        else:
            cmd=[sys.executable,'-m','vsora_imaging.rml','--input',row['spectrum'],'--output',str(root/'rml')]
            for key,value in settings.items():cmd+=['--'+key.replace('_','-'),str(value)]
            run=subprocess.run(cmd,capture_output=True,text=True);(root/'cli.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stderr
            summary=json.loads((root/'rml/summary.json').read_text());image_path=root/'rml/relative-model.npy'
            before={str(f.relative_to(root/'rml')):sha(f) for f in (root/'rml').iterdir() if f.is_file()}
            repeated=subprocess.run(cmd,capture_output=True,text=True);assert repeated.returncode!=0 and 'FileExistsError' in repeated.stderr
            assert before=={str(f.relative_to(root/'rml')):sha(f) for f in (root/'rml').iterdir() if f.is_file()}
            old=reference/row['branch']/f"pixels{row['pixels']}"/'rml'
            with fits.open(old/'relative-model.fits') as a,fits.open(root/'rml/relative-model.fits') as b:
                np.testing.assert_array_equal(a[0].data,b[0].data)
                for key in ('CDELT1','CDELT2','CTYPE1','CTYPE2','CRPIX1','CRPIX2','BUNIT','FLUXREF','POSREF'):assert a[0].header[key]==b[0].header[key]
                assert abs(b[0].header['CDELT1'])*3600==np.float64(row['pixel_arcsec']) or np.isclose(abs(b[0].header['CDELT1'])*3600,row['pixel_arcsec'],rtol=1e-14)
            fits_checked+=1;new.append([row['branch'],row['pixels']])
        image=np.load(image_path,allow_pickle=False);assert sha(image_path)==row['science']['coarse_image_sha256']
        embedded=np.zeros((32,32));step=32//row['pixels'];embedded[::step,::step]=image
        np.save(root/'embedded-model.npy',embedded);assert sha(root/'embedded-model.npy')==row['science']['embedded_image_sha256']
        a=direct_visibility(data['uvw_lambda'],image,row['pixel_arcsec']);b=direct_visibility(data['uvw_lambda'],embedded,16.)
        cost_settings={k:v for k,v in settings.items() if k not in ('pixels','starts','max_iterations','seed')}
        coarse=evaluate_closure_image(data['uvw_lambda'],data['visibilities'],data['weights'],data['pairs'],image,**cost_settings)
        fine=evaluate_closure_image(data['uvw_lambda'],data['visibilities'],data['weights'],data['pairs'],embedded,**{**cost_settings,'pixel_arcsec':16.})
        metrics,_,_,_=compare_relative(truth,embedded,16.)
        science={'rml_summary':stable(summary),'coarse_objective':coarse,'embedded_reference_grid_objective':fine,
                 'reference_metrics':metrics,'maximum_complex_visibility_embedding_difference':float(np.max(np.abs(a-b))),
                 'coarse_image_sha256':sha(image_path),'embedded_image_sha256':sha(root/'embedded-model.npy')}
        assert science==row['science'];(root/'science.json').write_text(json.dumps(science,indent=2,allow_nan=False)+'\n')
        assert sha(row['spectrum'])==row['input_sha256']
    assert len(new)==fits_checked==6 and len(cited)==3
    modules=sorted(n for n,m in sys.modules.items() if n.startswith('vsora_') and getattr(m,'__file__',None));assert all(Path(sys.modules[n].__file__).is_relative_to(Path(sys.prefix)) for n in modules)
    record={'state':'complete','actual_new_rml_cli_runs':new,'cited_118_fits':cited,'all9_scientific_json_and_coarse_embedded_bytes_identical':True,
            'fits_numeric_data_and_wcs_checked':fits_checked,'all6_existing_output_repetitions_refused_before_fit':True,'all_input_sha_preserved':True,
            'outside_checkout':True,'runner_absent':True,'pythonpath_absent':True,'project_modules':modules,'all_project_modules_in_prefix':True,
            'source_workflow_not_imported':not any(n.startswith('workflows') for n in sys.modules)}
    (out/'verification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))


if __name__=='__main__':main()
