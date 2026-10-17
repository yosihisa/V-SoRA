"""Independent installed API and full native holdout study outside checkout."""
import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path
import numpy as np
from vsora_simulator.template_score import fit_template_mean_score,score_template_features
from vsora_simulator.known_template_validation import case_plan,error_rate_summary,empirical_auc
from vsora_observation.reference import reference_path

def run(reference,api_reference,output):
    expected=json.loads(Path(reference).read_text());gold=json.loads(Path(api_reference).read_text())
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    checks=0
    for case in gold['score_cases']:
        model=fit_template_mean_score(np.array(case['point_training']),np.array(case['casa_training']))
        assert model==case['model']
        assert score_template_features(np.array(case['test_features']),model).tolist()==case['scores'];checks+=1
    for case in gold['rate_cases']:
        assert error_rate_summary(case['errors'],case['trials'])==case['result'];checks+=1
    for case in gold['auc_cases']:
        assert empirical_auc(np.array(case['point_scores']),np.array(case['casa_scores']))==case['auc'];checks+=1
    assert case_plan()==gold['case_plan']
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='vsora-template-installed-') as folder:
        workspace=Path(folder);assert not (workspace/'tools/run.py').exists()
        log=(out/'native-cli.log').open('w')
        command=[sys.executable,'-m','vsora_simulator.known_template_validation','--profile','full','--output',str(out/'native')]
        result=subprocess.run(command,cwd=workspace,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
        log.close();assert result.returncode==0
        assert json.loads((out/'native/summary.json').read_text())==expected
        before=(out/'native/summary.json').read_bytes()
        result=subprocess.run(command,cwd=workspace,env=env,capture_output=True,text=True,timeout=30)
        assert result.returncode!=0 and before==(out/'native/summary.json').read_bytes()
    modules=sorted(name for name,module in sys.modules.items() if name.startswith('vsora_') and getattr(module,'__file__',None))
    assert all(Path(sys.modules[name].__file__).is_relative_to(Path(sys.prefix)) for name in modules)
    for asset in ('casa-template-jy-pixel.fits','known-casa-window-symmetry.json','known-array-scale-config.json'):
        assert reference_path(asset).is_relative_to(Path(sys.prefix))
    q={'state':'complete','api_checks':checks,'fixed_plan_identical':True,
       'full_native_cli_all_scientific_json_identical':True,'native_cases':9,
       'all_project_modules_under_runtime_prefix':True,'project_module_count':len(modules),'project_modules':modules,
       'all_configuration_and_sky_assets_under_runtime_prefix':True,'pythonpath_removed':True,
       'cli_cwd_outside_checkout':True,'workspace_has_checkout_runner':False,'existing_results_not_overwritten':True}
    (out/'summary.json').write_text(json.dumps(q,indent=2)+'\n');print(json.dumps(q,indent=2));return q

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('reference','api-reference','output'):p.add_argument('--'+name,required=True)
    run(**vars(p.parse_args()))
