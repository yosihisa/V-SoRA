import argparse
import json
from .session import correlate_session,calibrate_shard,apply_shard


def main():
    p=argparse.ArgumentParser(description='V-SoRA reference VDIF session processing')
    s=p.add_subparsers(dest='command',required=True)
    a=s.add_parser('correlate');a.add_argument('--manifest',required=True);a.add_argument('--output',required=True)
    a.add_argument('--rate-calibration');a.add_argument('--allow-calibration-extrapolation',action='store_true')
    a=s.add_parser('calibrate');a.add_argument('--input',required=True);a.add_argument('--output',required=True)
    a.add_argument('--point-flux-jy',type=float,required=True);a.add_argument('--reference-station',type=int,default=0)
    a=s.add_parser('apply');a.add_argument('--input',required=True);a.add_argument('--calibration',required=True)
    a.add_argument('--output',required=True);a.add_argument('--allow-calibration-extrapolation',action='store_true')
    a=p.parse_args()
    if a.command=='correlate': r=correlate_session(a.manifest,a.output,a.rate_calibration,a.allow_calibration_extrapolation)
    elif a.command=='calibrate': r=calibrate_shard(a.input,a.output,a.point_flux_jy,a.reference_station)
    else: r=apply_shard(a.input,a.calibration,a.output,a.allow_calibration_extrapolation)
    print(json.dumps(r,indent=2))


if __name__=='__main__': main()
