"""Import actual FITS-IDI and restore its weights, without simulation truth.

Invoke through tools/run_casa.py, after preparing a bridge with casa-input.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',required=True);p.add_argument('--bridge',required=True)
    p.add_argument('--output',required=True);p.add_argument('--image',action='store_true')
    a=p.parse_args();source=Path(a.input);out=Path(a.output)
    if out.exists(): raise FileExistsError('use a new output directory')
    with np.load(a.bridge,allow_pickle=False) as b:
        arrays={k:b[k] for k in b.files if k!='metadata_json'}
        metadata=json.loads(str(b['metadata_json']))
    digest=hashlib.sha256()
    with source.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): digest.update(block)
    if metadata.get('schema_version')!=1 or digest.hexdigest()!=metadata['source_sha256']:
        raise ValueError('bridge does not match current FITS input')
    weights=arrays['weights'];target=arrays['visibilities']
    if weights.shape!=target.shape or not np.isfinite(weights).all() or np.any(weights<0):
        raise ValueError('invalid bridge weights')
    out.mkdir(parents=True)
    report={**metadata,'state':'incomplete'}
    summary=out/'summary.json';summary.write_text(json.dumps(report,indent=2)+'\n')
    sys.argv=[sys.argv[0],'--noconfig']
    try:
        from casatasks import importfitsidi,tclean,exportfits
        from casatools import table,image
        import importlib.metadata as versions
        ms=out/'observation.ms'
        importfitsidi(fitsidifile=str(source.resolve()),vis=str(ms.resolve()),constobsid=True,coordframe='J2000')
        tb=table();tb.open(str(ms))
        actual=tb.getcol('DATA')[0];uvw=tb.getcol('UVW').T
        pairs=np.column_stack([tb.getcol('ANTENNA1'),tb.getcol('ANTENNA2')])
        times=tb.getcol('TIME');flags=tb.getcol('FLAG')[0];interval=tb.getcol('INTERVAL');tb.close()
        tb.open(str(ms/'SPECTRAL_WINDOW'));frequency=tb.getcol('CHAN_FREQ')[:,0];tb.close()
        if actual.shape!=target.shape or not np.array_equal(pairs,arrays['pairs']):
            raise ValueError('CASA channel/row/baseline order differs')
        errors={
            'data_relative_error':float(np.linalg.norm(actual-target)/max(np.linalg.norm(target),1e-20)),
            'uvw_max_error_m':float(np.max(abs(uvw-arrays['uvw_m']))),
            'time_max_error_s':float(np.max(abs(times-arrays['times_mjd_seconds']))),
            'frequency_max_error_hz':float(np.max(abs(frequency-arrays['frequencies_hz']))),
            'interval_max_error_s':float(np.max(abs(interval-arrays['integration_s'])))}
        if (errors['data_relative_error']>1e-6 or errors['uvw_max_error_m']>1e-6
                or errors['time_max_error_s']>2e-6 or errors['frequency_max_error_hz']>1e-5
                or errors['interval_max_error_s']>1e-6):
            raise ValueError('CASA values differ from input FITS-IDI')
        if not np.array_equal(flags,weights==0): raise ValueError('CASA flags differ from input zero weights')
        spectrum=weights[None,:,:].astype('float32');row=weights.mean(axis=0,keepdims=True)
        sigma=lambda w: np.divide(1,np.sqrt(w),out=np.zeros_like(w),where=w>0)
        tb.open(str(ms),nomodify=False)
        try:
            if 'WEIGHT_SPECTRUM' not in tb.colnames(): raise ValueError('CASA WEIGHT_SPECTRUM missing')
            tb.putcol('WEIGHT',row);tb.putcol('SIGMA',sigma(row))
            tb.putcol('WEIGHT_SPECTRUM',spectrum)
            if 'SIGMA_SPECTRUM' in tb.colnames(): tb.putcol('SIGMA_SPECTRUM',sigma(spectrum))
            tb.putcol('FLAG',spectrum==0);tb.putcol('FLAG_ROW',np.all(spectrum==0,axis=(0,1)))
        finally: tb.close()
        tb.open(str(ms))
        restored=tb.getcol('WEIGHT_SPECTRUM')[0];tb.close()
        if not np.array_equal(restored,weights): raise ValueError('CASA weight restoration differs')
        report.update(errors)
        report.update(casatools_version=versions.version('casatools'),casatasks_version=versions.version('casatasks'),
                      weight_max_error=0.,state='complete')
        if a.image:
            name=str(out/'image')
            tclean(vis=str(ms),imagename=name,imsize=128,cell='16arcsec',stokes='XX',specmode='mfs',
                   gridder='standard',deconvolver='hogbom',weighting='natural',niter=0,
                   interactive=False,parallel=False)
            ia=image();ia.open(name+'.residual');pixels=np.squeeze(ia.getchunk());ia.close()
            peak=np.unravel_index(np.argmax(pixels),pixels.shape)
            report.update(dirty_peak_xy=[int(x) for x in peak],dirty_peak_jy=float(pixels[peak]))
            exportfits(imagename=name+'.residual',fitsimage=str(out/'dirty.fits'),overwrite=False)
    except Exception as e:
        report.update(state='incomplete',error_type=type(e).__name__)
        summary.write_text(json.dumps(report,indent=2)+'\n');raise
    summary.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
