"""Verify standalone installed archive-to-window API/CLI outside checkout."""
import argparse,json,os
from pathlib import Path
import subprocess,sys,tempfile
from vsora_correlator.bispectrum_window_symmetry import inspect_bispectrum_window_file


def run(reference,fixtures,output):
    root=Path(fixtures).resolve();expected=json.loads(Path(reference).read_text())
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    cases=[]
    with tempfile.TemporaryDirectory(prefix='vsora-window-cli-') as folder:
        workspace=Path(folder);assert not (workspace/'tools/run.py').exists()
        for case in expected['cases']:
            name=case['case_id'];raw=root/name/'raw.npz';source=root/name/'visibility.npz'
            api=out/(name+'-api.json');cli=out/(name+'-cli.json')
            try:actual=inspect_bispectrum_window_file(raw,source,api,case['channel_index'])
            except ValueError:
                assert not case['expected_success'] and not api.exists()
            else:
                assert case['expected_success'] and actual==case['result']
            command=[str(Path(sys.prefix)/'bin/vsora-window-symmetry'),'--input',str(raw),
                     '--source-visibility',str(source),'--output',str(cli),
                     '--channel-index',str(case['channel_index'])]
            completed=subprocess.run(command,cwd=workspace,env=env,text=True,capture_output=True)
            (out/(name+'-cli.log')).write_text(completed.stdout+completed.stderr)
            if case['expected_success']:
                assert completed.returncode==0 and json.loads(cli.read_text())==case['result']
                before=cli.read_bytes()
                repeated=subprocess.run(command,cwd=workspace,env=env,text=True,capture_output=True)
                assert repeated.returncode!=0 and cli.read_bytes()==before
            else:assert completed.returncode!=0 and not cli.exists()
            cases.append({'case_id':name,'api_matches_source':True,'independent_console_matches_source':True,
                          'success':case['expected_success']})
    names=sorted(name for name,module in sys.modules.items()
                 if name.startswith('vsora_') and getattr(module,'__file__',None))
    assert names and all(Path(sys.modules[name].__file__).is_relative_to(Path(sys.prefix)) for name in names)
    q={'state':'complete','cases':cases,'all_api_and_cli_results_identical':True,
       'all_project_modules_under_runtime_prefix':True,'project_module_count':len(names),'project_modules':names,
       'cli_cwd_outside_checkout':True,'pythonpath_removed_for_cli':True,'workspace_has_checkout_runner':False,
       'existing_results_not_overwritten':True,'unavailable_cases_not_partially_written':True}
    (out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');print(json.dumps(q,indent=2));return q


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('reference','fixtures','output'):p.add_argument('--'+name,required=True)
    run(**vars(p.parse_args()))
