"""Unknown sky/gain rate pilot -> actual IQ derotation -> short FX closures."""
import argparse
import json
from pathlib import Path
import numpy as np
from vsora_correlator.fx import fx_correlate_series, remove_fringe_rate
from vsora_correlator.rate import estimate_station_rates
from vsora_imaging.closure import form_closures


def run(output,seed=22):
    out=Path(output)
    if out.exists():raise FileExistsError('output already exists')
    out.mkdir(parents=True)
    fs=2048000.; pilot=.512; exposure=.3; ns=int(fs*pilot)
    rng=np.random.default_rng(seed)
    gaussian=lambda shape:(rng.normal(size=shape)+1j*rng.normal(size=shape))/np.sqrt(2)
    sky=np.sqrt(1000.)*gaussian(ns);receiver=np.sqrt(10000.)*gaussian((4,ns))
    rates=np.array([0.,17.3,-11.7,26.1]);gain=np.array([.4,3.,1.5,.75])*np.exp(1j*np.array([0.,.7,-1.1,2.]))
    t=np.arange(ns)/fs
    iq=(sky[None]+receiver)*gain[:,None]*np.exp(2j*np.pi*rates[:,None]*t)
    # 1 ms pilot integrations; FFT32, 64 FFT blocks per time cell.
    p=fx_correlate_series(iq,fs,fft_length=32,blocks_per_integration=64)
    estimate=estimate_station_rates(p)
    correction=np.array(estimate['station_rates_hz'])
    corrected=remove_fringe_rate(iq,fs,correction,time_reference_s=estimate['time_reference_s'])
    samples=int(fs*exposure);blocks=samples//32
    before=fx_correlate_series(iq[:,:samples],fs,fft_length=32,blocks_per_integration=blocks)
    after=fx_correlate_series(corrected[:,:samples],fs,fft_length=32,blocks_per_integration=blocks)
    cb=form_closures(before['vis_jy'],before['weights'],before['pairs'],min_snr=10)
    ca=form_closures(after['vis_jy'],after['weights'],after['pairs'],min_snr=10)
    expected=1000*gain[after['pairs'][:,0]]*gain[after['pairs'][:,1]].conj()
    norms={name:float(np.sqrt(np.mean(ca[name][ca[name+'_valid']]**2)))
           if ca[name+'_valid'].any() else None for name in ('phase','logamp')}
    summary={'type':'closure_rate_validation','seed':seed,'sample_rate_hz':fs,'pilot_s':pilot,
             'pilot_cadence_s':.001,'image_integration_s':exposure,'fft_length':32,
             'true_station_rates_hz':rates.tolist(),'estimate':estimate,
             'maximum_rate_error_hz':float(abs(correction-rates).max()),
             'coherence_before_median':float(np.median(abs(before['vis_jy'].mean(axis=1)/expected[None]))),
             'coherence_after_median':float(np.median(abs(after['vis_jy'].mean(axis=1)/expected[None]))),
             'valid_closures_before':{k:int(cb[k+'_valid'].sum()) for k in ('phase','logamp')},
             'valid_closures_after':{k:int(ca[k+'_valid'].sum()) for k in ('phase','logamp')},
             'closure_rms_after':norms,
             'signal':'Continuous common Gaussian point sky1000Jy plus independent receiver SEFD10000Jy, constant unknown station gains',
             'limits':'No known sky amplitude/phase used in inference. Supplied uniform sample alignment. No VDIF quantization, RFI, clock drift, extended sky or phase noise.'}
    assert summary['maximum_rate_error_hz']<.05
    assert .9<summary['coherence_after_median']<1.1
    assert all(value is not None and value<.2 for value in norms.values())
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (out/'rate-only.json').write_text(json.dumps(estimate,indent=2)+'\n')
    np.savez_compressed(out/'corrected-spectral.npz',**after)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,3.5))
    axes[0].plot(rates,'o',label='Generating rates');axes[0].plot(correction,'x',label='Estimated, no sky model')
    axes[0].set(xlabel='Station',ylabel='Relative rate (Hz)',title='0.512 s pilot');axes[0].legend()
    axes[1].bar(np.arange(6)-.15,abs(before['vis_jy'].mean(axis=1)[0]/expected),width=.3,label='Before')
    axes[1].bar(np.arange(6)+.15,abs(after['vis_jy'].mean(axis=1)[0]/expected),width=.3,label='After estimated correction')
    axes[1].set(xlabel='Baseline',ylabel='Coherence ratio',title='Actual IQ -> FX, 0.3 s');axes[1].legend()
    fig.tight_layout();fig.savefig(out/'rate.png',dpi=140);plt.close(fig)
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--seed',type=int,default=22)
    a=p.parse_args();print(json.dumps(run(a.output,a.seed),indent=2))
