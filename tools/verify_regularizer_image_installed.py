"""固定罰則9条件をcheckout外の導入RML CLIと照合する。"""
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
from vsora_formats.spectral import load_spectral
from workflows.regularizer_image_validation import read_reference,initial_reference,score_regularizer_setting,KNOWN_FAILURE
from workflows.temporal_image_validation import split_times,sha,module_origins


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--reference',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    source=Path(a.source).resolve();ref=Path(a.reference).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False);old=json.loads((source/'summary.json').read_text());data,enrolled,inputs=read_reference(root,ref);assert inputs==old['input_files_sha256']
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');env.pop('PYTHONPATH',None);attempts=0;successes=0;known_failures=0;refusals=0;fits_count=0;arrays=0;native_rows=[];splits=split_times(8)
    with tempfile.TemporaryDirectory(prefix='vsora-regularizer-native-') as temporary:
        cwd=Path(temporary);assert not cwd.is_relative_to(root) and not (cwd/'tools/run.py').exists();os.chdir(cwd)
        for row in old['cases']:
            case=out/row['preset']/row['split'];case.mkdir(parents=True);src=source/row['preset']/row['split'];spectrum=ref/row['split']/'training.npz';assert sha(spectrum)==row['training_archive_sha256'];initial=initial_reference(load_spectral(spectrum),row['settings']);np.savez_compressed(case/'initial-reference.npz',**initial);assert sha(case/'initial-reference.npz')==row['initial_reference_sha256']
            with np.load(src/'initial-reference.npz',allow_pickle=False) as x:
                for k,v in initial.items():np.testing.assert_array_equal(v,x[k]);arrays+=1
            cmd=[sys.executable,'-m','vsora_imaging.rml','--input',str(spectrum),'--output',str(case/'rml')]
            for k,v in row['settings'].items():cmd+=['--'+k.replace('_','-'),str(v)]
            q=subprocess.run(cmd,cwd=cwd,env=env,text=True,capture_output=True);(case/'cli.log').write_text(q.stdout+q.stderr);attempts+=1
            if row['state']=='known_fit_failure':
                assert q.returncode!=0 and KNOWN_FAILURE in q.stderr and not (case/'rml').exists();known_failures+=1
            else:
                assert q.returncode==0,(row['preset'],row['split'],q.stderr);successes+=1;image=np.load(case/'rml/relative-model.npy',allow_pickle=False);np.testing.assert_array_equal(image,np.load(src/'rml/relative-model.npy',allow_pickle=False));arrays+=1
                with fits.open(case/'rml/relative-model.fits') as x,fits.open(src/'rml/relative-model.fits') as y:
                    np.testing.assert_array_equal(x[0].data,y[0].data);np.testing.assert_array_equal(x[0].data,image.astype(np.float32));arrays+=1;assert x[0].verify_checksum()==x[0].verify_datasum()==1
                    for k in ['CTYPE1','CTYPE2','CRVAL1','CRVAL2','CRPIX1','CRPIX2','CDELT1','CDELT2','BUNIT','FLUXREF','POSREF','RADESYS','FREQ']:assert x[0].header[k]==y[0].header[k]
                fits_count+=1;before={str(f):sha(f) for f in (case/'rml').iterdir() if f.is_file()};repeat=subprocess.run(cmd,cwd=cwd,env=env,text=True,capture_output=True);(case/'nonoverwrite.log').write_text(repeat.stdout+repeat.stderr);assert repeat.returncode!=0 and 'FileExistsError' in repeat.stderr;assert before=={str(f):sha(f) for f in (case/'rml').iterdir() if f.is_file()};refusals+=1
            print(json.dumps({'preset':row['preset'],'split':row['split'],'source_state_reproduced':row['state']}),flush=True)
        truth8=np.load(ref/'truth8.npy',allow_pickle=False);truth32=np.load(ref/'embedded-truth.npy',allow_pickle=False)
        for row in old['cases']:
            case=out/row['preset']/row['split'];native_row={**row}
            if row['state']=='fit_complete':
                image=np.load(case/'rml/relative-model.npy',allow_pickle=False);summary=json.loads((case/'rml/summary.json').read_text());science,embedded=score_regularizer_setting(data,splits[row['split']],image,summary,truth8,truth32,row['settings']);np.save(case/'embedded-model.npy',embedded);np.testing.assert_array_equal(embedded,np.load(source/row['preset']/row['split']/'embedded-model.npy',allow_pickle=False));arrays+=1
                science.update(image_npy_sha256=sha(case/'rml/relative-model.npy'),embedded_image_sha256=sha(case/'embedded-model.npy'));assert science==row['science'];native_row['science']=science
            else:assert row['science'] is None
            assert native_row==row;(case/'science.json').write_text(json.dumps(native_row,indent=2,allow_nan=False)+'\n');native_rows.append(native_row)
        origins=module_origins();pure=Path(sysconfig.get_path('purelib'));assert all(Path(v).is_relative_to(pure) for v in origins.values());(out/'runtime-origins.json').write_text(json.dumps(origins,indent=2)+'\n');expected={d.name:d for d in list((root/'apps').glob('*/src/vsora_*'))+list((root/'packages').glob('*/src/vsora_*'))};source_origins=json.loads((source/'runtime-origins.json').read_text());assert all(Path(v).is_relative_to(expected[n.split('.')[0]]) for n,v in source_origins.items())
        assert all(sha(ref/n)==h for n,h in inputs.items());result={**old,'cases':native_rows};assert result==old;(out/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        record={'stage':128,'state':'complete','actual_rml_cli_attempts':attempts,'successful_cli_fits':successes,'known_failed_cli_fits':known_failures,'starts_each':3,'all_science_json_exact':True,'numeric_arrays_compared':arrays,'initial_reference_bytes_identical':9,'same_input_archives_sha_verified':len(inputs),
                'fits_numeric_wcs_checksum_checked':fits_count,'nonoverwrite_refusals':refusals,'source_exact_project_module_origins':len(source_origins),'native_project_module_prefixes':len(origins),
                'original_inputs_sha_unchanged':True,'outside_checkout':True,'runner_absent':True,'pythonpath_removed_for_cli':True,'hyperparameters_selected_using_truth_or_unused_data':False,'defaults_changed':False,'actual_observation_validated':False}
        assert attempts==9 and successes+known_failures==9 and fits_count==refusals==successes;(out/'verification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))


if __name__=='__main__':main()
