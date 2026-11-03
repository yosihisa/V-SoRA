"""Independent finite clocked-band study on a small deterministic artificial fixture."""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import resource
import sys
import time

import numpy as np
from vsora_formats.lba import LBAFragmentRecording
from vsora_formats.lba_band import LBAComplexBandView
from vsora_correlator.lba_alignment import LBAClockedBandView
if __package__ in (None, ''):
    # Public study helpers live in this repository; product imports stay installed.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workflows.lba_complex_band_validation import finite_reference
from workflows.public_lba_fragments import scalar_reference


RTOL, ATOL = 1e-9, 1e-5


def model_case(index=0):
    return {'schema_version':1, 'station_id':'ARTIFICIAL-'+str(index),
        'time_origin_utc':'2020-01-02T03:04:05.123456789Z',
        'input_start_offset_s':[.001, .0027][index],
        'actual_sample_rate_hz':[8000083, 7999873][index],
        'rf_band_edge_hz':[1719000137, 1718999789][index],
        'output_center_frequency_hz':1721000000,
        'phase_offset_rad':[.2, -.4][index],
        'clock_provenance':'supplied_model', 'rf_provenance':'supplied_model'}


def finite_clock_reference(levels, n0, model, times, invalid=()):
    """Exact binary-input coordinates, separate finite FIR/65-term sums and phase."""
    band = finite_reference(np.asarray(levels, float), n0)
    values, validity, positions = [], [], []
    rate, offset = Fraction(model['actual_sample_rate_hz']), Fraction(model['input_start_offset_s'])
    edge = Fraction(model['rf_band_edge_hz'])-Fraction(model['output_center_frequency_hz'])
    for t in times:
        ft = Fraction(float(t)); position = float((ft-offset)*rate); positions.append(position)
        center = math.floor(position); indexes = range(center-32, center+33)
        coefficients = []
        for n in indexes:
            d = position-n
            sinc = 1. if d == 0 else math.sin(math.pi*d)/(math.pi*d)
            coefficients.append(sinc*(.5*(1+math.cos(math.pi*d/32)) if abs(d) <= 32 else 0.))
        norm = math.fsum(coefficients)
        z = complex(math.fsum((band[n-64].real*c/norm for n,c in zip(indexes,coefficients))),
                    math.fsum((band[n-64].imag*c/norm for n,c in zip(indexes,coefficients))))
        good = not any(center-96 < right and center+97 > left for left,right in invalid)
        cycles = (edge+rate/4)*ft-rate*offset/4+Fraction(n0,4)
        angle = math.tau*float(cycles % 1)+math.remainder(model['phase_offset_rad'],math.tau)
        values.append(z*complex(math.cos(angle),math.sin(angle)) if good else 0j)
        validity.append(good)
    return np.array(values), np.array(validity), np.array(positions)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def run(fixture, real_input, output):
    fixture, real_input, output = map(Path, (fixture, real_input, output))
    if output.exists():raise FileExistsError('choose a new clocked-band study directory')
    fixed = {'header.bin':'ece6274867844d64c1a52ac633e12336d2675b3ee2011bc340fae84d0d16f205',
             'payload.bin':'f85a0853664d11cf7fe1879ad0da58b447cac89665d63e8d46f12ce4eea95ff0'}
    assert all(sha(fixture/n)==h for n,h in fixed.items())
    output.mkdir(parents=True);began=time.monotonic()
    before=int(Path('/proc/self/statm').read_text().split()[1])*resource.getpagesize()
    raw=(fixture/'payload.bin').read_bytes();levels=scalar_reference(raw)
    arrays={};identities={};cases=[];max_error=max_position_error=0.;invalid_outputs=0
    for case in [0,1]:
        model=model_case(case)
        for pol in [0,1]:
            reader=LBAFragmentRecording(fixture/'header.bin',fixture/'payload.bin',1,
                nominal_sample_rate_hz=8000000,recorded_pol_order=('R','L'))
            source=LBAComplexBandView(reader,recorded_pol_index=pol,sideband='U')
            view=LBAClockedBandView(source,model=model,invalid_source_ranges=[(1050,1052)])
            assert source.actual_sample_rate_hz is None and source.station_id is None
            identities[f'm{case}-p{pol}']=view.processing_identity
            for start in [96.125,1027.25,12000.5]:
                times=model['input_start_offset_s']+(start+np.arange(129)*1.0001)/model['actual_sample_rate_hz']
                got=view.query(times)
                expected, valid, positions=finite_clock_reference(levels[:,pol],2,model,times,[(1050,1052)])
                np.testing.assert_allclose(got['complex_samples'],expected,rtol=RTOL,atol=ATOL)
                np.testing.assert_array_equal(got['valid'],valid)
                np.testing.assert_allclose(got['source_positions'],positions,rtol=0,atol=1e-9)
                chunks=[];first=0
                for count in [1,7,31,90]:
                    chunks.append(view.query(times[first:first+count]));first+=count
                for key in ['complex_samples','valid','source_positions','query_times_s']:
                    np.testing.assert_array_equal(got[key],np.concatenate([x[key] for x in chunks]))
                error=float(np.max(abs(got['complex_samples']-expected)));max_error=max(max_error,error)
                max_position_error=max(max_position_error,float(np.max(abs(got['source_positions']-positions))))
                prefix=f'm{case}-p{pol}-s{start}'
                for key,value in {'actual':got['complex_samples'],'expected':expected,'valid':valid,
                                  'source_positions':got['source_positions'],'query_times':times}.items():
                    arrays[prefix+'-'+key]=value
                invalid_outputs+=int((~valid).sum());cases.append({'case':prefix,'query_count':129,'max_error':error})
            assert reader.payload_hash_reads==1
    receipt=json.loads((real_input/'receipt.json').read_text());rejected=[]
    for station in receipt['plan']['stations']:
        folder=real_input/('station-'+station['id'])
        rows={Path(x['file']).name:x for x in receipt['reads'] if x['file'].startswith('station-'+station['id']+'/')}
        reader=LBAFragmentRecording(folder/'header.bin',folder/'payload.bin',station['payload_offset'],
            nominal_sample_rate_hz=8000000,recorded_pol_order=station['recorded_pol_order'],
            expected_header_sha256=rows['header.bin']['sha256'],expected_payload_sha256=rows['payload.bin']['sha256'])
        source=LBAComplexBandView(reader,recorded_pol_index=0,sideband='U')
        unknown=model_case();unknown.update(actual_sample_rate_hz=None,rf_band_edge_hz=None)
        try:LBAClockedBandView(source,model=unknown)
        except ValueError:rejected.append(station['id'])
        else:raise AssertionError('unknown real clock/RF accepted')
        assert reader.payload_read_calls==0
    assert len(arrays)==60 and len(cases)==12 and len(rejected)==4 and invalid_outputs>0
    np.savez_compressed(output/'finite-clocked-band.npz',**arrays)
    summary={'state':'complete','input_kind':'new deterministic artificial 8192-byte code fixture',
        'input_sha256':fixed,'cases':cases,'NPZ_fields':60,'processing_identities':identities,
        'independent_max_abs_error':max_error,'exact_binary_coordinate_max_abs_error_samples':max_position_error,
        'invalid_output_count':invalid_outputs,'real_station_unknown_clock_RF_rejected':rejected,
        'real_recording_complex_query_count':0,'source_parent_actual_clock_modified':False,
        'RTOL':RTOL,'ATOL_code_unit':ATOL,'MCSE':None,'new_MC_trials':0,
        'new_real_acquisition_or_original_change':False,'new_real_correlation_Closure_image':False,
        'scope':'Finite caller-model arithmetic; no real clock or RF estimation/authentication',
        'wall_s':time.monotonic()-began,'import_current_RSS_bytes':before,
        'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        'conservative_additional_peak_bytes':max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024-before)}
    assert all(sha(fixture/n)==h for n,h in fixed.items())
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (output/'environment.json').write_text(json.dumps({'product_modules':{n:m.__file__ for n,m in sys.modules.items()
        if n.startswith('vsora_') and getattr(m,'__file__',None)}},indent=2)+'\n')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['fixture','real-input','output']:p.add_argument('--'+name,required=True)
    a=p.parse_args();print(json.dumps(run(a.fixture,a.real_input,a.output)))
