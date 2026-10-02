"""Preserve short integrations/channel closures while assembling synthesis time."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import numpy as np
from astropy.time import Time
from vsora_formats.spectral import load_spectral,save_spectral


def merge_spectral(paths,output):
    if not 2<=len(paths)<=64:raise ValueError('synthesis requires 2..64 spectral inputs')
    out=Path(output)
    if out.suffix!='.npz':raise ValueError('synthesis output must be .npz')
    if out.exists():raise FileExistsError('synthesis output already exists')
    inputs=[];provenance=[];reference=None
    for path in paths:
        data=load_spectral(path);meta=data['metadata'];config=meta['config']
        if meta.get('clock_mapping_applied') is not True or meta.get('phase_center_corrected') is not True:
            raise ValueError('synthesis production inputs require sample/phase-center alignment')
        signature={'station_ids':[s['id'] for s in config['stations']],
            'positions':[s['enu_m'] for s in config['stations']],'site':{k:config['site'][k] for k in ('latitude_deg','longitude_deg','height_m')},
            'source':{k:config['source'][k] for k in ('frame','ra_deg','dec_deg')},
            'unit':meta['visibility_unit'],'pixel_arcsec':config['image']['pixel_arcsec']}
        if reference is None:reference=(signature,data)
        elif signature!=reference[0] or not np.array_equal(data['pairs'],reference[1]['pairs']) or not np.array_equal(data['frequencies_hz'],reference[1]['frequencies_hz']):
            raise ValueError('synthesis station/geometry/source/unit/frequency axes differ')
        if 'integration_s' not in data or data['integration_s'].shape!=(len(data['times_s']),len(data['pairs'])):
            raise ValueError('synthesis needs per-time/baseline exposure values')
        if not np.isfinite(data['integration_s']).all() or np.any(data['integration_s']<0):raise ValueError('invalid exposure')
        if not meta.get('time_origin_utc'):raise ValueError('synthesis UTC origin required')
        with open(path,'rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
        inputs.append(data)
        provenance.append({'input_sha256':sha,'time_origin_utc':meta['time_origin_utc'],
            'time_cells':len(data['times_s']),'rate_applied_hz':meta.get('rate_applied_hz'),
            'rate_reference_s':meta.get('rate_applied_reference_s'),'eop_status':meta.get('eop_status'),
            'rate_profile_sha256':meta.get('rate_only_profile_sha256'),
            'nominal_integration_s':meta.get('nominal_integration_s'),
            'exposure_per_baseline_s':data['integration_s'].sum(axis=0).tolist()})
    if sum(d['visibilities'].size for d in inputs)>1000000:raise ValueError('reference synthesis limited to one million baseline cells')
    origin=min(Time(d['metadata']['time_origin_utc']) for d in inputs)
    origin_text=origin.isot+'Z'
    times=np.concatenate([d['times_s']+(Time(d['metadata']['time_origin_utc'])-origin).sec for d in inputs])
    order=np.argsort(times);sorted_times=times[order]
    if np.any(np.diff(sorted_times)<=1e-9):raise ValueError('duplicate synthesis times')
    diagnostics=set(k for k in inputs[0] if k.startswith('diagnostic_'))
    if any(set(k for k in d if k.startswith('diagnostic_'))!=diagnostics for d in inputs):
        raise ValueError('synthesis diagnostic fields differ; use a consistent correlation profile')
    keys=['visibilities','weights','uvw_lambda','integration_s',*sorted(diagnostics)]
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
    save_spectral(out,cube,meta)
    return {'input_count':len(inputs),'time_cells':len(sorted_times),'channels':len(cube['frequencies_hz']),
        'baseline_count':len(cube['pairs']),'observation_span_s':float(sorted_times[-1]-sorted_times[0]),
        'exposure_per_baseline_s':meta['recorded_exposure_per_baseline_s'],'source_inputs':provenance,
        'visibility_unit':reference[0]['unit']}


def image_synthesis(paths,output,**settings):
    from .closure import extract_closures
    from .rml import image_closure
    out=Path(output);partial=out.with_name(out.name+'.partial')
    if out.exists() or partial.exists():raise FileExistsError('choose new synthesis directory')
    partial.mkdir(parents=True)
    try:
        merged=merge_spectral(paths,partial/'visibility.npz')
        closure=extract_closures(partial/'visibility.npz',partial/'closures.npz',min_snr=settings.get('min_snr',10.))
        rml=image_closure(partial/'visibility.npz',partial/'rml',**settings)
        result={'state':'complete','type':'closure_synthesis','synthesis':merged,'closures':closure,'rml':rml,
                'absolute_flux_measured':False,'absolute_position_measured':False}
        (partial/'summary.json').write_text(json.dumps(result,indent=2)+'\n');partial.rename(out);return result
    except Exception as exc:
        (partial/'failure.json').write_text(json.dumps({'state':'incomplete','error_type':type(exc).__name__})+'\n');raise


def main():
    import argparse
    p=argparse.ArgumentParser(description='Closure RML synthesis from distinct aligned short exposures')
    p.add_argument('--inputs',nargs='+',required=True);p.add_argument('--output',required=True)
    p.add_argument('--starts',type=int,default=3);p.add_argument('--max-iterations',type=int,default=800)
    p.add_argument('--prior-fwhm-arcsec',type=float,default=240.);p.add_argument('--min-snr',type=float,default=10.)
    p.add_argument('--entropy',type=float,default=.01);p.add_argument('--tsv',type=float,default=.0001)
    args=vars(p.parse_args());paths=args.pop('inputs');out=args.pop('output')
    print(json.dumps(image_synthesis(paths,out,**args),indent=2))


if __name__=='__main__':main()
