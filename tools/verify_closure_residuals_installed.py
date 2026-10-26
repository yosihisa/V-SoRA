"""保存済み18条件をcheckout外の導入API/CLIで照合する。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import tempfile
import numpy as np


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--reference',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[1];source=Path(a.source).resolve();reference=Path(a.reference).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');env.pop('PYTHONPATH',None)
    def run(args,log,cwd,success=True):
        q=subprocess.run(args,cwd=cwd,env=env,text=True,capture_output=True);(out/log).write_text(q.stdout+q.stderr);assert (q.returncode==0)==success,(log,q.returncode);return q
    with tempfile.TemporaryDirectory(prefix='vsora-residual-diagnostic-') as directory:
        cwd=Path(directory);assert not cwd.is_relative_to(root) and not (cwd/'tools/run.py').exists()
        run([sys.executable,str(root/'workflows/closure_residual_diagnostics.py'),'--repository',str(root),'--reference',str(reference),'--output',str(out/'native')],'native.log',cwd)
        expected={'vsora_imaging':root/'apps/imaging/src/vsora_imaging','vsora_formats':root/'packages/formats/src/vsora_formats','vsora_simulator':root/'apps/simulator/src/vsora_simulator','vsora_observation':root/'packages/observation/src/vsora_observation'}
        source_origins=json.loads((source/'runtime-origins.json').read_text());assert all(Path(source_origins[n]).parent==path for n,path in expected.items())
        installed_origins=json.loads((out/'native/runtime-origins.json').read_text());pure=Path(sysconfig.get_path('purelib'));assert all(Path(v).is_relative_to(pure) for v in installed_origins.values())
        left=json.loads((source/'summary.json').read_text());right=json.loads((out/'native/summary.json').read_text());assert left==right
        arrays=0;archives=0;commands=0
        np.testing.assert_array_equal(np.load(source/'common-baseline-mask.npy',allow_pickle=False),np.load(out/'native/common-baseline-mask.npy',allow_pickle=False));arrays+=1
        for row in left['cases']:
            relative=Path(row['branch'])/row['support']/row['candidate'];src=source/relative;dst=out/'native'/relative
            assert json.loads((src/'diagnostic.json').read_text())==json.loads((dst/'diagnostic.json').read_text())
            with np.load(src/'detail.npz',allow_pickle=False) as x,np.load(dst/'detail.npz',allow_pickle=False) as y:
                assert set(x.files)==set(y.files)
                for name in x.files:np.testing.assert_array_equal(x[name],y[name]);arrays+=1
            np.testing.assert_array_equal(np.load(src/'candidate.npy',allow_pickle=False),np.load(dst/'candidate.npy',allow_pickle=False));arrays+=1;archives+=1
            command_out=out/f'api-{commands:02d}.json'
            run([sys.executable,'-m','vsora_imaging.objective_evaluation','--input',str(dst.parent/'diagnostic-input.npz'),'--image',str(dst/'candidate.npy'),'--output',str(command_out),'--pixel-arcsec','16','--min-snr','10'],f'cli-{commands:02d}.log',cwd)
            actual=json.loads(command_out.read_text());assert actual.pop('input_sha256')==row['diagnostic_input_sha256'];assert actual.pop('candidate_sha256')==row['candidate_npy_sha256'];assert actual==row['diagnostic']['public_api'];commands+=1
        original_hashes={str(reference/name):digest for name,digest in left['input_files_sha256'].items()}
        before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (out/'native').rglob('*') if p.is_file()}
        q=run([sys.executable,str(root/'workflows/closure_residual_diagnostics.py'),'--repository',str(root),'--reference',str(reference),'--output',str(out/'native')],'nonoverwrite.log',cwd,False);assert 'FileExistsError' in q.stderr
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in {**before,**original_hashes}.items())
        report={'stage':125,'state':'complete','all_science_json_identical':True,'detail_archives_compared':archives,'numeric_arrays_exact':arrays,'native_public_cli_evaluations':commands,
            'all_cli_science_json_exact_to_api':True,'source_core_origins_exact':4,'installed_core_prefixes':len(installed_origins),'cwd_outside_checkout':True,'repository_runner_invoked':False,
            'nonoverwrite_and_all_input_output_bytes_unchanged':True,'maximum_independent_api_loss_absolute_difference':max(x['diagnostic']['public_data_loss_absolute_difference'] for x in left['cases']),
            'common_valid_baselines':left['common_valid_baselines'],'common_basis_indices_identical':left['common_basis_indices_identical'],'new_correlation_or_image_fit_executed':False,'p_value_computed':False,'actual_observation_validated':False}
        (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
