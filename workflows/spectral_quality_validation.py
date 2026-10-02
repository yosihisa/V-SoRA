"""Reproducible Gaussian/RFI tests; no physical receiver RFI claims."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from vsora_observation import load_config
from vsora_observation.geometry import observation_geometry
from vsora_simulator.iq import generate_iq
from vsora_correlator.fx import fx_correlate_series
from vsora_correlator.quality import channel_diagnostics
from vsora_imaging.dirty import dirty_image


QUALITY={'channel_weights':True,'min_sk_blocks':128,'sk_bounds':[.3,3.], 'exclude_rf_ranges_hz':[]}


def run(output):
    out=Path(output)
    if out.exists(): raise FileExistsError('new output required')
    out.mkdir(parents=True)
    false_flags=0;cells=0;sk_values=[]
    for seed in range(20):
        rng=np.random.default_rng(seed)
        x=(rng.normal(size=(128,64,4))+1j*rng.normal(size=(128,64,4)))/np.sqrt(2)
        d=channel_diagnostics(x,np.ones((128,4),bool),1.42e9+np.arange(64),QUALITY)
        false_flags+=int((d['diagnostic_station_flags']!=0).sum());cells+=64*4
        sk_values.extend(d['diagnostic_station_sk'].ravel())
    root=Path(__file__).resolve().parents[1];c=load_config(root/'configs/experiments/ideal-point.json')
    g=observation_geometry(c);sky=np.zeros((64,64));sky[34,29]=1000
    x,expected=generate_iq(g['uvw_lambda'][0],g['pairs'],sky,16,[10000]*4,2048000,1.42e9,64,1024,20)
    spectrum=np.fft.fft(x.reshape(4,1024,64).transpose(1,2,0),axis=1,norm='ortho')
    spectrum[:,13,:]+=500
    spectrum[0,20,:]+=20000
    contaminated=np.fft.ifft(spectrum,axis=1,norm='ortho').transpose(2,0,1).reshape(4,-1)
    raw=fx_correlate_series(contaminated,2048000,64,1024)
    good=fx_correlate_series(contaminated,2048000,64,1024,spectral_quality=QUALITY)
    order=np.argsort(1.42e9+np.fft.fftfreq(64,1/2048000));expected=expected[order]
    def error(r):
        w=r['weights'][0];v=r['vis_jy'][0]
        data=(v*w).sum(axis=0)/w.sum(axis=0);model=(expected*w).sum(axis=0)/w.sum(axis=0)
        return float(np.linalg.norm(data-model)/np.linalg.norm(model))
    frequency=good['frequencies_hz'];uvw=g['uvw_lambda'][0][None,:,:]*frequency[:,None,None]/1.42e9
    image,psf=dirty_image(uvw,good['vis_jy'][0],64,16,good['weights'][0])
    peak=np.unravel_index(np.argmax(image),image.shape)
    report={'gaussian_seeds':20,'gaussian_fft_blocks':128,'gaussian_cells':cells,
            'false_flag_cells':false_flags,'empirical_false_flag_fraction':false_flags/cells,
            'gaussian_sk_mean':float(np.mean(sk_values)),'sk_bounds':QUALITY['sk_bounds'],
            'rfi_fft_bins':[13,20],'flagged_station_channel_cells':int((good['diagnostic_station_flags']!=0).sum()),
            'continuum_visibility_error_before':error(raw),'continuum_visibility_error_after':error(good),
            'dirty_peak_yx':[int(i) for i in peak],'expected_peak_yx':[34,29],
            'dirty_peak_jy_per_beam':float(image[peak]),'assumed_source_flux_jy':1000,
            'assumed_sefd_jy':10000,'rfi_integrations':1,'rfi_fft_blocks':1024,
            'limits':'Synthetic stationary complex Gaussian signal, fixed thresholds; no field RFI false-alarm guarantee'}
    fig,ax=plt.subplots(1,3,figsize=(13,3.6))
    ax[0].plot(frequency-1.42e9,good['diagnostic_station_sk'][0]);ax[0].axhline(.3,color='gray');ax[0].axhline(3,color='gray')
    ax[0].set(title='Spectral kurtosis',xlabel='Baseband frequency (Hz)',ylabel='SK');ax[0].set_ylim(0,8)
    ax[1].imshow(good['diagnostic_station_flags'][0].T,aspect='auto');ax[1].set(title='Station channel flags',xlabel='RF channel',ylabel='Station')
    ax[2].imshow(image,origin='lower');ax[2].set(title='Dirty image after flags',xlabel='Pixel x',ylabel='Pixel y')
    fig.tight_layout();fig.savefig(out/'quality.png',dpi=130);plt.close(fig)
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    if false_flags/cells>.01 or report['continuum_visibility_error_after']>.08 or list(peak)!=[34,29]:
        raise AssertionError('quality validation failed; recorded outputs are not a pass')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(run(a.output),indent=2))
