"""Deterministic known-C reference experiment, usable outside a checkout.

Use --installed to require all imported project modules under sys.prefix.
No recording, triangle archive, unknown calibration, or image is consumed.
"""
import argparse
from decimal import Decimal, localcontext
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np
from scipy.stats import multivariate_normal
from vsora_correlator import gaussian_likelihood as api



def decimal_identity_log_ratio(c):
    """Independent real Gauss-Jordan calculation at 90 decimal digits."""
    with localcontext() as ctx:
        ctx.prec=90;n=len(c)
        a=[[Decimal.from_float(float(z)) for z in row] for row in c]
        inverse=[[Decimal(int(i==j)) for j in range(n)] for i in range(n)]
        determinant=Decimal(1)
        for j in range(n):
            pivot=a[j][j];determinant*=pivot
            a[j]=[z/pivot for z in a[j]];inverse[j]=[z/pivot for z in inverse[j]]
            for i in range(n):
                if i==j:continue
                factor=a[i][j]
                a[i]=[x-factor*y for x,y in zip(a[i],a[j],strict=True)]
                inverse[i]=[x-factor*y for x,y in zip(inverse[i],inverse[j],strict=True)]
        return float(Decimal(n)-determinant.ln()-sum(inverse[i][i] for i in range(n)))

def experiment():
    rows = []
    for n in (1, 2, 8):
        for m in (1, 37, 257):
            rng = np.random.default_rng(100000+n*1000+m)
            a = rng.normal(size=(n,n)) + 1j*rng.normal(size=(n,n))
            c0 = a @ a.conj().T + np.eye(n)
            c1 = c0 + np.diag(np.linspace(.2,.7,n))
            x = (rng.normal(size=(m,n))+1j*rng.normal(size=(m,n))) @ np.linalg.cholesky(c0).T / np.sqrt(2)
            s = api.sample_second_moment(x)
            def real_nll(c):
                r = .5*np.block([[c.real,-c.imag],[c.imag,c.real]])
                return float(-np.sum(multivariate_normal.logpdf(
                    np.concatenate([x.real,x.imag],axis=1),cov=r)))
            real0,real1 = real_nll(c0),real_nll(c1)
            base_llr = api.gaussian_log_likelihood_ratio(c0,c1,s,m)
            for scale in (1e-120,1.,1e120):
                actual = api.gaussian_nll(c0*scale,s*scale,m)
                expected = real0-m*n*np.log(np.pi)+m*n*np.log(scale)
                ratio = api.gaussian_log_likelihood_ratio(c0*scale,c1*scale,s*scale,m)
                direct = sum(np.outer(row,row.conj()) for row in x)/m
                assert np.allclose(s,direct,rtol=3e-14,atol=3e-14)
                assert np.isclose(actual,expected,rtol=3e-13,atol=3e-10)
                assert np.isclose(ratio,real0-real1,rtol=3e-10,atol=5e-10)
                assert np.isclose(ratio,base_llr,rtol=3e-12,atol=5e-11)
                assert api.gaussian_log_likelihood_ratio(c0*scale,c0*scale,s*scale,m)==0
                rows.append({'stations':n,'common_independent_modes':m,'common_covariance_scale':scale,
                    'nll_without_constant':actual,'log_likelihood_ratio_c1_over_c0':ratio,
                    'independent_real_gaussian_nll_reference':expected,
                    'independent_real_gaussian_llr_reference':real0-real1,
                    'nll_reference_abs_difference':abs(actual-expected),
                    'llr_reference_abs_difference':abs(ratio-(real0-real1)),
                    'direct_moment_max_abs_difference':float(np.max(np.abs(s-direct))),
                    'equal_covariances_exact_zero':True,'state':'complete'})
    small = []
    for delta in (-.2,-1e-5,-1e-12,1e-12,1e-5,.2):
        c1 = 1+delta
        with localcontext() as ctx:
            ctx.prec=90;d=Decimal.from_float(c1)-1
            expected=float(-(1+d).ln()+d/(1+d))
        actual=api.gaussian_log_likelihood_ratio([[1]],[[c1]],[[1]],1)
        assert np.isclose(actual,expected,rtol=3e-13,atol=1e-36)
        small.append({'covariance0':1.,'covariance1':c1,'second_moment':1.,'modes':1,
            'log_likelihood_ratio':actual,'decimal_90_digit_reference':expected,
            'relative_error':abs((actual-expected)/expected),'state':'complete'})
    matrix_small=[]
    for n,delta,complex_case in [(2,1e-5,False),(2,1e-12,False),(8,1e-5,False),(8,1e-12,False),(8,1e-12,True)]:
        rng=np.random.default_rng(100)
        a=rng.normal(size=(n,n))
        if complex_case:a=a+1j*rng.normal(size=(n,n))
        c1=np.eye(n)+delta*(a+a.conj().T)
        real=np.block([[c1.real,-c1.imag],[c1.imag,c1.real]])
        expected=decimal_identity_log_ratio(real)/2
        actual=api.gaussian_log_likelihood_ratio(np.eye(n),c1,np.eye(n),1)
        assert np.isclose(actual,expected,rtol=2e-13,atol=1e-36)
        matrix_small.append({'stations':n,'perturbation_scale':delta,'complex_covariance':complex_case,
            'seed':100,'log_likelihood_ratio':actual,'decimal_90_digit_reference':expected,
            'relative_error':abs((actual-expected)/expected),'state':'complete'})
    return {'state':'complete','type':'known_covariance_gaussian_reference','matrix_cases':rows,
        'matrix_tiny_difference_cases':matrix_small,'matrix_tiny_difference_case_count':len(matrix_small),
        'tiny_difference_cases':small,'matrix_case_count':len(rows),'tiny_difference_case_count':len(small),
        'assumptions':['zero known mean','proper complex Gaussian','iid rows','all stations share all rows',
                       'known positive definite fixed covariance','known independent mode count'],
        'image_likelihood_defined':False,'unknown_gain_sefd_lo_estimated':False,
        'real_hardware_validation_performed':False,'production_rml_noise_model_changed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True);p.add_argument('--reference');p.add_argument('--installed',action='store_true')
    a=p.parse_args();out=Path(a.output)
    if out.exists():raise FileExistsError('output already exists; refusing to overwrite')
    if a.installed:
        checkout=Path(__file__).resolve().parents[1]
        assert not Path.cwd().resolve().is_relative_to(checkout)
        assert 'PYTHONPATH' not in os.environ
        assert not (Path.cwd()/'tools/run.py').exists()
    summary=experiment()
    if a.reference:assert summary==json.loads(Path(a.reference).read_text())
    modules={n:m for n,m in sys.modules.items() if n.startswith('vsora_') and getattr(m,'__file__',None)}
    if a.installed:assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in modules.values())
    out.mkdir(parents=True,exist_ok=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    (out/'installation.json').write_text(json.dumps({'state':'complete','installed_checked':a.installed,
        'all_project_modules_under_runtime_prefix':a.installed,'project_modules':sorted(modules),
        'reference_json_identical':bool(a.reference),
        'api_module_sha256':hashlib.sha256(Path(api.__file__).read_bytes()).hexdigest()},indent=2)+'\n')
    print(json.dumps({'state':'complete','matrix_cases':len(summary['matrix_cases']),
        'tiny_difference_cases':len(summary['tiny_difference_cases']),
        'matrix_tiny_difference_cases':len(summary['matrix_tiny_difference_cases']),'installed_checked':a.installed}))


if __name__=='__main__':main()
