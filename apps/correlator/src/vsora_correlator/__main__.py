import argparse
import json
from .session import correlate_session,calibrate_shard,apply_shard
from .aligned import correlate_aligned
from vsora_formats.casa import prepare_casa_input


def main():
    p=argparse.ArgumentParser(description='V-SoRA reference VDIF session processing')
    s=p.add_subparsers(dest='command',required=True)
    a=s.add_parser('correlate');a.add_argument('--manifest',required=True);a.add_argument('--output',required=True)
    a.add_argument('--rate-calibration');a.add_argument('--allow-calibration-extrapolation',action='store_true')
    a=s.add_parser('calibrate');a.add_argument('--input',required=True);a.add_argument('--output',required=True)
    model=a.add_mutually_exclusive_group(required=True)
    model.add_argument('--point-flux-jy',type=float);model.add_argument('--model-config')
    a.add_argument('--reference-station',type=int,default=0)
    a=s.add_parser('apply');a.add_argument('--input',required=True);a.add_argument('--calibration',required=True)
    a.add_argument('--output',required=True);a.add_argument('--allow-calibration-extrapolation',action='store_true')
    a=s.add_parser('correlate-aligned');a.add_argument('--manifest',required=True);a.add_argument('--clock-model',required=True)
    a.add_argument('--output',required=True);a.add_argument('--integrations',type=int,required=True)
    a.add_argument('--start-offset-s',type=float,default=.002)
    a.add_argument('--save-bispectrum',action='store_true',help='Also save common-FFT raw third-order sums; actual independence and RML likelihood unverified')
    a.add_argument('--sequential-input',action='store_true',help='Read and check the entire prefix instead of seeking with FIR guard');a.add_argument('--rate-profile');a.add_argument('--allow-rate-extrapolation',action='store_true')
    a=s.add_parser('casa-input');a.add_argument('--input',required=True);a.add_argument('--output',required=True)
    a=p.parse_args()
    if a.command=='correlate': r=correlate_session(a.manifest,a.output,a.rate_calibration,a.allow_calibration_extrapolation)
    elif a.command=='calibrate': r=calibrate_shard(a.input,a.output,a.point_flux_jy,a.reference_station,a.model_config)
    elif a.command=='correlate-aligned': r=correlate_aligned(a.manifest,a.clock_model,a.output,a.integrations,a.start_offset_s,a.rate_profile,a.allow_rate_extrapolation,not a.sequential_input,collect_bispectrum=a.save_bispectrum)
    elif a.command=='casa-input': r=prepare_casa_input(a.input,a.output)
    else: r=apply_shard(a.input,a.calibration,a.output,a.allow_calibration_extrapolation)
    print(json.dumps(r,indent=2))


if __name__=='__main__': main()
