"""同格子生成を再構成し、checkout外の導入RML CLI3件と照合する。"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import tempfile
import numpy as np
from astropy.io import fits
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from vsora_formats.spectral import save_spectral
from workflows.matched_grid_image_validation import make_control,score_matched
from workflows.temporal_image_validation import SETTINGS,NUMERIC_FIELDS,split_times,partition_input,sha,training_arrays_identity,module_origins


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--reference',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    source=Path(a.source).resolve();ref=Path(a.reference).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False);old=json.loads((source/'summary.json').read_text())
    assert old['fixed_new_fits']==3;data,truth8,truth32,generation=make_control(root,ref,out/'generation');assert generation==old['generation'];arrays=0
    for name in ['truth8.npy','embedded-truth.npy','common-baseline-mask.npy','control.npz','transport-detail.npz']:
        assert sha(source/name)==sha(out/'generation'/name)
        if name.endswith('.npy'):np.testing.assert_array_equal(np.load(source/name,allow_pickle=False),np.load(out/'generation'/name,allow_pickle=False));arrays+=1
        else:
            with np.load(source/name,allow_pickle=False) as x,np.load(out/'generation'/name,allow_pickle=False) as y:
                assert set(x.files)==set(y.files)
                for k in x.files:np.testing.assert_array_equal(x[k],y[k]);arrays+=1
    splits=split_times(8);env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');env.pop('PYTHONPATH',None);native_rows=[];actual_cli=0;refusals=0;fits_count=0
    with tempfile.TemporaryDirectory(prefix='vsora-matched-grid-native-') as temporary:
        cwd=Path(temporary);assert not cwd.is_relative_to(root) and not (cwd/'tools/run.py').exists();os.chdir(cwd)
        for row in old['cases']:
            case=out/row['split'];case.mkdir();d=partition_input(data,splits[row['split']]);spectrum=case/'training.npz';save_spectral(spectrum,{k:d[k] for k in NUMERIC_FIELDS},d['metadata']);assert sha(spectrum)==row['training_archive_sha256'] and training_arrays_identity(d)==row['training_numeric_arrays']
            with np.load(spectrum,allow_pickle=False) as x,np.load(source/row['split']/'training.npz',allow_pickle=False) as y:
                assert set(x.files)==set(y.files)
                for k in x.files:np.testing.assert_array_equal(x[k],y[k]);arrays+=1
            cmd=[sys.executable,'-m','vsora_imaging.rml','--input',str(spectrum),'--output',str(case/'rml')]
            for k,v in SETTINGS.items():cmd+=['--'+k.replace('_','-'),str(v)]
            q=subprocess.run(cmd,cwd=cwd,env=env,text=True,capture_output=True);(case/'cli.log').write_text(q.stdout+q.stderr);assert q.returncode==0,(row['split'],q.stderr);actual_cli+=1
            image=np.load(case/'rml/relative-model.npy',allow_pickle=False);np.testing.assert_array_equal(image,np.load(source/row['split']/'rml/relative-model.npy',allow_pickle=False));arrays+=1
            with fits.open(case/'rml/relative-model.fits') as x,fits.open(source/row['split']/'rml/relative-model.fits') as y:
                np.testing.assert_array_equal(x[0].data,y[0].data);np.testing.assert_array_equal(x[0].data,image.astype(np.float32));arrays+=1
                assert x[0].verify_checksum()==x[0].verify_datasum()==1
                for k in ['CTYPE1','CTYPE2','CRVAL1','CRVAL2','CRPIX1','CRPIX2','CDELT1','CDELT2','BUNIT','FLUXREF','POSREF','RADESYS','FREQ']:assert x[0].header[k]==y[0].header[k]
            fits_count+=1;before={str(f):sha(f) for f in (case/'rml').iterdir() if f.is_file()};q=subprocess.run(cmd,cwd=cwd,env=env,text=True,capture_output=True);(case/'nonoverwrite.log').write_text(q.stdout+q.stderr);assert q.returncode!=0 and 'FileExistsError' in q.stderr;assert before=={str(f):sha(f) for f in (case/'rml').iterdir() if f.is_file()};refusals+=1
            print(json.dumps({'split':row['split'],'actual_cli_complete':True}),flush=True)
        for row in old['cases']:
            case=out/row['split'];image=np.load(case/'rml/relative-model.npy',allow_pickle=False);summary=json.loads((case/'rml/summary.json').read_text());science,embedded=score_matched(data,splits[row['split']],image,summary,truth8,truth32);np.save(case/'embedded-model.npy',embedded);np.testing.assert_array_equal(embedded,np.load(source/row['split']/'embedded-model.npy',allow_pickle=False));arrays+=1
            science.update(image_npy_sha256=sha(case/'rml/relative-model.npy'),embedded_image_sha256=sha(case/'embedded-model.npy'));assert science==row['science'];(case/'science.json').write_text(json.dumps(science,indent=2,allow_nan=False)+'\n');native_rows.append({**row,'science':science})
        origins=module_origins();pure=Path(sysconfig.get_path('purelib'));assert all(Path(v).is_relative_to(pure) for v in origins.values());(out/'runtime-origins.json').write_text(json.dumps(origins,indent=2)+'\n');expected={d.name:d for d in list((root/'apps').glob('*/src/vsora_*'))+list((root/'packages').glob('*/src/vsora_*'))};source_origins=json.loads((source/'runtime-origins.json').read_text());assert all(Path(v).is_relative_to(expected[n.split('.')[0]]) for n,v in source_origins.items())
        assert all(sha(ref/n)==h for n,h in generation['input_files_sha256'].items());result={**old,'generation':generation,'cases':native_rows};assert result==old;(out/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        record={'stage':127,'state':'complete','actual_rml_cli_runs':actual_cli,'starts_each':3,'all_science_json_exact':True,'generation_and_detail_archive_bytes_exact':5,'numeric_arrays_compared':arrays,'training_archives_bytes_exact':3,'fits_numeric_wcs_checksum_checked':fits_count,'nonoverwrite_refusals':refusals,
                'original_inputs_sha_unchanged':True,'source_exact_project_module_origins':len(source_origins),'native_project_module_prefixes':len(origins),'outside_checkout':True,'runner_absent':True,'pythonpath_removed_for_cli':True,'truth_used_by_generator_and_post_evaluation_only':True,'independent_noise_trials_claimed':False,'actual_observation_validated':False}
        assert actual_cli==fits_count==refusals==3;(out/'verification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))


if __name__=='__main__':main()
