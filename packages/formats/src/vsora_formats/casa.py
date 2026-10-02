"""Prepare a CASA import bridge from the actual V-SoRA FITS-IDI contents."""
import hashlib
import json
from pathlib import Path
import numpy as np
from astropy.io import fits


def prepare_casa_input(input_path,output_path):
    source=Path(input_path);output=Path(output_path)
    if output.exists(): raise FileExistsError(output.name)
    with fits.open(source,checksum=True) as hdus:
        if any(h.verify_checksum()!=1 or h.verify_datasum()!=1 for h in hdus):
            raise ValueError('FITS checksums must be present and valid')
        if 'VSORA_META' not in hdus: raise ValueError('only V-SoRA FITS-IDI supported')
        meta=json.loads(hdus['VSORA_META'].data['JSON'][0])
        uv=hdus['UV_DATA'];h=uv.header;data=uv.data
        if meta.get('schema_version') not in (2,3) or meta.get('visibility_storage')!='conjugated_internal':
            raise ValueError('re-export old IDI to the CASA compatible v2/v3 profile')
        if h.get('NO_STKD')!=1 or h.get('STK_1')!=-5 or h.get('NO_BAND')!=1 or h.get('WEIGHTYP')!='NORMAL':
            raise ValueError('only one-band XX NORMAL inverse variance supported')
        nchan=h['NO_CHAN'];flux=np.asarray(data['FLUX']).reshape(len(data),nchan,3)
        weights=flux[...,2].T.astype('float32')
        values=(flux[...,0]-1j*flux[...,1]).T
        if not np.isfinite(flux).all() or np.any(weights<0): raise ValueError('invalid FLUX/weights')
        packed=np.asarray(data['BASELINE']);pairs=np.column_stack([packed//256-1,packed%256-1])
        seconds=np.column_stack([data[k] for k in ('UU','VV','WW')])
        times=((np.asarray(data['DATE'])-2400000.5)+np.asarray(data['TIME']))*86400
        frequencies=h['REF_FREQ']+(np.arange(nchan)+1-h['REF_PIXL'])*h['CHAN_BW']
        arrays=dict(visibilities=values,weights=weights,pairs=pairs,uvw_m=seconds*299792458.,
                    times_mjd_seconds=times,frequencies_hz=frequencies,
                    integration_s=np.asarray(data['INTTIM']))
        if any(not np.isfinite(a).all() for a in arrays.values()): raise ValueError('nonfinite CASA metadata')
    digest=hashlib.sha256()
    with source.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): digest.update(block)
    sha=digest.hexdigest()
    report={'schema_version':1,'source_sha256':sha,'rows':len(data),'channels':nchan,
            'flagged_channel_rows':int((weights==0).sum()),
            'weight_policy':'Restore input NORMAL inverse variance, zero weight means flag'}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as f:
        np.savez_compressed(f,**arrays,metadata_json=json.dumps(report))
    return report
