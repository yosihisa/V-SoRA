"""Atomic short VDIF -> aligned pilot/rate -> ADC closures -> relative RML."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import numpy as np
from .session import load_session
from .aligned import correlate_aligned,validate_aligned_dimensions,MAX_ALIGNED_INTEGRATIONS
from .rate import estimate_rate_shard


def process_closure_session(manifest,clock_model,output,*,pilot_integrations=256,pilot_integration_s=None,start_offset_s=.002,
                            integration_s=.3,max_rate_hz=100.,starts=3,max_iterations=800,
                            prior_fwhm_arcsec=240.,entropy=.01,tsv=.0001,progress=None):
    c=load_session(manifest);fs=c['sample_rate_hz'];nf=c['fft_length']
    if not np.isfinite(integration_s) or not .1<=integration_s<=3:
        raise ValueError('short aligned pipeline integration must be 0.1..3 seconds')
    blocks=round(integration_s*fs/nf)
    if abs(blocks*nf/fs-integration_s)>1e-9 or (blocks*nf)%4096:
        raise ValueError('final integration must contain whole VDIF frames and FFT blocks')
    if isinstance(pilot_integrations,bool) or not isinstance(pilot_integrations,int) or not 8<=pilot_integrations<=MAX_ALIGNED_INTEGRATIONS:
        raise ValueError('rate pilot requires 8..16384 short integrations')
    pilot_blocks=c['blocks_per_integration']
    if pilot_integration_s is not None:
        if not np.isfinite(pilot_integration_s) or pilot_integration_s<=0:
            raise ValueError('positive finite pilot integration required')
        pilot_blocks=round(pilot_integration_s*fs/nf)
        samples=pilot_blocks*nf
        if pilot_blocks<1 or abs(samples/fs-pilot_integration_s)>1e-10 or (samples%4096 and 4096%samples):
            raise ValueError('pilot integration must contain whole FFT blocks and whole frames or divide a VDIF frame')
    pilot_config={**c,'blocks_per_integration':pilot_blocks}
    _,pilot_span,_=validate_aligned_dimensions(pilot_config,pilot_integrations)
    validate_aligned_dimensions({**c,'blocks_per_integration':blocks},1)
    cadence=pilot_blocks*nf/fs
    if not np.isfinite(max_rate_hz) or not 0<max_rate_hz<.5/cadence:
        raise ValueError('rate search must be below the temporal Nyquist limit')
    acquisition={'pilot_integration_s':cadence,'pilot_integrations':pilot_integrations,'pilot_span_s':pilot_span,
        'temporal_nyquist_hz':.5/cadence,'max_baseline_rate_hz':max_rate_hz,
        'coherence_at_search_bound':float(abs(np.sinc(max_rate_hz*cadence))),
        'initial_baseline_rate_bound_externally_required':True,
        'sk_eligible_fraction':None,
        'limits':'Rates outside temporal Nyquist may alias undetectably; search range is not a measured initial LO bound. Short-cell SK may be ineligible. Noise search false-positive probability is not calibrated.'}
    out=Path(output);partial=out.with_name(out.name+'.partial')
    if out.exists() or partial.exists():raise FileExistsError('choose a new pipeline output directory')
    partial.mkdir(parents=True)
    state={'schema_version':1,'state':'running','completed_steps':[]}
    def record(step):
        state['completed_steps'].append(step)
        (partial/'pipeline.json').write_text(json.dumps(state,indent=2)+'\n')
        if progress:progress(step,len(state['completed_steps']))
    def clone(name,block_count):
        copied={k:deepcopy(v) for k,v in c.items() if not k.startswith('_')}
        copied['observation_config']='observation.json';copied['blocks_per_integration']=block_count
        for station in copied['stations']:station['vdif']=str((c['_root']/station['vdif']).resolve())
        path=partial/name;path.write_text(json.dumps(copied,indent=2)+'\n');return path
    try:
        (partial/'observation.json').write_text(json.dumps(c['_config'],indent=2)+'\n')
        (partial/'clock.json').write_text(Path(clock_model).read_text())
        source=[]
        for station in c['stations']:
            path=c['_root']/station['vdif']
            with path.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
            source.append({'station_id':station['id'],'sha256':sha,'bytes':path.stat().st_size})
        with open(manifest,'rb') as stream:manifest_sha=hashlib.file_digest(stream,'sha256').hexdigest()
        with open(clock_model,'rb') as stream:clock_sha=hashlib.file_digest(stream,'sha256').hexdigest()
        with open(c['_root']/c['observation_config'],'rb') as stream:observation_sha=hashlib.file_digest(stream,'sha256').hexdigest()
        pilot_manifest=clone('pilot-manifest.json',pilot_blocks)
        pilot=correlate_aligned(pilot_manifest,clock_model,partial/'pilot',pilot_integrations,start_offset_s)
        from vsora_formats.spectral import load_spectral
        diagnostic=load_spectral(partial/'pilot/shard-00000.npz')
        eligible=diagnostic.get('diagnostic_station_sk_eligible')
        if eligible is not None:acquisition['sk_eligible_fraction']=float(np.mean(eligible))
        del diagnostic
        record('aligned_pilot')
        estimate=estimate_rate_shard(partial/'pilot/shard-00000.npz',max_rate_hz=max_rate_hz)
        profile=partial/'rate-only.json';profile.write_text(json.dumps(estimate,indent=2)+'\n')
        record('model_free_rate')
        final_manifest=clone('final-manifest.json',blocks)
        final=correlate_aligned(final_manifest,clock_model,partial/'correlation',1,start_offset_s,profile)
        record('rate_corrected_short_correlation')
        from vsora_imaging.closure import extract_closures
        from vsora_imaging.rml import image_closure
        visibility=partial/'correlation/shard-00000.npz'
        closure=extract_closures(visibility,partial/'closures.npz',min_snr=10.)
        record('closure_extraction')
        image=image_closure(visibility,partial/'rml',pixels=32,pixel_arcsec=c['_config']['image']['pixel_arcsec'],
                    starts=starts,max_iterations=max_iterations,prior_fwhm_arcsec=prior_fwhm_arcsec,entropy=entropy,tsv=tsv)
        record('relative_rml')
        result={**state,'state':'complete','input_manifest_sha256':manifest_sha,'input_clock_sha256':clock_sha,
                'input_observation_sha256':observation_sha,'input_vdif':source,
                'pilot':pilot,'rate_acquisition':acquisition,'rate_estimate':estimate,'correlation':final,'closures':closure,'rml':image,
                'coherent_integration_s':integration_s,'absolute_flux_measured':False,'absolute_position_measured':False,
                'limits':'Supplied linear sample clocks; <=3s and 600m, <=1s geometry segments; stable pilot sky/gain; high SNR Gaussian closures; CPU small reference'}
        (partial/'pipeline.json').write_text(json.dumps(result,indent=2)+'\n')
        (partial/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
        partial.rename(out);return result
    except Exception as exc:
        state.update(state='incomplete',error_type=type(exc).__name__)
        (partial/'pipeline.json').write_text(json.dumps(state,indent=2)+'\n')
        (partial/'failure.json').write_text(json.dumps(state,indent=2)+'\n')
        raise


def main():
    import argparse
    p=argparse.ArgumentParser(description='VDIF short pilot -> unknown rates -> closure-only relative RML')
    p.add_argument('--manifest',required=True);p.add_argument('--clock-model',required=True);p.add_argument('--output',required=True)
    p.add_argument('--pilot-integrations',type=int,default=256);p.add_argument('--pilot-integration-s',type=float); p.add_argument('--integration-s',type=float,default=.3)
    p.add_argument('--start-offset-s',type=float,default=.002);p.add_argument('--max-rate-hz',type=float,default=100.)
    p.add_argument('--starts',type=int,default=3);p.add_argument('--max-iterations',type=int,default=800)
    p.add_argument('--prior-fwhm-arcsec',type=float,default=240.);p.add_argument('--entropy',type=float,default=.01);p.add_argument('--tsv',type=float,default=.0001)
    args=vars(p.parse_args());manifest=args.pop('manifest');clock=args.pop('clock_model');out=args.pop('output')
    print(json.dumps(process_closure_session(manifest,clock,out,**args),indent=2))


if __name__=='__main__':main()
