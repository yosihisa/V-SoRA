"""Re-evaluate frozen Cas A images without changing the noisy data or RML."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from vsora_imaging.experiment import compare_relative


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def run(high_sensitivity_run,low_sensitivity_run,prior_run,output):
    high=Path(high_sensitivity_run);low=Path(low_sensitivity_run);prior=Path(prior_run);out=Path(output)
    if out.exists():raise FileExistsError('new evaluation output required')
    out.mkdir(parents=True)
    high_summary=json.loads((high/'summary.json').read_text());low_summary=json.loads((low/'summary.json').read_text())
    priors=json.loads((prior/'summary.json').read_text());old_priors={row['prior_fwhm_arcsec']:row for row in priors['rows']}
    cases=[('stage024_sefd1000_prior240',high,high/'synthesis/rml/relative-model.npy',high_summary['metrics']),
           ('stage028_sefd10000_prior160',low,prior/'prior-160/relative-model.npy',old_priors[160.]['metrics']),
           ('stage028_sefd10000_prior240',low,low/'synthesis/rml/relative-model.npy',low_summary['metrics']),
           ('stage028_sefd10000_prior320',low,prior/'prior-320/relative-model.npy',old_priors[320.]['metrics'])]
    rows=[];panels=[]
    for label,root,image,old in cases:
        start=time.perf_counter();truth_path=root/'truth-relative.npy';truth=np.load(truth_path);model=np.load(image)
        metric,a,b,registered=compare_relative(truth,model,16)
        assert abs(metric['registered_flux_retained_fraction']-1)<1e-12
        assert metric['registration_diagnostics']['selected_coordinate_converged']
        rows.append({'case':label,'truth_sha256':sha(truth_path),'recovered_sha256':sha(image),
            'spectral_sha256':sha(root/'synthesis/visibility.npz'),'original_saved_metrics':old,
            'full_support_metrics':metric,'evaluation_elapsed_s':time.perf_counter()-start})
        panels.append((label,a,b,registered))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(len(rows),3,figsize=(10,11))
    for row,(label,a,b,registered) in zip(axes,panels):
        for axis,title,image in zip(row,['Truth, display field','RML, raw display','RML, translated display'],[a,b,registered]):
            axis.imshow(image,origin='lower',cmap='inferno',vmin=0,vmax=a.max());axis.set_title(title,fontsize=10)
        row[0].set_ylabel(label.replace('stage','').replace('_','\n'),fontsize=9)
    fig.suptitle('Display crops only; reported errors include full padded support',fontsize=12)
    fig.tight_layout();fig.savefig(out/'comparison.png',dpi=140);plt.close(fig)
    summary={'type':'fixed_image_full_support_registration','rows':rows,
        'rml_reoptimized':False,'comparison_version':2,
        'limits':'Truth is used for evaluation only. Original recovered arrays and visibilities unchanged, identified by SHA. Whole padded support and bounded translation, not astrometry or statistical confidence intervals. Continuous refinement is deterministic numerical multistart, not a mathematical global-optimum proof.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--high-sensitivity-run',required=True)
    p.add_argument('--low-sensitivity-run',required=True);p.add_argument('--prior-run',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();s=run(a.high_sensitivity_run,a.low_sensitivity_run,a.prior_run,a.output)
    print(json.dumps([{'case':r['case'],'old_percent':100*r['original_saved_metrics']['registered_nrmse'],
        'full_percent':100*r['full_support_metrics']['registered_nrmse'],
        'shift_arcsec':r['full_support_metrics']['registration_shift_yx_arcsec'],
        'boundary':r['full_support_metrics']['registration_boundary_reached']} for r in s['rows']],indent=2))
