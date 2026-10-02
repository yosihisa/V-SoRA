import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.signal import fftconvolve
from astropy.io import fits
from vsora_formats.visibility import load_visibility
from .dirty import dirty_image
from .clean import clean
from vsora_observation.geometry import tangent_grid, ARCSEC_RAD


def compare_models(truth, model, pixel_arcsec, common_beam_arcsec=110):
    """Compare both Jy/pixel models at a common peak-normalized Gaussian beam.

    Excludes dirty-beam residuals and never renormalizes the reconstructed flux.
    """
    n=truth.shape[0];axis=np.arange(-n//2,n//2+1)
    yy,xx=np.meshgrid(axis,axis,indexing='ij')
    beam=np.exp(-4*np.log(2)*(xx*xx+yy*yy)/(common_beam_arcsec/pixel_arcsec)**2)
    a=fftconvolve(truth,beam,mode='same');b=fftconvolve(model,beam,mode='same')
    region=np.hypot(xx[:n,:n],yy[:n,:n])*pixel_arcsec<=260
    av,bv=a[region],b[region]
    norm=np.linalg.norm(av)
    correlation=float(np.corrcoef(av,bv)[0,1]) if np.std(bv)>0 and np.std(av)>0 else None
    return {'common_beam_arcsec':common_beam_arcsec,
            'nrmse':float(np.linalg.norm(bv-av)/norm),
            'correlation':correlation,
            'model_flux_ratio':float(model.sum()/truth.sum()),
            'evaluation':'CLEAN model only, common beam, fixed 260 arcsec region; no flux renormalization'},a,b


def write_image_fits(path,image,config,unit,beam_fwhm_arcsec=None):
    h=fits.Header()
    h['CTYPE1']='RA---SIN';h['CTYPE2']='DEC--SIN'
    h['CRVAL1']=config['source']['ra_deg'];h['CRVAL2']=config['source']['dec_deg']
    h['CRPIX1']=image.shape[1]//2+1;h['CRPIX2']=image.shape[0]//2+1
    # Internal x points east. FITS need not have negative RA increment.
    h['CDELT1']=config['image']['pixel_arcsec']/3600;h['CDELT2']=h['CDELT1']
    h['RADESYS']='ICRS';h['BUNIT']=unit;h['ORIGIN']='V-SoRA'
    h['FREQ']=config['observation']['frequency_hz']
    if beam_fwhm_arcsec is not None:
        h['BMAJ']=beam_fwhm_arcsec/3600;h['BMIN']=h['BMAJ'];h['BPA']=0.
    fits.writeto(path,np.asarray(image,dtype='float32'),h,checksum=True)


def image_visibility(path,output,clean_radius_arcsec=None):
    out=Path(output)
    if out.exists():
        raise FileExistsError('output directory already exists')
    d=load_visibility(path);config=d['metadata']['config'];im=config['image']
    dirty,psf=dirty_image(d['uvw_lambda'],d['vis_jy'],im['pixels'],im['pixel_arcsec'],d['weights'])
    uvnorm=np.linalg.norm(d['uvw_lambda'][...,:2],axis=-1)
    beam_arcsec=206264.806247/max(uvnorm.max(),1)
    # circular lambda/B reference beam, not a fitted telescope beam
    mask=None
    if clean_radius_arcsec is not None:
        l,m=tangent_grid(im['pixels'],im['pixel_arcsec'])
        mask=np.hypot(l,m)<=clean_radius_arcsec*ARCSEC_RAD
    # Stop at 3 thermal sigma when noise is enabled; floor is relative to peak.
    image_sigma=1/np.sqrt(d['weights'].sum())
    threshold=max(abs(dirty).max()*1e-3,3*image_sigma if config['noise']['enabled'] else 0,1e-8)
    result=clean(dirty,psf,threshold=threshold,max_iterations=5000,mask=mask,
                 beam_fwhm_pixels=beam_arcsec/im['pixel_arcsec'])
    out.mkdir(parents=True)
    write_image_fits(out/'dirty.fits',dirty,config,'Jy/beam')
    write_image_fits(out/'psf.fits',psf,config,'1')
    write_image_fits(out/'model.fits',result['model_jy_pixel'],config,'Jy/pixel')
    write_image_fits(out/'restored.fits',result['restored_jy_clean_beam'],config,'Jy/beam',beam_arcsec)
    write_image_fits(out/'residual.fits',result['residual_jy_dirty_beam'],config,'Jy/beam')
    summary={k:v for k,v in result.items() if not isinstance(v,np.ndarray)}
    summary['beam_note']='Circular lambda/max(projected baseline), not fitted PSF'
    summary['model_flux_jy']=float(result['model_jy_pixel'].sum())
    summary['visibility_samples']=int(d['vis_jy'].size)
    summary['image_peak_jy']=float(result['restored_jy_clean_beam'].max())
    summary['thermal_image_sigma_jy']=float(image_sigma)
    summary['clean_threshold_jy']=float(threshold)
    summary['clean_radius_arcsec']=clean_radius_arcsec
    summary['w_phase_at_200arcsec_rad']=float(2*np.pi*np.max(np.abs(d['uvw_lambda'][...,2]))*(1-np.sqrt(1-(200*ARCSEC_RAD)**2)))
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    fig,axes=plt.subplots(1,4,figsize=(14,3.4))
    for ax,title,data in zip(axes,['Dirty','PSF','CLEAN model','Restored'],[dirty,psf,result['model_jy_pixel'],result['restored_jy_clean_beam']]):
        plot=ax.imshow(data,origin='lower',cmap='inferno');ax.set_title(title)
        fig.colorbar(plot,ax=ax,shrink=.7)
    fig.tight_layout();fig.savefig(out/'images.png',dpi=120);plt.close(fig)
    return summary


def main():
    p=argparse.ArgumentParser(description='Direct Fourier imaging and reference CLEAN')
    p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    p.add_argument('--clean-radius-arcsec',type=float)
    a=p.parse_args();print(json.dumps(image_visibility(a.input,a.output,a.clean_radius_arcsec),indent=2))


if __name__=='__main__': main()
