"""Evaluate prior sensitivity on the identical completed VDIF synthesis data."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from vsora_imaging.rml import image_closure
from vsora_imaging.experiment import compare_relative


def run(synthesis_run,output):
    root=Path(synthesis_run);out=Path(output)
    if out.exists():raise FileExistsError('new prior comparison output required')
    original=json.loads((root/'summary.json').read_text());truth=np.load(root/'truth-relative.npy')
    source=root/'synthesis/visibility.npz'
    with source.open('rb') as stream:source_sha=hashlib.file_digest(stream,'sha256').hexdigest()
    out.mkdir(parents=True);rows=[{'prior_fwhm_arcsec':240.,'metrics':original['metrics'],
        'closure_chisq_per_measurement':original['synthesis']['rml']['closure_chisq_per_measurement'],
        'selected_optimizer_success':original['synthesis']['rml']['runs'][original['synthesis']['rml']['selected_start']]['optimizer_success']}]
    for prior in [160.,320.]:
        result=image_closure(source,out/f'prior-{int(prior)}',prior_fwhm_arcsec=prior,starts=3,max_iterations=2000)
        metrics,a,b,registered=compare_relative(truth,np.load(out/f'prior-{int(prior)}/relative-model.npy'),16.)
        rows.append({'prior_fwhm_arcsec':prior,'metrics':metrics,
            'closure_chisq_per_measurement':result['closure_chisq_per_measurement'],
            'selected_optimizer_success':result['runs'][result['selected_start']]['optimizer_success']})
    summary={'input_spectral_sha256':source_sha,'rows':rows,
        'limits':'Same noisy data; truth used only for comparison. Gaussian prior changed, not statistical confidence intervals or real-device sensitivity.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--synthesis-run',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(run(a.synthesis_run,a.output),indent=2))
