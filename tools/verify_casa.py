"""Independent CASA FITS-IDI ingestion and point-source image verification.

Run with the isolated CASA interpreter and configured local CASA data.
"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',required=True);p.add_argument('--expected',required=True)
    p.add_argument('--output',required=True);p.add_argument('--image',action='store_true')
    a=p.parse_args()
    out=Path(a.output)
    if out.exists(): raise FileExistsError('use a new output directory')
    out.mkdir(parents=True)
    # Let CASA skip user config; the caller supplies an explicit site config.
    sys.argv=[sys.argv[0],'--noconfig']
    from casatasks import importfitsidi,tclean,exportfits
    from casatools import table,image
    import importlib.metadata as versions
    ms=out/'observation.ms'
    importfitsidi(fitsidifile=str(Path(a.input).resolve()),vis=str(ms.resolve()),constobsid=True,coordframe='J2000')
    tb=table();tb.open(str(ms))
    data=tb.getcol('DATA')[0];uvw=tb.getcol('UVW').T
    flags=tb.getcol('FLAG')[0]
    antennas=np.column_stack([tb.getcol('ANTENNA1'),tb.getcol('ANTENNA2')])
    ms_times=tb.getcol('TIME');integration=tb.getcol('INTERVAL');weights=tb.getcol('WEIGHT')
    tb.close()
    with np.load(a.expected,allow_pickle=False) as expected:
        original=expected['vis_jy']
        target=original.ravel()[None,:] if original.ndim==2 else original.transpose(1,0,2).reshape(original.shape[1],-1)
        targetuvw=expected['uvw_m'].reshape(-1,3)
        target_times=np.repeat(expected['times_mjd'],original.shape[-1])*86400
        target_pairs=np.tile(expected['pairs'],(expected['vis_jy'].shape[0],1))
        expected_peak=expected['expected_dirty_peak_xy'].tolist() if 'expected_dirty_peak_xy' in expected else None
        expected_flux=float(expected['expected_flux_jy']) if 'expected_flux_jy' in expected else None
        ew=expected['weights'] if 'weights' in expected else None
        expected_weights=None if ew is None else ew.ravel()[None,:] if ew.ndim==2 else ew.transpose(1,0,2).reshape(ew.shape[1],-1)
        expected_frequency=expected['frequencies_hz'] if 'frequencies_hz' in expected else None
    if target.shape!=data.shape: raise ValueError('CASA channel/row count differs')
    report={'casatools_version':versions.version('casatools'),'casatasks_version':versions.version('casatasks'),
            'ms_rows':data.shape[-1],'channels':data.shape[0],'flags':int(flags.sum()),
            'data_relative_error_direct':float(np.linalg.norm(data-target)/np.linalg.norm(target)),
            'data_relative_error_conjugate':float(np.linalg.norm(data-target.conj())/np.linalg.norm(target)),
            'uvw_relative_error_direct':float(np.linalg.norm(uvw-targetuvw)/np.linalg.norm(targetuvw)),
            'uvw_relative_error_negative':float(np.linalg.norm(uvw+targetuvw)/np.linalg.norm(targetuvw)),
            'time_max_error_s':float(np.max(abs(ms_times-target_times))),
            'antenna_pairs_match':bool(np.array_equal(antennas,target_pairs)),
            'interval_min_s':float(integration.min()),'interval_max_s':float(integration.max()),
            'weight_min':float(weights.min()),'weight_max':float(weights.max())}
    if expected_weights is not None:
        row_weights=expected_weights.mean(axis=0)
        positive=row_weights>0
        report['import_weight_scale_median']=float(np.median(weights[0,positive]/row_weights[positive]))
        # importfitsidi initializes correlator weights via exposure*bandwidth.
        # Our NORMAL weights already represent inverse variance in Jy^-2.
        # Restore these explicitly before later CASA calibration/imaging.
        correct=row_weights[None,:].astype('float32');spectrum=expected_weights[None,:,:].astype('float32')
        tb.open(str(ms),nomodify=False)
        tb.putcol('WEIGHT',correct)
        tb.putcol('SIGMA',np.where(correct>0,1/np.sqrt(correct),0).astype('float32'))
        if 'WEIGHT_SPECTRUM' not in tb.colnames(): raise ValueError('CASA import did not create WEIGHT_SPECTRUM')
        tb.putcol('WEIGHT_SPECTRUM',spectrum)
        if 'SIGMA_SPECTRUM' in tb.colnames():
            sigma=np.divide(1,np.sqrt(spectrum),out=np.zeros_like(spectrum),where=spectrum>0)
            tb.putcol('SIGMA_SPECTRUM',sigma)
        tb.close()
        tb.open(str(ms));actual_weights=tb.getcol('WEIGHT_SPECTRUM')[0];tb.close()
        report['weight_policy']='Restore input NORMAL inverse-variance weights after CASA importfitsidi initialization'
        report['weight_relative_error_after_restore']=float(np.linalg.norm(actual_weights-expected_weights)/np.linalg.norm(expected_weights))
        report['import_flags_match_zero_weights']=bool(np.array_equal(flags,expected_weights==0))
    if expected_frequency is not None:
        tb.open(str(ms/'SPECTRAL_WINDOW'));actual_frequency=tb.getcol('CHAN_FREQ')[:,0];tb.close()
        report['frequency_max_error_hz']=float(np.max(abs(actual_frequency-expected_frequency)))
    if a.image:
        name=str(out/'point')
        result=tclean(vis=str(ms),imagename=name,imsize=128,cell='16arcsec',stokes='XX',
                      specmode='mfs',gridder='standard',deconvolver='hogbom',
                      weighting='natural',niter=0,interactive=False,parallel=False)
        ia=image();ia.open(name+'.residual')
        array=np.squeeze(ia.getchunk());ia.close()
        peak=np.unravel_index(np.argmax(array),array.shape)
        report['dirty_peak_xy']=[int(x) for x in peak]
        report['dirty_peak_jy']=float(array[peak])
        report['expected_dirty_peak_xy']=expected_peak
        report['image_position_correct']=bool(list(peak)==expected_peak)
        report['image_flux_relative_error']=float(abs(array[peak]/expected_flux-1)) if expected_flux else None
        exportfits(imagename=name+'.residual',fitsimage=str(out/'point-dirty.fits'),overwrite=False)
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if report['data_relative_error_direct']>1e-6 or report['uvw_relative_error_negative']>1e-6 or report['time_max_error_s']>2e-6 or not report['antenna_pairs_match']:
        raise AssertionError('CASA metadata/visibility conversion failed')
    if a.image and (not report['image_position_correct'] or report['image_flux_relative_error']>.002):
        raise AssertionError('CASA image position/amplitude failed')
    if report.get('weight_relative_error_after_restore',0)>1e-6:
        raise AssertionError('CASA weight restoration failed')
    if report.get('frequency_max_error_hz',0)>1e-5 or not report.get('import_flags_match_zero_weights',True):
        raise AssertionError('CASA frequencies/flags differ')


if __name__=='__main__': main()
