"""Experimental raw U3 sums sidecar; no implicit IID or noise likelihood."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import zipfile
from datetime import datetime
import numpy as np

ARRAYS={'triangles','times_s','frequencies_hz','common_fft_count','nominal_fft_count',
        'edge_sums','paired_edge_sums','triple_edge_sum','channel_triangle_usable'}
BASE={'station_ids','time_origin_utc','voltage_unit','fft_length','sample_rate_hz','visibility_sha256','processing_notes'}
FIXED={'edge_order':'ij, jk, ki','paired_edge_order':'ab, ac, bc',
       'visibility_convention':'Vij=E[x_i conj(x_j)], i<j',
       'input_sample_independence_verified':False,'input_mask_independence_verified':False,
       'gaussian_bispectrum_likelihood_assumed':False,'closure_phase_unbiased_guarantee':False,
       'production_rml_noise_model_changed':False,'real_hardware_validation_performed':False}
POWER_ARRAYS=ARRAYS|{'common_station_power_sums'}
POWER_FIXED={'common_power_station_order':'i, j, k',
             'common_power_sample_set':'triangle-common valid FFT blocks',
             'observed_power_ratio_unbiased_guarantee':False}
MAX_CELLS=262144
MAX_BYTES=40*1024**2


def arrays_for_version(schema_version):
    if (isinstance(schema_version,(bool,np.bool_)) or not isinstance(schema_version,(int,np.integer))
            or int(schema_version) not in (1,2)):
        raise ValueError('raw bispectrum schema_version must be1 or2')
    return ARRAYS.copy() if int(schema_version)==1 else POWER_ARRAYS.copy()


def _metadata(metadata,schema_version=1):
    arrays_for_version(schema_version)
    optional=set(FIXED)|{'bispectrum_unit'}
    if schema_version==2:optional|=set(POWER_FIXED)|{'common_power_sum_unit'}
    if not isinstance(metadata,dict) or not BASE<=set(metadata) or set(metadata)-BASE-optional:
        raise ValueError('exact raw bispectrum metadata fields required')
    q=dict(metadata);ids=q['station_ids']
    if (not isinstance(ids,list) or not 3<=len(ids)<=8 or not all(isinstance(s,str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,31}',s) for s in ids)
            or len(set(ids))!=len(ids)):
        raise ValueError('3..8 distinct portable station IDs required')
    origin=q['time_origin_utc']
    try:
        stamp=datetime.fromisoformat(origin.replace('Z','+00:00'))
        if stamp.utcoffset() is None or stamp.utcoffset().total_seconds()!=0:raise ValueError
    except (AttributeError,TypeError,ValueError):raise ValueError('UTC time origin required') from None
    if q['voltage_unit'] not in ('ADC','sqrt(Jy)'):raise ValueError('ADC or sqrt(Jy) voltage unit required')
    nf=q['fft_length'];fs=q['sample_rate_hz']
    if (isinstance(nf,bool) or not isinstance(nf,int) or not 2<=nf<=4096 or isinstance(fs,bool)
            or not isinstance(fs,(int,float)) or not np.isfinite(fs) or fs<=0):
        raise ValueError('finite sample rate and integer FFT length2..4096 required')
    if not isinstance(q['visibility_sha256'],str) or not re.fullmatch('[0-9a-f]{64}',q['visibility_sha256']):
        raise ValueError('lowercase visibility SHA256 required')
    notes=q['processing_notes']
    if not isinstance(notes,list) or not notes or not all(isinstance(v,str) and v for v in notes):raise ValueError('processing notes required')
    fixed={**FIXED,'bispectrum_unit':'ADC^6' if q['voltage_unit']=='ADC' else 'Jy^3'}
    if schema_version==2:
        fixed.update(POWER_FIXED,common_power_sum_unit='ADC^2' if q['voltage_unit']=='ADC' else 'Jy')
    for k,v in fixed.items():
        if k in q and (type(q[k]) is not type(v) or q[k]!=v):raise ValueError('unsupported bispectrum unit or verified assumption claim')
    q.update(fixed)
    if len(json.dumps(q,allow_nan=False))>32768:raise ValueError('metadata too large')
    return q


def validate_bispectrum(data,metadata,*,schema_version=1):
    required=arrays_for_version(schema_version)
    q=_metadata(metadata,schema_version)
    if not isinstance(data,dict) or set(data)!=required or any(np.ma.isMaskedArray(v) for v in data.values()):
        raise ValueError('exact unmasked raw bispectrum arrays required')
    d={k:np.asarray(v) for k,v in data.items()};a=d['edge_sums'];h=d['paired_edge_sums'];j=d['triple_edge_sum']
    if a.ndim!=4 or a.shape[-1]!=3 or h.shape!=a.shape or j.shape!=a.shape[:3]:raise ValueError('raw sum shapes [time,channel,triangle,3] required')
    nt,nf,nk=a.shape[:3]
    if not nt or not nf or not nk or nf!=q['fft_length'] or nt*nf*nk>MAX_CELLS:raise ValueError('raw bispectrum dimensions outside supported range')
    if any(not np.iscomplexobj(v) or not np.isfinite(v).all() for v in (a,h,j)):raise ValueError('finite complex raw sums required')
    t,f,tri,m,nominal,usable=(d[k] for k in ('times_s','frequencies_hz','triangles','common_fft_count','nominal_fft_count','channel_triangle_usable'))
    if (t.shape!=(nt,) or f.shape!=(nf,) or not np.issubdtype(t.dtype,np.floating) or not np.issubdtype(f.dtype,np.floating)
            or not np.isfinite(t).all() or not np.isfinite(f).all() or np.any(t<0) or np.any(f<=0)
            or np.any(np.diff(t)<=0) or np.any(np.diff(f)<=0)):
        raise ValueError('finite increasing real time and RF frequency axes required')
    if (tri.shape!=(nk,3) or not np.issubdtype(tri.dtype,np.integer) or np.any(tri<0) or np.any(tri>=len(q['station_ids']))
            or np.any(tri[:,0]>=tri[:,1]) or np.any(tri[:,1]>=tri[:,2]) or len(np.unique(tri,axis=0))!=nk):
        raise ValueError('unique canonical station triangles required')
    if (m.shape!=(nt,nk) or nominal.shape!=(nt,) or not np.issubdtype(m.dtype,np.integer) or not np.issubdtype(nominal.dtype,np.integer)
            or np.any(m<0) or np.any(m>1000000) or np.any(nominal<0) or np.any(nominal>1000000000) or np.any(m>nominal[:,None])):
        raise ValueError('valid common and nominal FFT counts required')
    if usable.dtype!=np.bool_ or usable.shape!=(nt,nf,nk) or np.any(usable&(m[:,None,:]<3)):
        raise ValueError('boolean usability cannot include fewer than3 samples')
    zero=m[:,None,:]==0
    if (np.any(np.where(zero[...,None],a,0)!=0) or np.any(np.where(zero[...,None],h,0)!=0) or np.any(np.where(zero,j,0)!=0)):
        raise ValueError('zero-count raw sums must be zero')
    tolerance=1e-12*np.maximum(abs(j.real),np.finfo(float).tiny)
    if np.any(j.real<0) or np.any(abs(j.imag)>tolerance):raise ValueError('triple edge sum must be nonnegative real within rounding tolerance')
    reconstructed=reconstruct_bispectrum(d)
    if schema_version==2:
        power=d['common_station_power_sums']
        if (power.shape!=a.shape or power.dtype.kind!='f' or power.dtype.itemsize!=8
                or not np.isfinite(power).all() or np.any(power<0)):
            raise ValueError('finite nonnegative float64 common station power sums [time,channel,triangle,3] required')
        if np.any(np.where(zero[...,None],power,0)!=0):
            raise ValueError('zero-count common power sums must be zero')
        with np.errstate(over='ignore',invalid='ignore'):
            ordinary=np.divide(np.prod(a,axis=-1),m[:,None,:].astype(float)**3,
                               out=np.zeros_like(j),where=m[:,None,:]>0)
        if not np.isfinite(ordinary).all():raise ValueError('ordinary raw product outside finite numerical range')
        no_power=np.any(power==0,axis=-1)
        if np.any(no_power&((reconstructed!=0)|(ordinary!=0))):
            raise ValueError('zero empirical common power inconsistent with nonzero raw products')
    return d,q


def reconstruct_bispectrum(data):
    a=np.asarray(data['edge_sums'],complex);h=np.asarray(data['paired_edge_sums'],complex);j=np.asarray(data['triple_edge_sum'],complex)
    m=np.asarray(data['common_fft_count'],float)[:,None,:];eligible=m>=3
    with np.errstate(over='ignore',invalid='ignore'):
        product=np.prod(a,axis=-1)
        numerator=product-h[:,:,:,0]*a[:,:,:,2]-h[:,:,:,1]*a[:,:,:,1]-h[:,:,:,2]*a[:,:,:,0]+2*j
        u=np.divide(numerator,m*(m-1)*(m-2),out=np.zeros_like(product),where=eligible)
    if not np.isfinite(u).all():raise ValueError('reconstructed U3 outside finite numerical range')
    return u


def save_bispectrum(path,data,metadata,*,schema_version=1):
    d,q=validate_bispectrum(data,metadata,schema_version=schema_version);p=Path(path)
    if p.suffix!='.npz':raise ValueError('NPZ suffix required')
    if p.exists():raise FileExistsError(p.name)
    p.parent.mkdir(parents=True,exist_ok=True)
    temp=None
    try:
        with tempfile.NamedTemporaryFile(dir=p.parent,prefix='.bispectrum-',suffix='.partial',delete=False) as stream:
            temp=Path(stream.name)
            np.savez_compressed(stream,schema_version=np.array(int(schema_version)),metadata_json=np.array(json.dumps(q,allow_nan=False)),**d)
            stream.flush();os.fsync(stream.fileno())
        with zipfile.ZipFile(temp) as archive:
            if sum(info.file_size for info in archive.infolist())>MAX_BYTES:
                raise ValueError('raw bispectrum archive exceeds supported decoded size')
        os.link(temp,p)
    finally:
        if temp is not None:temp.unlink(missing_ok=True)


def load_bispectrum(path,source_visibility=None):
    p=Path(path);expected_sets=(ARRAYS|{'schema_version','metadata_json'},POWER_ARRAYS|{'schema_version','metadata_json'})
    with zipfile.ZipFile(p) as archive:
        infos=archive.infolist()
        if (not any(len(infos)==len(expected) and {i.filename for i in infos}=={k+'.npy' for k in expected} for expected in expected_sets)
                or sum(i.file_size for i in infos)>MAX_BYTES):raise ValueError('unsupported or oversized raw bispectrum archive')
        for info in infos:
            with archive.open(info) as stream:
                version=np.lib.format.read_magic(stream)
                if version==(1,0):shape,_,dtype=np.lib.format.read_array_header_1_0(stream)
                elif version==(2,0):shape,_,dtype=np.lib.format.read_array_header_2_0(stream)
                else:raise ValueError('unsupported raw bispectrum array header')
                if dtype.hasobject or any(v<0 for v in shape) or math.prod(shape)*dtype.itemsize>info.file_size:
                    raise ValueError('unsupported raw bispectrum array payload')
    with np.load(p,allow_pickle=False) as file:d={k:file[k] for k in file.files}
    version=d.pop('schema_version');meta=d.pop('metadata_json')
    if version.shape!=() or not np.issubdtype(version.dtype,np.integer) or int(version) not in (1,2):raise ValueError('unsupported raw bispectrum version')
    if meta.shape!=() or meta.dtype.kind!='U':raise ValueError('scalar JSON metadata required')
    d,q=validate_bispectrum(d,json.loads(str(meta)),schema_version=int(version))
    if source_visibility is not None:
        with open(source_visibility,'rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if digest!=q['visibility_sha256']:raise ValueError('source visibility SHA256 differs')
        from .spectral import load_spectral
        original=load_spectral(source_visibility);metadata=original['metadata']
        ids=[v['id'] for v in metadata.get('config',{}).get('stations',[])]
        if (not np.array_equal(d['times_s'],original['times_s']) or not np.array_equal(d['frequencies_hz'],original['frequencies_hz'])
                or ids!=q['station_ids'] or metadata.get('time_origin_utc')!=q['time_origin_utc']
                or metadata.get('fft_length')!=q['fft_length'] or metadata.get('fft_sample_rate_hz')!=q['sample_rate_hz']
                or metadata.get('visibility_unit')!=('ADC^2' if q['voltage_unit']=='ADC' else 'Jy')):
            raise ValueError('source visibility axes, station IDs, epoch, FFT profile or units differ')
        counts=np.asarray(original.get('valid_fft_count'))
        if counts.shape!=(len(d['times_s']),len(original['pairs'])) or not np.issubdtype(counts.dtype,np.integer) or np.any(counts<0):
            raise ValueError('source integer baseline FFT counts required')
        pair_index={tuple(v):n for n,v in enumerate(original['pairs'])}
        for n,(i,k,l) in enumerate(d['triangles']):
            for edge,(a,b) in enumerate(((i,k),(k,l),(l,i))):
                key=(min(a,b),max(a,b))
                if key not in pair_index:raise ValueError('source triangle edge missing')
                index=pair_index[key];m=d['common_fft_count'][:,n]
                if np.any(m>counts[:,index]):raise ValueError('common FFT count exceeds source baseline count')
                if np.any(d['channel_triangle_usable'][:,:,n]&(original['weights'][:,:,index]<=0)):
                    raise ValueError('usable triangle contains an invalid source baseline')
                same=(m==counts[:,index])&(m>0)
                if same.any():
                    mean=d['edge_sums'][same,:,n,edge]/m[same,None]
                    expected=original['visibilities'][same,:,index]
                    if a>b:expected=expected.conj()
                    scale=max(float(np.max(abs(mean))),float(np.max(abs(expected))),np.finfo(float).tiny)
                    if not np.allclose(mean,expected,rtol=1e-11,atol=1e-12*scale):
                        raise ValueError('same-count raw edge sum differs from source visibility')
    return {**d,'schema_version':int(version),'metadata':q,'distinct_sample_bispectrum':reconstruct_bispectrum(d),
            'distinct_sample_available':d['common_fft_count']>=3,'source_visibility_verified':source_visibility is not None}
