"""Check installed replicate API and native CLI from a checkout-free cwd."""
import argparse,hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
from vsora_simulator import independent_training_validation as study
from vsora_observation.reference import reference_path


def run(reference,api_reference,output):
    checkout=Path(__file__).resolve().parents[1]
    assert not Path.cwd().resolve().is_relative_to(checkout),'run API verification outside checkout'
    assert 'PYTHONPATH' not in os.environ
    expected=json.loads(Path(reference).read_text());gold=json.loads(Path(api_reference).read_text())
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False);checks=0
    for c in gold['replicate_cases']:
        assert study.independent_replicate_summary(c['values'])==c['result'];checks+=1
    assert study.case_plan()==gold['case_plan']
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-independent-training-cli-') as folder:
        workspace=Path(folder);assert not (workspace/'tools/run.py').exists()
        command=[sys.executable,'-m','vsora_simulator.independent_training_validation','--profile','full','--output',str(out/'native')]
        with (out/'native-cli.log').open('w') as f:
            result=subprocess.run(command,cwd=workspace,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1800)
        assert result.returncode==0
        actual=json.loads((out/'native/summary.json').read_text());assert actual==expected
        assert actual['state']=='complete' and len(actual['cases'])==7 and actual['outer_replicates_total']==112
        def hashes():return {str(p.relative_to(out/'native')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (out/'native').rglob('*') if p.is_file()}
        before=hashes();result=subprocess.run(command,cwd=workspace,env=env,capture_output=True,text=True,timeout=30)
        assert result.returncode!=0 and hashes()==before
    modules=sorted(name for name,m in sys.modules.items() if name.startswith('vsora_') and getattr(m,'__file__',None))
    assert all(Path(sys.modules[n].__file__).is_relative_to(Path(sys.prefix)) for n in modules)
    for asset in ('casa-template-jy-pixel.fits','known-casa-window-symmetry.json','known-array-scale-config.json'):
        assert reference_path(asset).is_relative_to(Path(sys.prefix))
    q={'state':'complete','api_checks':checks,'fixed_plan_identical':True,
       'full_native_cli_all_scientific_json_identical':True,'native_cases':7,'outer_replicates':112,
       'all_project_modules_under_runtime_prefix':True,'project_module_count':len(modules),'project_modules':modules,
       'all_configuration_and_sky_assets_under_runtime_prefix':True,'pythonpath_removed':True,
       'api_and_cli_cwd_outside_checkout':True,'workspace_has_checkout_runner':False,'existing_results_not_overwritten':True}
    (out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');return q


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('reference','api-reference','output'):p.add_argument('--'+name,required=True)
    print(json.dumps(run(**vars(p.parse_args())),indent=2))
