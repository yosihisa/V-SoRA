"""checkout外で学習archiveを再構成し、導入済みRML CLIを9件実行する。"""
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
from vsora_formats.spectral import load_spectral,save_spectral
from workflows.temporal_image_validation import SETTINGS,NUMERIC_FIELDS,partition_input,split_times,score_fit,sha,module_origins,training_arrays_identity
from workflows.rate_acquisition_validation import arrays_identity
from workflows.closure_residual_diagnostics import common_baseline_mask


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--reference',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    source=Path(a.source).resolve();ref=Path(a.reference).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
    old=json.loads((source/'summary.json').read_text());assert old['fixed_new_fits']==9;names=list(dict.fromkeys(v['branch'] for v in old['cases']));loaded=[load_spectral(ref/n/'visibility.npz') for n in names]
    common=common_baseline_mask(loaded);np.testing.assert_array_equal(common,np.load(source/'common-baseline-mask.npy',allow_pickle=False));data_by_branch={n:{**d,'weights':np.where(common,d['weights'],0.)} for n,d in zip(names,loaded,strict=True)}
    splits=split_times(8);env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');env.pop('PYTHONPATH',None);native_rows=[];actual_cli=0;refused=0;fits_checked=0;array_count=1
    with tempfile.TemporaryDirectory(prefix='vsora-temporal-native-') as temporary:
        cwd=Path(temporary);assert not cwd.is_relative_to(root) and not (cwd/'tools/run.py').exists();os.chdir(cwd)
        for row in old['cases']:
            case=out/row['branch']/row['split'];case.mkdir(parents=True);original=source/row['branch']/row['split'];d=partition_input(data_by_branch[row['branch']],splits[row['split']]);spectrum=case/'training.npz'
            save_spectral(spectrum,{k:d[k] for k in NUMERIC_FIELDS},d['metadata']);assert sha(spectrum)==row['training_archive_sha256'] and training_arrays_identity(load_spectral(spectrum))==row['training_numeric_arrays']
            with np.load(spectrum,allow_pickle=False) as x,np.load(original/'training.npz',allow_pickle=False) as y:
                assert set(x.files)==set(y.files)
                for key in x.files:np.testing.assert_array_equal(x[key],y[key]);array_count+=1
            cmd=[sys.executable,'-m','vsora_imaging.rml','--input',str(spectrum),'--output',str(case/'rml')]
            for key,value in SETTINGS.items():cmd+=['--'+key.replace('_','-'),str(value)]
            q=subprocess.run(cmd,cwd=cwd,env=env,text=True,capture_output=True);(case/'cli.log').write_text(q.stdout+q.stderr);assert q.returncode==0,(row['branch'],row['split'],q.stderr);actual_cli+=1
            image=np.load(case/'rml/relative-model.npy',allow_pickle=False);np.testing.assert_array_equal(image,np.load(original/'rml/relative-model.npy',allow_pickle=False));array_count+=1
            with fits.open(case/'rml/relative-model.fits') as x,fits.open(original/'rml/relative-model.fits') as y:
                np.testing.assert_array_equal(x[0].data,y[0].data);np.testing.assert_array_equal(x[0].data,image.astype(np.float32));array_count+=1
                assert x[0].verify_checksum()==x[0].verify_datasum()==1
                for key in ['CTYPE1','CTYPE2','CRVAL1','CRVAL2','CRPIX1','CRPIX2','CDELT1','CDELT2','BUNIT','FLUXREF','POSREF','RADESYS','FREQ']:assert x[0].header[key]==y[0].header[key]
            fits_checked+=1
            before={str(f):sha(f) for f in (case/'rml').iterdir() if f.is_file()};q=subprocess.run(cmd,cwd=cwd,env=env,text=True,capture_output=True);(case/'nonoverwrite.log').write_text(q.stdout+q.stderr);assert q.returncode!=0 and 'FileExistsError' in q.stderr;assert before=={str(f):sha(f) for f in (case/'rml').iterdir() if f.is_file()};refused+=1
            print(json.dumps({'branch':row['branch'],'split':row['split'],'actual_cli_complete':True}),flush=True)
        # 真値はCLI全9件が終わってから読む。runの選択は各CLI自身のtraining objective。
        truth=np.load(ref/'truth.npy',allow_pickle=False)
        for row in old['cases']:
            case=out/row['branch']/row['split'];original=source/row['branch']/row['split'];image=np.load(case/'rml/relative-model.npy',allow_pickle=False);summary=json.loads((case/'rml/summary.json').read_text())
            science,embedded=score_fit(data_by_branch[row['branch']],splits[row['split']],image,summary,truth);np.save(case/'embedded-model.npy',embedded);array_count+=1
            science.update(image_npy_sha256=sha(case/'rml/relative-model.npy'),embedded_image_sha256=sha(case/'embedded-model.npy'));assert science==row['science'];np.testing.assert_array_equal(embedded,np.load(original/'embedded-model.npy',allow_pickle=False))
            (case/'science.json').write_text(json.dumps(science,indent=2,allow_nan=False)+'\n');native_rows.append({**row,'science':science})
        origins=module_origins();pure=Path(sysconfig.get_path('purelib'));assert all(Path(v).is_relative_to(pure) for v in origins.values());(out/'runtime-origins.json').write_text(json.dumps(origins,indent=2)+'\n')
        expected={d.name:d for d in list((root/'apps').glob('*/src/vsora_*'))+list((root/'packages').glob('*/src/vsora_*'))};source_origins=json.loads((source/'runtime-origins.json').read_text());assert all(Path(v).is_relative_to(expected[n.split('.')[0]]) for n,v in source_origins.items())
        assert all(sha(ref/n)==h for n,h in old['input_files_sha256'].items())
        result={**old,'cases':native_rows};assert result==old;(out/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        verification={'stage':126,'state':'complete','actual_rml_cli_runs':actual_cli,'starts_each':3,'all_science_json_exact':True,'images_and_embedded_arrays_exact':True,'numeric_arrays_compared':array_count,'training_archives_bytes_exact':9,
                      'fits_numeric_wcs_checksum_checked':fits_checked,'nonoverwrite_refusals':refused,'original_inputs_sha_unchanged':True,'native_project_module_prefixes':len(origins),'source_exact_project_module_origins':len(source_origins),
                      'outside_checkout':True,'runner_absent':True,'pythonpath_removed_for_cli':True,'truth_read_after_all_cli':True,'independent_noise_trials_claimed':False,'actual_observation_validated':False}
        assert actual_cli==fits_checked==refused==9;(out/'verification.json').write_text(json.dumps(verification,indent=2)+'\n');print(json.dumps(verification))


if __name__=='__main__':main()
