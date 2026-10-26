"""導入coreで固定原本4件を再生成し、sourceの全原本byteへ照合する。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args();root=Path(__file__).resolve().parents[1];source=Path(a.source).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');env.pop('PYTHONPATH',None)
    with tempfile.TemporaryDirectory(prefix='vsora-independent-raw-native-') as temporary:
        cwd=Path(temporary);assert not cwd.is_relative_to(root) and not (cwd/'tools/run.py').exists()
        cmd=[sys.executable,str(root/'workflows/independent_raw_matrix.py'),'--mode','installed','--output',str(out/'study')];q=subprocess.run(cmd,cwd=cwd,env=env,capture_output=True,text=True,timeout=900);(out/'native.log').write_text(q.stdout+q.stderr);assert q.returncode==0,q.stderr
        left=json.loads((source/'summary.json').read_text());right=json.loads((out/'study/summary.json').read_text());assert left==right;files=0;arrays=0;prefix_counts=[]
        for row in left['cases']:
            name=row['case'];src=source/name;dst=out/'study'/name
            assert json.loads((src/'science.json').read_text())==json.loads((dst/'science.json').read_text())
            for filename,digest in row['raw_input_file_sha256'].items():assert sha(src/'input'/filename)==sha(dst/'input'/filename)==digest;files+=1
            for filename in ['truth.npy','generation.json','boundary-decodes.npz']:assert sha(src/filename)==sha(dst/filename)
            np.testing.assert_array_equal(np.load(src/'truth.npy',allow_pickle=False),np.load(dst/'truth.npy',allow_pickle=False));arrays+=1
            with np.load(src/'boundary-decodes.npz',allow_pickle=False) as x,np.load(dst/'boundary-decodes.npz',allow_pickle=False) as y:
                assert set(x.files)==set(y.files)
                for key in x.files:np.testing.assert_array_equal(x[key],y[key]);arrays+=1
            info=json.loads((dst/'runtime-private.json').read_text());assert all(Path(v).is_relative_to(Path(sys.prefix)) for v in info['project_origins'].values());prefix_counts.append(len(info['project_origins']))
        before={str(f):sha(f) for f in (out/'study').rglob('*') if f.is_file()};q=subprocess.run(cmd,cwd=cwd,env=env,capture_output=True,text=True,timeout=30);assert q.returncode!=0 and 'FileExistsError' in q.stderr;(out/'nonoverwrite.log').write_text(q.stderr);assert all(sha(f)==h for f,h in before.items())
        report={'stage':131,'state':'complete','raw_cases_each':4,'same_conditions_reexecuted_not_independent_eight_cases':True,'input_files_bytes_exact':files,'generation_truth_boundary_archives_bytes_exact':12,'numeric_arrays_exact':arrays,
                'all_science_json_exact':True,'headers_checked_each':left['headers_checked'],'boundary_frames_decoded_each':left['boundary_decodes'],'worker_prefix_module_counts':prefix_counts,
                'outside_checkout':True,'repository_runner_invoked_in_installed':False,'workflow_helper_still_requires_checkout':True,'pythonpath_removed':True,'worker_existing_output_refusals_each':4,'whole_study_existing_output_refused':True,
                'source_all_raw_sha_unchanged':all(sha(source/r['case']/'input'/n)==h for r in left['cases'] for n,h in r['raw_input_file_sha256'].items()),'new_inference_correlation_image_executed':False,'zero_sky_control_generated':False,'actual_observation_validated':False}
        assert files==76 and arrays==68;(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
