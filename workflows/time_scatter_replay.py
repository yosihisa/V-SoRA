"""Replay a closed Stage039 synthetic archive for passive pilot diagnostics."""
import json
from pathlib import Path
from vsora_correlator.aligned import correlate_aligned
from vsora_correlator.time_scatter import diagnose_time_file


def run(archive,output):
    base=Path(archive);out=Path(output);out.mkdir(parents=True,exist_ok=False);results={}
    for label,folder,profile_name in [('control','control-constant','rate-only.json'),('fast','fast-linear','rate-linear.json')]:
        src=base/folder
        correlate_aligned(src/'pilot-manifest.json',src/'clock.json',out/label/'pilot',1500)
        q=diagnose_time_file(out/label/'pilot/shard-00000.npz',out/label/'time-scatter.json',16,src/profile_name)
        print(label,q['state'],[(b['station_ids'],b['mean_to_time_power_ratio_unbounded']) for b in q.get('baselines',[])],flush=True)
        results[label]=q
    old=diagnose_time_file(base/'fast-linear/pilot/shard-00000.npz',out/'old-archive.json',16,base/'fast-linear/rate-linear.json')
    assert old['state']=='unverified' and old['cell_reason']=='missing_station_power_flags_or_fft_counts'
    a=[x['mean_to_time_power_ratio_unbounded'] for x in results['control']['baselines']]
    b=[x['mean_to_time_power_ratio_unbounded'] for x in results['fast']['baselines']]
    assert min(a)>.97
    assert min(b)<.85*min(a)
    q={'state':'complete','source':'Stage039 fixed Gaussian IQ -> complex8 VDIF archives; re-correlated for common FFT counts',
       'old_archive_state':old['state'],'old_archive_reason':old['cell_reason'],
       'control':results['control'],'fast_periodic':results['fast'],
       'generating_truth_used_by_diagnostic':False,'same_pilot_profile_fit_dependence_calibrated':False,
       'within_cell_loss_recovered':False,'real_hardware_validation_performed':False,
       'scope':'Center-rotated saved pilot, passive scatter only. Independent nominal FFT/time cells assumed, no hardware false-alarm or coherence estimate.'}
    (out/'summary.json').write_text(json.dumps(q,indent=2,allow_nan=False)+'\n')
    return q


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--archive",required=True);p.add_argument("--output",required=True)
    run(**vars(p.parse_args()))


if __name__=="__main__":main()
