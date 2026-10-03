"""One-cell first-order closure noise from a known full visibility covariance.

Forward-model diagnostic. No inference of unknown receiver/sky covariance and
no automatic change to production RML likelihoods or data selection.
"""
import numpy as np
from .closure import closure_design, wrap_phase


def joint_closure_noise(mean_visibilities, real_covariance, pairs, min_snr=5.):
    """Propagate [all Re V, all Im V] covariance to [phase, log amplitude].

    For nonzero mean V, d arg(V)=Im(dV/V), d log|V|=Re(dV/V).
    The returned joint matrix retains phase/amplitude cross covariance and
    redundant rows. It may be singular and is not inverted here. Invalid rows
    have zero values/Jacobian/covariance and must be excluded using joint_valid.
    min_snr uses |mean V| / sqrt(mean real/imaginary variance), not a measured
    detection probability or a proof of the Gaussian closure approximation.
    """
    v=np.asarray(mean_visibilities);raw=np.asarray(real_covariance)
    design=closure_design(pairs);b=len(pairs)
    if (v.shape!=(b,) or not np.iscomplexobj(v) or not np.isfinite(v).all()
            or np.iscomplexobj(raw) or raw.shape!=(2*b,2*b)
            or not np.isfinite(raw).all() or not np.isfinite(min_snr) or min_snr<5
            or len(np.unique(pairs))>8):
        raise ValueError('one finite complex mean per baseline, real covariance, min_snr >= 5, up to 8 stations required')
    c=np.asarray(raw,float);scale=max(float(np.max(abs(c))),np.finfo(float).tiny)
    if not np.allclose(c/scale,c.T/scale,rtol=1e-10,atol=1e-12):
        raise ValueError('visibility covariance must be symmetric')
    c=c*.5+c.T*.5
    if np.linalg.eigvalsh(c/scale).min() < -1e-12:
        raise ValueError('visibility covariance must be positive semidefinite')
    sigma=np.sqrt(np.maximum(0.,.5*np.diag(c)[:b]+.5*np.diag(c)[b:]))
    amplitude=abs(v);snr=np.zeros(b)
    if not np.isfinite(amplitude).all():
        raise ValueError('mean visibility amplitude exceeds finite numerical range')
    with np.errstate(over='ignore',divide='ignore',invalid='ignore'):
        np.divide(amplitude,sigma,out=snr,where=sigma>0)
    snr[(sigma==0)&(amplitude>0)]=np.inf
    baseline_valid=(amplitude>0)&(snr>=min_snr)
    inverse=np.zeros(b,complex)
    with np.errstate(over='ignore',divide='ignore',invalid='ignore'):
        np.divide(1.,v,out=inverse,where=baseline_valid)
    if not np.isfinite(inverse).all():
        raise ValueError('closure propagation exceeds finite numerical range')
    phase_j=np.c_[np.diag(inverse.imag),np.diag(inverse.real)]
    amp_j=np.c_[np.diag(inverse.real),np.diag(-inverse.imag)]
    matrices=[design['phase_matrix'],design['logamp_matrix']]
    valid=[np.all(baseline_valid[None,:]|(a==0),axis=1) for a in matrices]
    joint_valid=np.r_[*valid]
    with np.errstate(over='ignore',invalid='ignore'):
        jac=np.vstack([matrices[0] @ phase_j,matrices[1] @ amp_j])
    jac[~joint_valid]=0.
    with np.errstate(over='ignore',invalid='ignore'):
        propagated=jac @ c @ jac.T
    if not np.isfinite(jac).all() or not np.isfinite(propagated).all():
        raise ValueError('closure propagation exceeds finite numerical range')
    values=np.r_[wrap_phase(matrices[0] @ np.angle(v)),
        matrices[1] @ np.log(np.where(amplitude>0,amplitude,1.))]
    return {**design,'baseline_snr':snr,'baseline_valid':baseline_valid,
        'joint_valid':joint_valid,'joint_values':np.where(joint_valid,values,0.),
        'joint_jacobian':jac,'joint_covariance':(propagated+propagated.T)/2,
        'joint_parameter_order':'all closure phases rad, then all log closure amplitudes',
        'phase_count':len(matrices[0]),'logamp_count':len(matrices[1]),
        'noise_model':'First-order high-SNR propagation of known full real visibility covariance',
        'closure_distribution_gaussian_guaranteed':False,'covariance_inverted':False,
        'limits':'Known one-cell forward model; invalid/redundant rows retained with mask. No measured receiver covariance, low-SNR likelihood, inter-cell correlation, gain variation or hardware guarantee.'}
