"""Bounded nonoverlapping short windows with independent rate profiles."""
import json
from pathlib import Path
import numpy as np
from .session import load_session
from .aligned import validate_aligned_dimensions,MAX_SPECTRAL_CELLS
from .closure_pipeline import process_closure_session
from .input_identity import InputIdentity


def plan_windows(config,window_count,step_s,start_offset_s,pilot_integrations,pilot_integration_s,integration_s):
    if isinstance(window_count,bool) or not isinstance(window_count,int) or not 2<=window_count<=64:
        raise ValueError('sequence requires 2..64 windows')
    if not np.isfinite(start_offset_s) or start_offset_s<0 or (step_s is not None and (not np.isfinite(step_s) or step_s<=0)):
        raise ValueError('positive window step and nonnegative start required')
    if pilot_integration_s is not None and (not np.isfinite(pilot_integration_s) or pilot_integration_s<=0):
        raise ValueError('positive finite pilot integration required')
    fs=config['sample_rate_hz'];nf=config['fft_length']
    blocks=config['blocks_per_integration'] if pilot_integration_s is None else round(pilot_integration_s*fs/nf)
    ns=blocks*nf
    if (blocks<1 or (pilot_integration_s is not None and abs(ns/fs-pilot_integration_s)>1e-10)
            or (ns%4096 and 4096%ns)):
        raise ValueError('pilot integration must match FFT and VDIF frame grid')
    if isinstance(pilot_integrations,bool) or not isinstance(pilot_integrations,int) or pilot_integrations<8:
        raise ValueError('pilot requires at least eight short integrations')
    _,span,_=validate_aligned_dimensions({**config,'blocks_per_integration':blocks},pilot_integrations)
    if not np.isfinite(integration_s) or not .1<=integration_s<=3:
        raise ValueError('image integration must be 0.1..3 seconds')
    image_blocks=round(integration_s*fs/nf)
    if abs(image_blocks*nf/fs-integration_s)>1e-9 or (image_blocks*nf)%4096:
        raise ValueError('image integration must contain whole VDIF frames and FFT blocks')
    validate_aligned_dimensions({**config,'blocks_per_integration':image_blocks},1)
    stations=len(config['stations'])
    if window_count*nf*stations*(stations-1)//2>MAX_SPECTRAL_CELLS:
        raise ValueError('sequence exceeds one million spectral cells')
    if integration_s>span+1e-9:raise ValueError('image integration must be covered by each pilot')
    if step_s is None:step_s=span
    if step_s<max(span,integration_s)-1e-9:raise ValueError('sequence pilot windows must not overlap')
    starts=start_offset_s+np.arange(window_count)*step_s
    return [{'window_index':i,'start_offset_s':float(t),'pilot_end_s':float(t+span),
             'image_end_s':float(t+integration_s)} for i,t in enumerate(starts)]


def process_sequence(manifest,clock_model,output,*,window_count=3,step_s=None,start_offset_s=.002,
                     pilot_integrations=256,pilot_integration_s=None,integration_s=.3,max_rate_hz=100.,
                     starts=3,max_iterations=800,prior_fwhm_arcsec=240.,entropy=.01,tsv=.0001,progress=None,
                     require_rate_consistency=False,rate_model="constant"):
    if not isinstance(require_rate_consistency,bool):raise ValueError('require_rate_consistency bool required')
    if rate_model not in ('constant','linear'):raise ValueError('rate_model must be constant or linear')
    if rate_model=='linear' and require_rate_consistency:
        raise ValueError('constant subpilot consistency requirement cannot be combined with linear rate correction')
    config=load_session(manifest)
    plan=plan_windows(config,window_count,step_s,start_offset_s,pilot_integrations,pilot_integration_s,integration_s)
    out=Path(output);partial=out.with_name(out.name+'.partial')
    if out.exists() or partial.exists():raise FileExistsError('choose a new sequence directory')
    partial.mkdir(parents=True)
    state={'schema_version':1,'type':'short_window_sequence','state':'running','planned_windows':plan,
           'completed_windows':[],'current_window_index':None,'phase':'prepared','completed_steps':0,'total_steps':3*window_count+1}
    def unchanged():
        source_identity.assert_current(manifest,clock_model,config)
    def save():
        (partial/'sequence.json').write_text(json.dumps(state,indent=2)+'\n')
    def phase(label):
        state['completed_steps']+=1;state['phase']=label;save()
        if progress:progress(label,state['completed_steps'])
    identity=None;records=[];paths=[]
    try:
        source_identity=InputIdentity(manifest,clock_model,expected_config=config)
        state['input_identity']=source_identity.diagnostics;save()
        for window in plan:
            index=window['window_index'];state['current_window_index']=index;save();unchanged()
            prefix=f'window-{index:04d}'
            result=process_closure_session(manifest,clock_model,partial/prefix,
                pilot_integrations=pilot_integrations,pilot_integration_s=pilot_integration_s,
                start_offset_s=window['start_offset_s'],integration_s=integration_s,max_rate_hz=max_rate_hz,
                correlation_only=True,_source_identity=source_identity,
                require_rate_consistency=require_rate_consistency,rate_model=rate_model,
                progress=lambda label,done:phase(f'window_{index}:{label}'))
            unchanged()
            current={key:result[key] for key in ['input_manifest_sha256','input_clock_sha256','input_observation_sha256','input_vdif']}
            if identity is not None and current!=identity:raise ValueError('input identity changed between windows')
            identity=current;records.append({**window,'relative_directory':prefix,
                'rate_estimate':result['rate_estimate'],'rate_acquisition':result['rate_acquisition'],
                'rate_consistency':result.get('rate_consistency'),'correlation':result['correlation']})
            paths.append(partial/prefix/'correlation/shard-00000.npz')
            state['completed_windows'].append(index);save()
        state.update(current_window_index=None,phase='synthesis');save()
        from vsora_imaging.synthesis import image_synthesis
        synthesis=image_synthesis(paths,partial/'synthesis',starts=starts,max_iterations=max_iterations,
            prior_fwhm_arcsec=prior_fwhm_arcsec,entropy=entropy,tsv=tsv,pixels=32,
            pixel_arcsec=config['_config']['image']['pixel_arcsec'])
        unchanged();phase('sequence_relative_rml')
        unchanged()
        diagnoses=[r['rate_consistency']['state'] for r in records if r['rate_consistency'] is not None]
        aggregate='variation_detected' if 'variation_detected' in diagnoses else ('unverified' if 'unverified' in diagnoses or len(diagnoses)!=window_count else 'consistent')
        result={**state,'state':'complete','current_window_index':None,**identity,'windows':records,
                'rate_consistency':{'state':aggregate,'window_counts':{s:diagnoses.count(s) for s in ('consistent','variation_detected','unverified')},
                                    'coherence_stability_measured':False},
                'rate_model':rate_model,'rate_consistency_policy':'required' if require_rate_consistency else 'report',
                'input_identity':source_identity.diagnostics,
                'closures':synthesis['closures'],'rml':synthesis['rml'],'synthesis':synthesis['synthesis'],
                'window_step_s':plan[1]['start_offset_s']-plan[0]['start_offset_s'],
                'nominal_image_exposure_per_station_s':window_count*integration_s,
                'effective_exposure_per_baseline_s':synthesis['synthesis']['exposure_per_baseline_s'],
                'selected_pilot_start_to_end_span_s':plan[-1]['pilot_end_s']-plan[0]['start_offset_s'],
                'inputs_stat_unchanged':True,'absolute_flux_measured':False,'absolute_position_measured':False,
                'limits':'Each <=3s pilot has constant sky/gain and selected constant or smooth linear relative LO model; supplied linear sample clocks. No arbitrary phase-noise recovery. Nonoverlapping windows, independent noise approximation, high-SNR closures, <=64 windows. Fresh full original hashes shared in this run, ordinary stat guards; no hours-scale throughput claim.'}
        (partial/'sequence.json').write_text(json.dumps(result,indent=2)+'\n')
        (partial/'summary.json').write_text(json.dumps(result,indent=2)+'\n');partial.rename(out);return result
    except Exception as exc:
        state.update(state='incomplete',error_type=type(exc).__name__)
        save();(partial/'failure.json').write_text(json.dumps(state,indent=2)+'\n');raise


def main():
    import argparse
    p=argparse.ArgumentParser(description='Short nonoverlapping VDIF windows -> local rates -> relative closure synthesis')
    p.add_argument('--manifest',required=True);p.add_argument('--clock-model',required=True);p.add_argument('--output',required=True)
    p.add_argument('--window-count',type=int,default=3);p.add_argument('--step-s',type=float,help='Start spacing; defaults to nonoverlapping pilot span')
    p.add_argument('--start-offset-s',type=float,default=.002);p.add_argument('--pilot-integrations',type=int,default=256)
    p.add_argument('--pilot-integration-s',type=float);p.add_argument('--integration-s',type=float,default=.3)
    p.add_argument('--max-rate-hz',type=float,default=100.);p.add_argument('--starts',type=int,default=3)
    p.add_argument('--rate-model',choices=['constant','linear'],default='constant')
    p.add_argument('--require-rate-consistency',action='store_true')
    p.add_argument('--max-iterations',type=int,default=800);p.add_argument('--prior-fwhm-arcsec',type=float,default=240.)
    p.add_argument('--entropy',type=float,default=.01);p.add_argument('--tsv',type=float,default=.0001)
    args=vars(p.parse_args());manifest=args.pop('manifest');clock=args.pop('clock_model');output=args.pop('output')
    print(json.dumps(process_sequence(manifest,clock,output,**args),indent=2))


if __name__=='__main__':main()
