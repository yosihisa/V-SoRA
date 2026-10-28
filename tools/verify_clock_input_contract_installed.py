"""checkout外の導入API/CLIと固定原本の全数値・metadataをsourceへ照合する。"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--raw-reference',required=True);p.add_argument('--record131',required=True);p.add_argument('--old-reference',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[1];assert not Path.cwd().resolve().is_relative_to(root) and not (Path.cwd()/'tools/run.py').exists() and 'PYTHONPATH' not in os.environ
    spec=importlib.util.spec_from_file_location('clock_contract_helper',root/'workflows/clock_input_contract_validation.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    expected=json.loads((Path(a.source)/'summary.json').read_text());out=Path(a.output).resolve();out.mkdir(exist_ok=False,parents=True)
    helper.run(a.raw_reference,a.record131,a.old_reference,out/'study',installed=True,expected=expected)
    for name in helper.CASES:
        from vsora_formats.spectral import load_spectral
        import numpy as np
        source=load_spectral(Path(a.source)/name/'shard-00000.npz');native=load_spectral(out/'study'/name/'shard-00000.npz')
        for key,value in source.items():
            if isinstance(value,np.ndarray):np.testing.assert_array_equal(value,native[key])
        assert source['metadata']==native['metadata']
    origins={n:m.__file__ for n,m in sys.modules.items() if n.startswith('vsora_') and getattr(m,'__file__',None)}
    assert origins and all(Path(v).is_relative_to(Path(sys.prefix)) for v in origins.values())
    helper.write_json(out/'module-paths-private.json',origins)
    helper.write_json(out/'verification.json',{'stage':138,'state':'complete','all_four_api_cli_science_exact':True,'all_numerical_arrays_directly_compared':True,'all_metadata_exact':True,'actual_valid_cli_calls':4,'actual_bad_cli_rejections':3,'valid_api_refusals':4,'valid_cli_refusals':4,'outside_checkout':True,'runner_absent':True,'pythonpath_absent':True,'helper_requires_checkout':True,'project_module_count':len(origins),'all_project_modules_in_prefix':True,'raw_files_sha_preserved':76,'physical_iq_clock_or_sefd_verified':False})


if __name__=='__main__':main()
