import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from astropy.io import fits
from vsora_formats.visibility import load_visibility
from .dirty import dirty_image
from .clean import clean


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


def image_visibility(path,output):
    out=Path(output)
    if out.exists():
        raise FileExistsError('output directory already exists')
    d=load_visibility(path);config=d['metadata']['config'];im=config['image']
    dirty,psf=dirty_image(d['uvw_lambda'],d['vis_jy'],im['pixels'],im['pixel_arcsec'],d['weights'])
    uvnorm=np.linalg.norm(d['uvw_lambda'][...,:2],axis=-1)
    beam_arcsec=206264.806247/max(uvnorm.max(),1)
    # circular lambda/B reference beam, not a fitted telescope beam
    result=clean(dirty,psf,threshold=max(abs(dirty).max()*1e-3,1e-8),
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
    a=p.parse_args();print(json.dumps(image_visibility(a.input,a.output),indent=2))


if __name__=='__main__': main()
