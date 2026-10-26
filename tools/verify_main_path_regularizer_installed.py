"""模擬電圧由来の同じ最小学習archiveで、導入済みRML CLI9件を照合する。"""
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
from workflows.main_path_regularizer_validation import read_main_reference,score_main_case
from workflows.regularizer_image_validation import KNOWN_FAILURE,initial_reference
from workflows.temporal_image_validation import sha,module_origins
from workflows.matched_grid_image_validation import quantize_truth8


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--reference',required=True);p.add_argument('--truth',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    source=Path(a.source).resolve();ref=Path(a.reference).resolve();truth_path=Path(a.truth).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False);old=json.loads((source/'summary.json').read_text());loaded,baseline,inputs,fine_loss=read_main_reference(root,ref,truth_path);assert inputs==old['input_files_sha256'] and baseline==old['cited126_cases']
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');env.pop('PYTHONPATH',None);attempts=successes=known_failures=refusals=fits_count=arrays=0;native_rows=[]
    with tempfile.TemporaryDirectory(prefix='vsora-main-regularizer-native-') as temporary:
        cwd=Path(temporary);assert not cwd.is_relative_to(root) and not (cwd/'tools/run.py').exists();os.chdir(cwd)
        for row in old['cases']:
            case=out/row['preset']/row['branch'];case.mkdir(parents=True);src=source/row['preset']/row['branch'];spectrum=ref/row['branch']/'all_training/training.npz';assert sha(spectrum)==row['training_archive_sha256'];initial=initial_reference(loaded[row['branch']],row['settings']);np.savez_compressed(case/'initial-reference.npz',**initial);assert sha(case/'initial-reference.npz')==row['initial_reference_sha256']
            with np.load(src/'initial-reference.npz',allow_pickle=False) as x:
                for k,v in initial.items():np.testing.assert_array_equal(v,x[k]);arrays+=1
            cmd=[sys.executable,'-m','vsora_imaging.rml','--input',str(spectrum),'--output',str(case/'rml')]
            for k,v in row['settings'].items():cmd+=['--'+k.replace('_','-'),str(v)]
            q=subprocess.run(cmd,cwd=cwd,env=env,text=True,capture_output=True);(case/'cli.log').write_text(q.stdout+q.stderr);attempts+=1
            if row['state']=='known_fit_failure':
                assert q.returncode!=0 and KNOWN_FAILURE in q.stderr and not (case/'rml').exists();known_failures+=1
            else:
                assert q.returncode==0,(row['preset'],row['branch'],q.stderr);successes+=1;image=np.load(case/'rml/relative-model.npy',allow_pickle=False);np.testing.assert_array_equal(image,np.load(src/'rml/relative-model.npy',allow_pickle=False));arrays+=1
                with fits.open(case/'rml/relative-model.fits') as x,fits.open(src/'rml/relative-model.fits') as y:
                    np.testing.assert_array_equal(x[0].data,y[0].data);np.testing.assert_array_equal(x[0].data,image.astype(np.float32));arrays+=1;assert x[0].verify_checksum()==x[0].verify_datasum()==1
                    for k in ['CTYPE1','CTYPE2','CRVAL1','CRVAL2','CRPIX1','CRPIX2','CDELT1','CDELT2','BUNIT','FLUXREF','POSREF','RADESYS','FREQ']:assert x[0].header[k]==y[0].header[k]
                fits_count+=1;before={str(f):sha(f) for f in (case/'rml').iterdir() if f.is_file()};q=subprocess.run(cmd,cwd=cwd,env=env,text=True,capture_output=True);(case/'nonoverwrite.log').write_text(q.stdout+q.stderr);assert q.returncode!=0 and 'FileExistsError' in q.stderr;assert before=={str(f):sha(f) for f in (case/'rml').iterdir() if f.is_file()};refusals+=1
            print(json.dumps({'preset':row['preset'],'branch':row['branch'],'source_state_reproduced':row['state']}),flush=True)
        truth32=np.load(truth_path,allow_pickle=False);quantized8=quantize_truth8(truth32)
        for row in old['cases']:
            case=out/row['preset']/row['branch'];native={**row}
            if row['state']=='fit_complete':
                image=np.load(case/'rml/relative-model.npy',allow_pickle=False);summary=json.loads((case/'rml/summary.json').read_text());science,embedded=score_main_case(loaded[row['branch']],image,summary,truth32,quantized8,row['settings'],fine_loss[row['branch']]);np.save(case/'embedded-model.npy',embedded);np.testing.assert_array_equal(embedded,np.load(source/row['preset']/row['branch']/'embedded-model.npy',allow_pickle=False));arrays+=1
                science.update(image_npy_sha256=sha(case/'rml/relative-model.npy'),embedded_image_sha256=sha(case/'embedded-model.npy'));assert science==row['science'];native['science']=science
            else:assert row['science'] is None
            assert native==row;(case/'science.json').write_text(json.dumps(native,indent=2,allow_nan=False)+'\n');native_rows.append(native)
        origins=module_origins();pure=Path(sysconfig.get_path('purelib'));assert all(Path(v).is_relative_to(pure) for v in origins.values());(out/'runtime-origins.json').write_text(json.dumps(origins,indent=2)+'\n');expected={d.name:d for d in list((root/'apps').glob('*/src/vsora_*'))+list((root/'packages').glob('*/src/vsora_*'))};source_origins=json.loads((source/'runtime-origins.json').read_text());assert all(Path(v).is_relative_to(expected[n.split('.')[0]]) for n,v in source_origins.items())
        assert all(sha(truth_path if n=='fine_truth_npy' else ref/n)==h for n,h in inputs.items());result={**old,'cases':native_rows};assert result==old;(out/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        record={'stage':129,'state':'complete','actual_rml_cli_attempts':attempts,'successful_cli_fits':successes,'known_failed_cli_fits':known_failures,'starts_each':3,'all_science_json_exact':True,'numeric_arrays_compared':arrays,'initial_reference_bytes_identical':9,'same_input_archives_sha_verified':len(inputs),
                'fits_numeric_wcs_checksum_checked':fits_count,'nonoverwrite_refusals':refusals,'source_exact_project_module_origins':len(source_origins),'native_project_module_prefixes':len(origins),'original_inputs_sha_unchanged':True,'outside_checkout':True,'runner_absent':True,'pythonpath_removed_for_cli':True,
                'fine32_reference_residuals_match125':True,'quantized_reference8_is_generating_sky':False,'new_unused_prediction_evaluated':False,'hyperparameters_selected_using_truth_or_unused_data':False,'defaults_changed':False,'actual_observation_validated':False}
        assert attempts==9 and successes+known_failures==9 and fits_count==refusals==successes;(out/'verification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))


if __name__=='__main__':main()
