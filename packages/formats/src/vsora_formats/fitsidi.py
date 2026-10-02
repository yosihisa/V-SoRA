"""Limited one-band, one-channel, XX FITS-IDI candidate writer.

Columns follow AIPS Memo 114; the profile is checked with CASA importfitsidi.
The local reader intentionally only accepts files with V-SoRA provenance.
"""
import json
from pathlib import Path
import numpy as np
import astropy.units as u
from astropy.io import fits
from astropy.time import Time
from astropy.coordinates import SkyCoord,FK5,GCRS,EarthLocation
from astropy.utils import iers


def _column(name,fmt,array,unit=None):
    return fits.Column(name=name,format=fmt,array=np.asarray(array),unit=unit)


def write_fitsidi(path,geometry,vis,weights,config,metadata=None,integration_s=None):
    v=np.asarray(vis);w=np.asarray(weights);uvw=np.asarray(geometry['uvw_lambda'])
    if v.ndim!=2 or w.shape!=v.shape or uvw.shape!=(*v.shape,3):
        raise ValueError('FITS-IDI expects time/baseline continuum data')
    if any(not np.isfinite(a).all() for a in (v,w,uvw)) or np.any(w<0):
        raise ValueError('invalid visibility/weights')
    ntime,nb=v.shape;rows=v.size;nst=len(config['stations'])
    if nst>255 or any(len(s['id'])>8 for s in config['stations']):
        raise ValueError('limited IDI supports <=255 stations and IDs <=8 chars')
    p=Path(path)
    if p.exists(): raise FileExistsError(p.name)
    pairs=np.asarray(geometry['pairs']);times=Time(geometry['times_mjd'],format='mjd',scale='utc')
    if pairs.shape!=(nb,2) or times.shape!=(ntime,) or np.any(pairs[:,0]>=pairs[:,1]):
        raise ValueError('invalid baseline/time dimensions')
    obs=config['observation'];fc=obs['frequency_hz'];bw=obs['bandwidth_hz']
    rdate=Time(obs['start_utc']).isot[:10]
    def table(columns,name,revision=1):
        hdu=fits.BinTableHDU.from_columns(columns,name=name)
        hdu.header.update({'EXTVER':1,'TABREV':revision,'OBSCODE':'VSORA','NO_STKD':1,
                           'STK_1':-5,'NO_BAND':1,'NO_CHAN':1,'REF_FREQ':fc,
                           'CHAN_BW':bw,'REF_PIXL':1.,'RDATE':rdate})
        return hdu
    primary=fits.PrimaryHDU()
    primary.header.update({'OBJECT':'BINARYTB','TELESCOP':'VSORA','ORIGIN':'V-SoRA',
                           'CORRELAT':'VSORA','FXCORVER':'0.1','DATE-OBS':obs['start_utc'].replace('Z','')})
    primary.header.add_history('Generated from V-SoRA simulation; single-channel CASA-tested profile v2.')
    xyz=np.asarray(geometry['station_ecef_m']);origin=xyz[0]
    names=[s['id'] for s in config['stations']];numbers=np.arange(1,nst+1)
    ag=table([_column('ANNAME','8A',names),_column('STABXYZ','3D',xyz-origin,'METERS'),
              _column('DERXYZ','3E',np.zeros((nst,3)),'M/SEC'),_column('NOSTA','1J',numbers),
              _column('MNTSTA','1J',np.zeros(nst,int)),_column('STAXOF','3E',np.zeros((nst,3)),'METERS'),
              _column('DIAMETER','1E',[s.get('diameter_m',0.) for s in config['stations']],'METERS')],
             'ARRAY_GEOMETRY')
    ag.header.update({'ARRAYX':origin[0],'ARRAYY':origin[1],'ARRAYZ':origin[2],'ARRNAM':'VSORA',
                      'FRAME':'GEOCENTRIC','NUMORB':0,'FREQ':fc,'TIMSYS':'UTC'})
    with iers.conf.set_temp('auto_download',False),iers.conf.set_temp('auto_max_age',None):
        day=Time(rdate,scale='utc')
        ag.header['GSTIA0']=float(day.sidereal_time('mean','greenwich').deg)
        ag.header['DEGPDY']=360.9856449733
        ag.header['UT1UTC']=float(day.delta_ut1_utc)
        ag.header['IATUTC']=int(round((day.tai.jd-day.utc.jd)*86400))
        xp,yp=iers.IERS_Auto.open().pm_xy(day)
        ag.header['POLARX']=float(xp.to_value(u.arcsec));ag.header['POLARY']=float(yp.to_value(u.arcsec))
    frequency=table([_column('FREQID','1J',[1]),_column('BANDFREQ','1D',[0.],'HZ'),
                     _column('CH_WIDTH','1E',[bw],'HZ'),_column('TOTAL_BANDWIDTH','1E',[bw],'HZ'),
                     _column('SIDEBAND','1J',[1])],'FREQUENCY')
    antenna=table([_column('TIME','1D',np.zeros(nst),'DAYS'),
                   _column('TIME_INTERVAL','1E',np.full(nst,obs['duration_s']/86400),'DAYS'),
                   _column('ANNAME','8A',names),_column('ANTENNA_NO','1J',numbers),
                   _column('ARRAY','1J',np.ones(nst,int)),_column('FREQID','1J',np.ones(nst,int)),
                   _column('NO_LEVELS','1J',np.full(nst,256)),_column('POLTYA','1A',['X']*nst),
                   _column('POLAA','1E',np.zeros(nst),'DEGREES'),_column('POLCALA','2E',np.zeros((nst,2))),
                   _column('POLTYB','1A',['Y']*nst),_column('POLAB','1E',np.full(nst,90),'DEGREES'),
                   _column('POLCALB','2E',np.zeros((nst,2)))],'ANTENNA')
    antenna.header.update({'NOPCAL':2,'POLTYPE':'X-Y LIN'})
    target=SkyCoord(config['source']['ra_deg']*u.deg,config['source']['dec_deg']*u.deg,frame='icrs')
    equ=target.transform_to(FK5(equinox=Time('J2000')))
    apparent=target.transform_to(GCRS(obstime=times[0]))
    cols=[_column('SOURCE_ID','1J',[1]),_column('SOURCE','16A',['CASA_MODEL']),
          _column('QUAL','1J',[0]),_column('CALCODE','4A',['']),_column('FREQID','1J',[1])]
    for k in ['IFLUX','QFLUX','UFLUX','VFLUX','ALPHA']:
        cols.append(_column(k,'1E',[0.]))
    cols.extend([_column('FREQOFF','1D',[0.],'HZ'),_column('RAEPO','1D',[equ.ra.deg],'DEGREES'),
                 _column('DECEPO','1D',[equ.dec.deg],'DEGREES'),_column('EQUINOX','8A',['J2000']),
                 _column('RAAPP','1D',[apparent.ra.deg],'DEGREES'),_column('DECAPP','1D',[apparent.dec.deg],'DEGREES'),
                 _column('SYSVEL','1D',[0.],'M/SEC'),_column('VELTYP','8A',['GEOCENTR']),
                 _column('VELDEF','8A',['OPTICAL']),_column('RESTFREQ','1D',[0.],'HZ'),
                 _column('PMRA','1D',[0.],'DEG/DAY'),_column('PMDEC','1D',[0.],'DEG/DAY'),
                 _column('PARALLAX','1E',[0.],'ARCSEC')])
    source=table(cols,'SOURCE')
    # Preserve Time's two-part Julian date; subtracting two large .jd doubles
    # loses tens of microseconds even though DATE/TIME can preserve the split.
    midnight=np.floor(times.mjd)+2400000.5
    fraction=(times.jd1-midnight)+times.jd2
    baseline=np.tile(256*(pairs[:,0]+1)+(pairs[:,1]+1),ntime)
    duration=np.broadcast_to(obs['integration_s'] if integration_s is None else integration_s,v.shape).reshape(-1)
    if np.any(duration<0) or not np.isfinite(duration).all(): raise ValueError('invalid integration time')
    # CASA importfitsidi conjugates stored FLUX. Verify with an off-axis point:
    # the initial unconjugated profile roundtripped locally but mirrored in CASA.
    stored=v.conj()
    flux=np.column_stack([stored.real.ravel(),stored.imag.ravel(),w.ravel()]).astype('float32')
    # Memo 114 baseline = first-second; internal baseline = second-first.
    seconds=-uvw.reshape(rows,3)/fc
    columns=[_column(k,'1D',seconds[:,i],'SECONDS') for i,k in enumerate(['UU','VV','WW'])]
    columns.extend([_column('DATE','1D',np.repeat(midnight,nb),'DAYS'),
                    _column('TIME','1D',np.repeat(fraction,nb),'DAYS'),
                    _column('BASELINE','1J',baseline),_column('ARRAY','1J',np.ones(rows,int)),
                    _column('SOURCE_ID','1J',np.ones(rows,int)),_column('FREQID','1J',np.ones(rows,int)),
                    _column('INTTIM','1E',duration,'SECONDS'),_column('FLUX','3E',flux,'JY')])
    uv=table(columns,'UV_DATA',2)
    uv.header.update({'NMATRIX':1,'MAXIS':6,'WEIGHTYP':'NORMAL','SORT':'TB'})
    axes=[(3,'COMPLEX',1.,1.),(1,'STOKES',-5.,-1.),(1,'FREQ',fc,bw),
          (1,'BAND',1.,1.),(1,'RA',equ.ra.deg,0.),(1,'DEC',equ.dec.deg,0.)]
    for i,(size,ctype,ref,delta) in enumerate(axes,1):
        uv.header.update({f'MAXIS{i}':size,f'CTYPE{i}':ctype,f'CRVAL{i}':ref,f'CDELT{i}':delta,f'CRPIX{i}':1.})
    index=len(columns);uv.header[f'TMATX{index}']=True;uv.header[f'TDIM{index}']='(3,1,1,1,1,1)'
    provenance={'schema_version':2,'config':config,'metadata':metadata or {},
                'baseline_conversion':'IDI uvw is negative of internal uvw; visibility conjugated for CASA profile',
                'visibility_storage':'conjugated_internal',
                'profile':'one XX product, one continuum channel, one band, one source'}
    text=json.dumps(provenance)
    extra=fits.BinTableHDU.from_columns([_column('JSON',f'{len(text)}A',[text])],name='VSORA_META')
    p.parent.mkdir(parents=True,exist_ok=True)
    fits.HDUList([primary,ag,frequency,source,antenna,extra,uv]).writeto(p,checksum=True)


def read_fitsidi(path):
    with fits.open(path,checksum=True) as hdus:
        if 'VSORA_META' not in hdus: raise ValueError('reader only supports V-SoRA single-channel profile')
        meta=json.loads(hdus['VSORA_META'].data['JSON'][0])
        config=meta['config'];tab=hdus['UV_DATA'];d=tab.data
        if tab.header['NO_CHAN']!=1 or tab.header['NO_BAND']!=1 or tab.header['STK_1']!=-5:
            raise ValueError('unsupported IDI spectral/polarization profile')
        nb=len(config['stations'])*(len(config['stations'])-1)//2
        if len(d)%nb: raise ValueError('incomplete time/baseline grid')
        packed=np.asarray(d['BASELINE']);pairs=np.column_stack([packed//256-1,packed%256-1])
        pairs=pairs.reshape(-1,nb,2)
        if not (pairs==pairs[0]).all(): raise ValueError('inconsistent baseline order')
        flux=np.asarray(d['FLUX']).reshape(-1,3)
        mjd=((d['DATE']-2400000.5)+d['TIME']).reshape(-1,nb)
        if not np.allclose(mjd,mjd[:,0,None],rtol=0,atol=1e-12): raise ValueError('baseline times differ')
        uvw=-np.column_stack([d[k] for k in ['UU','VV','WW']])*tab.header['REF_FREQ']
        values=flux[:,0]+1j*flux[:,1]
        if meta.get('visibility_storage')=='conjugated_internal': values=values.conj()
        result={'vis_jy':values.reshape(-1,nb),
                'weights':flux[:,2].reshape(-1,nb),'uvw_lambda':uvw.reshape(-1,nb,3),
                'pairs':pairs[0],'time_mjd':mjd[:,0],
                'metadata':{**meta['metadata'],'config':config},
                'integration_s':np.asarray(d['INTTIM']).reshape(-1,nb)}
    return result
