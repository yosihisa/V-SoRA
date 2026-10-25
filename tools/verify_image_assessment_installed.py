"""導入版の評価API/CLIをcheckout外で固定4入力と完全照合する。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from vsora_imaging import assessment as api


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(); p.add_argument('--reference', required=True); p.add_argument('--output', required=True)
    args = p.parse_args(); root = Path(__file__).resolve().parents[1]
    assert not Path.cwd().resolve().is_relative_to(root)
    assert not (Path.cwd()/'tools/run.py').exists() and 'PYTHONPATH' not in os.environ
    reference = Path(args.reference).resolve(); source = json.loads((reference/'summary.json').read_text())
    assert len(source['rows']) == 4 and source['same_input_reused_for_integrations'] and not source['truth_used_by_estimator']
    output = Path(args.output); output.mkdir(parents=True, exist_ok=False)
    cases = []; direct_rml = 0
    for row in source['rows']:
        case = reference/row['case_directory']; summary = json.loads((case/'pipeline-input.json').read_text())
        metrics = row['reference_metrics']; expected = row['assessment']
        assert api.assess_pipeline_result(summary, reference_metrics=metrics) == expected
        if summary.get('rml') is not None:
            rml_assessment = api.assess_rml_result(summary['rml'], processing_state=summary['state'], reference_metrics=metrics)
            assert all(expected[k] == v for k, v in rml_assessment.items()); direct_rml += 1
        target = output/f"{row['case']}.json"
        cmd = [sys.executable, '-m', 'vsora_imaging.assessment', '--input', str(case/'pipeline-input.json'), '--output', str(target)]
        if metrics is not None: cmd += ['--reference-metrics', str(case/'reference-metrics.json')]
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert json.loads(target.read_text()) == json.loads(result.stdout) == expected
        before = digest(target); repeat = subprocess.run(cmd, capture_output=True, text=True)
        assert repeat.returncode != 0 and 'FileExistsError' in repeat.stderr and digest(target) == before
        cases.append(row['case'])
    # 同じSEFDの原本は積分時間間で完全一致。生成SEFD差を同じraw bytesとは主張しない。
    for first, second in ((0, 1), (2, 3)):
        assert source['rows'][first]['input_sha256'] == source['rows'][second]['input_sha256']
    modules = sorted(name for name, module in sys.modules.items() if name.startswith('vsora_') and getattr(module, '__file__', None))
    assert modules and all(Path(sys.modules[name].__file__).is_relative_to(Path(sys.prefix)) for name in modules)
    record = {'state': 'complete', 'pipeline_api_and_cli_whole_json_identical': cases,
              'direct_rml_api_conditions': direct_rml, 'project_modules': modules,
              'all_project_modules_in_prefix': True, 'outside_checkout': True,
              'runner_absent': True, 'pythonpath_absent': True,
              'non_overwrite_verified_for_every_case': True,
              'scope': 'Re-assessment of frozen source-generated pipeline outputs. VDIF correlation/RML not re-executed by this verifier; both full regressions cover existing algorithms.'}
    (output/'verification.json').write_text(json.dumps(record, indent=2)+'\n'); print(json.dumps(record))


if __name__ == '__main__': main()
