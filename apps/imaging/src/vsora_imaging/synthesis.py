"""Preserve short integrations/channel closures while assembling synthesis time."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import numpy as np
from astropy.time import Time
from vsora_formats.spectral import load_spectral,save_spectral


def _recorded_sigmf_identity(meta, config):
    """Validate agreement of recorded claims, without reopening raw inputs."""
    if meta.get('synthesis'):
        raise ValueError('already merged SigMF inputs require a separate provenance contract')
    if meta.get('visibility_unit')!='ADC^2':
        raise ValueError('SigMF synthesis requires ADC^2')
    identity=meta.get('input_identity')
    keys={'input_manifest_sha256','input_clock_sha256','input_observation_sha256','input_sigmf'}
    if not isinstance(identity,dict) or set(identity)!=keys:
        raise ValueError('complete recorded SigMF input_identity required')
    def digest(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None
    if any(not digest(identity[key]) for key in keys-{'input_sigmf'}):
        raise ValueError('recorded SigMF control SHA256 required')
    pairs=identity['input_sigmf'];ids=[s['id'] for s in config['stations']]
    if not isinstance(pairs,list) or len(pairs)!=len(ids):
        raise ValueError('recorded SigMF station pairs required')
    for pair,station in zip(pairs,ids):
        if not isinstance(pair,dict) or set(pair)!={'station_id','metadata','data'} or pair['station_id']!=station:
            raise ValueError('recorded SigMF station order differs')
        for part in ['metadata','data']:
            item=pair[part]
            if (not isinstance(item,dict) or set(item)!={'sha256','bytes'} or not digest(item['sha256'])
                    or type(item['bytes']) is not int or item['bytes']<=0):
                raise ValueError('recorded SigMF pair SHA256 and positive integer bytes required')
    if len({p['data']['sha256'] for p in pairs})!=len(pairs):
        raise ValueError('recorded SigMF station data SHA must be distinct')
    origin=meta.get('time_origin_utc')
    if not isinstance(origin,str) or re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z',origin) is None:
        raise ValueError('SigMF synthesis UTC-Z origin with at most nine fractional digits required')
    epoch=Time(origin)
    if abs((epoch-Time(config['observation']['start_utc'])).sec)>1e-9:
        raise ValueError('SigMF synthesis origin differs from supplied observation epoch')
    epoch.precision=9
    common=('input_clock_sha256','input_observation_sha256','input_sigmf')
    return {key:deepcopy(identity[key]) for key in common},epoch.isot+'Z'


def _source_snapshot(manifest,clock,identity=None):
    from vsora_correlator.input_identity import InputIdentity
    from vsora_correlator.session import load_session
    if identity is not None and not isinstance(identity,InputIdentity):
        raise TypeError('live InputIdentity required for source reuse')
    config=load_session(manifest,allow_sigmf=True)
    if config.get('input_format')!='sigmf_ci16_le':
        raise ValueError('fresh source verification is SigMF-only')
    source=identity if identity is not None else InputIdentity(manifest,clock,expected_config=config)
    if identity is not None:source.assert_current(manifest,clock,config)
    return source,config


def merge_spectral(paths,output,*,source_manifest=None,clock_model=None,input_manifests=None,_source_identity=None):
    if not 2<=len(paths)<=64:raise ValueError('synthesis requires 2..64 spectral inputs')
    out=Path(output)
    if out.suffix!='.npz':raise ValueError('synthesis output must be .npz')
    if out.exists():raise FileExistsError('synthesis output already exists')
    supplied=[v is not None for v in (source_manifest,clock_model,input_manifests)]
    if any(supplied) and not all(supplied):
        raise ValueError('source_manifest, clock_model and input_manifests must be supplied together')
    if _source_identity is not None and not all(supplied):
        raise ValueError('live source reuse requires all explicit source paths')
    source=None;views=[];child_configs=[]
    if all(supplied):
        if not isinstance(input_manifests,(list,tuple)) or len(input_manifests)!=len(paths):
            raise ValueError('one input manifest per spectral input required')
        from vsora_correlator.session import load_session
        source,source_config=_source_snapshot(source_manifest,clock_model,_source_identity)
        for manifest in input_manifests:
            config=load_session(manifest,allow_sigmf=True)
            views.append(source.bind_sigmf_session(manifest,clock_model,config));child_configs.append(config)
    def unchanged():
        if source is not None:
            source.assert_current(source_manifest,clock_model,source_config)
            for manifest,view,config in zip(input_manifests,views,child_configs):
                view.assert_current(manifest,clock_model,config)
    inputs=[];provenance=[];reference=None;sigmf_mode=None
    for index,path in enumerate(paths):
        unchanged()
        data=load_spectral(path);meta=data['metadata'];config=meta['config']
        unchanged()
        sigmf=meta.get('input_format')=='sigmf_ci16_le'
        if source is not None:
            if not sigmf or meta.get('input_identity')!=views[index].public_identity:
                raise ValueError('fresh source/derived identity differs from recorded spectral identity')
            child=child_configs[index]
            canonical=lambda value:json.dumps(value,sort_keys=True,allow_nan=False)
            if (canonical(config)!=canonical(child['_config'])
                    or canonical(meta.get('fft_length'))!=canonical(child['fft_length'])
                    or canonical(meta.get('fft_sample_rate_hz'))!=canonical(child['sample_rate_hz'])
                    or not np.isfinite(meta.get('nominal_integration_s',np.nan))
                    or abs(meta['nominal_integration_s']-child['blocks_per_integration']*child['fft_length']/child['sample_rate_hz'])>1e-12):
                raise ValueError('spectral configuration differs from fresh derived session')
            from itertools import combinations
            pairs=np.array(list(combinations(range(len(child['stations'])),2)),dtype=int)
            frequencies=np.sort(child['_config']['observation']['frequency_hz']+np.fft.fftfreq(child['fft_length'],1/child['sample_rate_hz']))
            if not np.array_equal(data['pairs'],pairs) or not np.array_equal(data['frequencies_hz'],frequencies):
                raise ValueError('spectral axes differ from fresh derived session')
        if not sigmf and isinstance(meta.get('input_identity'),dict) and 'input_sigmf' in meta['input_identity']:
            raise ValueError('recorded SigMF identity requires explicit input_format')
        if sigmf_mode is None:sigmf_mode=sigmf
        elif sigmf_mode!=sigmf:raise ValueError('mixed SigMF and legacy synthesis inputs are unsupported')
        if meta.get('clock_mapping_applied') is not True or meta.get('phase_center_corrected') is not True:
            raise ValueError('synthesis production inputs require sample/phase-center alignment')
        signature={'station_ids':[s['id'] for s in config['stations']],
            'positions':[s['enu_m'] for s in config['stations']],'site':{k:config['site'][k] for k in ('latitude_deg','longitude_deg','height_m')},
            'source':{k:config['source'][k] for k in ('frame','ra_deg','dec_deg')},
            'unit':meta['visibility_unit'],'pixel_arcsec':config['image']['pixel_arcsec']}
        if sigmf:
            common,epoch=_recorded_sigmf_identity(meta,config)
            signature.update(sigmf_original_identity=common,sigmf_time_origin_utc=epoch)
            counts=data.get('valid_fft_count')
            if (not isinstance(counts,np.ndarray) or counts.shape!=(len(data['times_s']),len(data['pairs']))
                    or not np.issubdtype(counts.dtype,np.integer) or np.any(counts<0)):
                raise ValueError('SigMF synthesis requires nonnegative integer valid_fft_count per time/baseline')
            known={'metadata','visibilities','weights','uvw_lambda','integration_s','valid_fft_count','times_s','pairs','frequencies_hz'}
            if any(k not in known and not k.startswith('diagnostic_') for k in data):
                raise ValueError('unrecognized SigMF spectral field cannot be silently discarded')
        if reference is None:reference=(signature,data)
        elif signature!=reference[0] or not np.array_equal(data['pairs'],reference[1]['pairs']) or not np.array_equal(data['frequencies_hz'],reference[1]['frequencies_hz']):
            raise ValueError('synthesis station/geometry/source/unit/frequency axes differ')
        if 'integration_s' not in data or data['integration_s'].shape!=(len(data['times_s']),len(data['pairs'])):
            raise ValueError('synthesis needs per-time/baseline exposure values')
        if not np.isfinite(data['integration_s']).all() or np.any(data['integration_s']<0):raise ValueError('invalid exposure')
        if not meta.get('time_origin_utc'):raise ValueError('synthesis UTC origin required')
        with open(path,'rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
        unchanged()
        inputs.append(data)
        provenance.append({'input_sha256':sha,'time_origin_utc':meta['time_origin_utc'],
            'time_cells':len(data['times_s']),'rate_applied_hz':meta.get('rate_applied_hz'),
            'rate_reference_s':meta.get('rate_applied_reference_s'),'eop_status':meta.get('eop_status'),
            'rate_profile_sha256':meta.get('rate_only_profile_sha256'),
            'nominal_integration_s':meta.get('nominal_integration_s'),
            'exposure_per_baseline_s':data['integration_s'].sum(axis=0).tolist()})
        if sigmf:
            provenance[-1].update(input_format='sigmf_ci16_le',input_identity=deepcopy(meta['input_identity']))
    if sum(d['visibilities'].size for d in inputs)>1000000:raise ValueError('reference synthesis limited to one million baseline cells')
    origin=min(Time(d['metadata']['time_origin_utc']) for d in inputs)
    if sigmf_mode:origin.precision=9
    origin_text=origin.isot+'Z'
    times=np.concatenate([d['times_s']+(Time(d['metadata']['time_origin_utc'])-origin).sec for d in inputs])
    order=np.argsort(times);sorted_times=times[order]
    if np.any(np.diff(sorted_times)<=1e-9):raise ValueError('duplicate synthesis times')
    diagnostics=set(k for k in inputs[0] if k.startswith('diagnostic_'))
    if any(set(k for k in d if k.startswith('diagnostic_'))!=diagnostics for d in inputs):
        raise ValueError('synthesis diagnostic fields differ; use a consistent correlation profile')
    keys=['visibilities','weights','uvw_lambda','integration_s',*sorted(diagnostics)]
    if sigmf_mode:keys.append('valid_fft_count')
    cube={k:np.concatenate([d[k] for d in inputs],axis=0)[order] for k in keys}
    cube.update(times_s=sorted_times,pairs=inputs[0]['pairs'],frequencies_hz=inputs[0]['frequencies_hz'])
    spans=np.concatenate([np.full(len(d['times_s']),d['metadata']['nominal_integration_s'])
              if 'nominal_integration_s' in d['metadata'] else d['integration_s'].max(axis=1) for d in inputs])[order]
    if not np.isfinite(spans).all() or np.any(spans<=0):raise ValueError('invalid nominal integration spans')
    if np.any(sorted_times[1:]-spans[1:]/2 < sorted_times[:-1]+spans[:-1]/2-1e-8):
        raise ValueError('overlapping synthesis integrations would duplicate information')
    config=deepcopy(inputs[0]['metadata']['config'])
    config['observation']['start_utc']=origin_text
    cadence=float(spans.min());duration=float(np.ceil((sorted_times[-1]+spans[-1]/2)/cadence)*cadence)
    config['observation'].update(duration_s=duration,integration_s=cadence)
    meta={'config':config,'visibility_unit':reference[0]['unit'],'time_origin_utc':origin_text,
        'clock_mapping_applied':True,'phase_center_corrected':True,'synthesis':True,'source_inputs':provenance,
        'recorded_exposure_per_baseline_s':cube['integration_s'].sum(axis=0).tolist(),
        'noise_assumption':'Independent short exposures/channels; full within-cell closure covariance only',
        'overlap_check':'Nominal spans when supplied; effective maximum baseline exposure for older profiles',
        'limitations':'No complex averaging or station gain matching; time/channel values remain distinct; filtered noise correlations approximate'}
    if sigmf_mode:
        meta.update(input_format='sigmf_ci16_le',time_origin_precision_digits=9,
            sigmf_original_identity=deepcopy(reference[0]['sigmf_original_identity']),
            sigmf_identity_scope='Recorded agreement only; raw inputs and producer checksums are not reauthenticated',
            original_files_rehashed=False)
        if source is not None:
            unchanged()
            meta.update(original_files_rehashed=True,
                sigmf_identity_scope='Fresh original/derived file identities match recorded claims; no computation proof, producer authentication or file lock',
                input_identity_verification={'source_identity':source.public_identity,'source_diagnostics':source.diagnostics,
                    'derived_diagnostics':[view.diagnostics for view in views],
                    'scope':'Original/control guards before/after spectral reads and hashes, and immediately before output; changes after the last check or preserving all raw stat fields remain outside this snapshot'})
            if _source_identity is not None:
                meta['input_identity_verification']['source_reuse_mode']='live_same_run_source; root hash counters are cumulative and must not be added twice'
    save_spectral(out,cube,meta)
    result={'input_count':len(inputs),'time_cells':len(sorted_times),'channels':len(cube['frequencies_hz']),
        'baseline_count':len(cube['pairs']),'observation_span_s':float(sorted_times[-1]-sorted_times[0]),
        'exposure_per_baseline_s':meta['recorded_exposure_per_baseline_s'],'source_inputs':provenance,
        'visibility_unit':reference[0]['unit']}
    if sigmf_mode:
        result.update(input_format='sigmf_ci16_le',time_origin_utc=origin_text,
            sigmf_original_identity=deepcopy(meta['sigmf_original_identity']),original_files_rehashed=meta['original_files_rehashed'],
            sigmf_identity_scope=meta['sigmf_identity_scope'])
        if source is not None:result['input_identity_verification']=deepcopy(meta['input_identity_verification'])
    return result


def image_synthesis(paths,output,*,sigmf_reference_image=False,source_manifest=None,clock_model=None,
                    input_manifests=None,_source_identity=None,**settings):
    if not isinstance(sigmf_reference_image,bool):raise ValueError('sigmf_reference_image bool required')
    supplied=[v is not None for v in (source_manifest,clock_model,input_manifests)]
    if sigmf_reference_image and not all(supplied):
        raise ValueError('SigMF reference image requires all explicit source paths')
    if not sigmf_reference_image and (any(supplied) or _source_identity is not None):
        raise ValueError('explicit source image verification requires sigmf_reference_image=True')
    from .closure import extract_closures
    from .rml import image_closure
    out=Path(output);partial=out.with_name(out.name+'.partial')
    if out.exists() or partial.exists():raise FileExistsError('choose new synthesis directory')
    source=source_config=None;verification={};image_views=[]
    if sigmf_reference_image:
        source,source_config=_source_snapshot(source_manifest,clock_model,_source_identity)
        if not isinstance(input_manifests,(list,tuple)) or len(input_manifests)!=len(paths):
            raise ValueError('one input manifest per spectral input required')
        from vsora_correlator.session import load_session
        for manifest in input_manifests:
            config=load_session(manifest,allow_sigmf=True)
            image_views.append((manifest,config,source.bind_sigmf_session(manifest,clock_model,config)))
        verification=dict(source_manifest=source_manifest,clock_model=clock_model,input_manifests=input_manifests,_source_identity=source)
    def unchanged():
        if source is not None:source.assert_current(source_manifest,clock_model,source_config)
        for manifest,config,view in image_views:view.assert_current(manifest,clock_model,config)
    partial.mkdir(parents=True)
    try:
        unchanged()
        merged=merge_spectral(paths,partial/'visibility.npz',**verification)
        unchanged()
        if merged.get('input_format')=='sigmf_ci16_le' and not sigmf_reference_image:
            raise ValueError('SigMF images require explicit sigmf_reference_image=True and source verification')
        closure=extract_closures(partial/'visibility.npz',partial/'closures.npz',min_snr=settings.get('min_snr',10.))
        unchanged()
        rml=image_closure(partial/'visibility.npz',partial/'rml',**settings)
        unchanged()
        result={'state':'complete','type':'closure_synthesis','synthesis':merged,'closures':closure,'rml':rml,
                'absolute_flux_measured':False,'absolute_position_measured':False}
        if sigmf_reference_image:
            result.update(sigmf_reference_image=True,
                imaging_validation_scope='Existing fixed observed high-SNR independent-baseline closure covariance only; no calibrated real-data or low-SNR image likelihood')
        (partial/'summary.json').write_text(json.dumps(result,indent=2)+'\n');partial.rename(out);return result
    except Exception as exc:
        (partial/'failure.json').write_text(json.dumps({'state':'incomplete','error_type':type(exc).__name__})+'\n');raise


def main():
    import argparse
    p=argparse.ArgumentParser(description='Closure RML synthesis from distinct aligned short exposures')
    p.add_argument('--inputs',nargs='+',required=True);p.add_argument('--output',required=True)
    p.add_argument('--merge-only',action='store_true',help='Save aligned spectral windows to .npz without closure extraction or image fitting')
    p.add_argument('--sigmf-reference-image',action='store_true',help='Explicit existing high-SNR reference image with original-source verification; no new noise model')
    p.add_argument('--source-manifest');p.add_argument('--clock-model');p.add_argument('--input-manifests',nargs='+')
    p.add_argument('--starts',type=int,default=3);p.add_argument('--max-iterations',type=int,default=800)
    p.add_argument('--prior-fwhm-arcsec',type=float,default=240.);p.add_argument('--min-snr',type=float,default=10.)
    p.add_argument('--entropy',type=float,default=.01);p.add_argument('--tsv',type=float,default=.0001)
    args=vars(p.parse_args());paths=args.pop('inputs');out=args.pop('output');merge_only=args.pop('merge_only')
    verification={k:args.pop(k) for k in ('source_manifest','clock_model','input_manifests')};reference_image=args.pop('sigmf_reference_image')
    if merge_only and reference_image:p.error('--merge-only and --sigmf-reference-image are mutually exclusive')
    if not merge_only and not reference_image and any(v is not None for v in verification.values()):
        p.error('fresh source verification currently requires --merge-only')
    print(json.dumps(merge_spectral(paths,out,**verification) if merge_only else image_synthesis(paths,out,
        sigmf_reference_image=reference_image,**verification,**args),indent=2))


if __name__=='__main__':main()
