"""Bounded original LBA fragments and a limited real/2-pol/2-bit probe.

This is not a product reader or an astronomical correlation. Keep recordings,
provider metadata, arrays and numerical reports out of Git. The acquisition
plan names exact original offsets; headers are never rewritten for a crop.
"""
import argparse
import datetime as dt
import ftplib
import hashlib
import json
import math
from pathlib import Path
import re
import resource
import shutil
import socket
import tarfile
import time

import numpy as np

LEVELS = np.array([8191, -8192, 24575, -24576], dtype=np.int16)
FFT_STARTS = (0, 262144, 524288, 1048576)
SAMPLES = 2097152


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def old_header(data):
    if not isinstance(data, bytes) or re.fullmatch(rb'\d{8}:\d{6}\n', data) is None:
        raise ValueError('limited old LBA timestamp header required')
    try:
        return dt.datetime.strptime(data.decode('ascii'), '%Y%m%d:%H%M%S\n').replace(tzinfo=dt.timezone.utc)
    except ValueError as error:
        raise ValueError('invalid old LBA calendar') from error


def window_offset(header, start, payload_bytes):
    epoch = old_header(header)
    start = dt.datetime.fromisoformat(start.replace('Z', '+00:00'))
    if start.tzinfo is None or start.utcoffset() != dt.timedelta(0):
        raise ValueError('explicit UTC start required')
    delta = start-epoch
    us = (delta.days*86400+delta.seconds)*1000000+delta.microseconds
    # Supplied 8 MHz, two real 2-bit polarizations: four bytes per microsecond.
    offset = us*4
    if offset < 0 or offset+1048576 > payload_bytes:
        raise ValueError('selected window outside original payload')
    return offset


def decode(raw):
    if not isinstance(raw, bytes) or not raw or len(raw) % 2:
        raise ValueError('positive whole little-endian u16 payload required')
    bits = np.unpackbits(np.frombuffer(raw, np.uint8), bitorder='little').reshape(-1, 2)
    codes = (bits[:, 0]+2*bits[:, 1]).reshape(-1, 2)
    return codes, LEVELS[codes]


def scalar_reference(raw):
    """u16 word/time/band loops, separate from vector bit-plane unpacking."""
    if not raw or len(raw) % 2:
        raise ValueError('whole u16 reference payload required')
    result = np.empty((len(raw)*2, 2), np.int16)
    levels = (8191, -8192, 24575, -24576)
    for word_index in range(len(raw)//2):
        word = int.from_bytes(raw[2*word_index:2*word_index+2], 'little')
        for tick in range(4):
            for band in range(2):
                result[4*word_index+tick, band] = levels[(word >> (4*tick+2*band)) & 3]
    return result


def repack(codes):
    if codes.ndim != 2 or codes.shape[1] != 2 or codes.size % 4 or codes.dtype != np.uint8 or np.any(codes > 3):
        raise ValueError('two-band uint8 codes in 0..3 required')
    c = codes.reshape(-1, 4)
    return (c[:, 0] | (c[:, 1] << 2) | (c[:, 2] << 4) | (c[:, 3] << 6)).tobytes()


def make_plan(probe):
    stations=[]
    for entry in probe['entries']:
        identity=Path(entry['name']).name.split('_')[1].upper()
        if identity not in {'AT','HO','MP','PA'} or entry['size'] != 40000016:
            raise ValueError('limited four-station LBA member required')
        header=entry['ASCII_header_prefix'].encode('ascii');old_header(header)
        tar_headers=[r for r in probe['reads'] if r['offset']==entry['header_offset'] and r['bytes']==512]
        if len(tar_headers)!=1:raise ValueError('unique original tar header required')
        stations.append({'id':identity,'member':entry['name'],'member_bytes':entry['size'],
            'header_offset':entry['header_offset'],'data_offset':entry['data_offset'],
            'archive_header_sha256':tar_headers[0]['sha256'],'file_header_sha256':hashlib.sha256(header).hexdigest(),
            'payload_offset':window_offset(header,'2005-03-11T22:08:40.002Z',entry['size']-16),
            'recorded_pol_order':['L','R'] if identity=='PA' else ['R','L']})
    if {s['id'] for s in stations}!={'AT','HO','MP','PA'} or len(stations)!=4:
        raise ValueError('four distinct station members required')
    return {'host':'ftp.mpifr-bonn.mpg.de','archive_path':probe['archive'],'archive_bytes':probe['archive_bytes'],
            'archive_MDTM':probe['archive_MDTM'],'selected_start_utc':'2005-03-11T22:08:40.002Z',
            'stations':sorted(stations,key=lambda s:s['id']),
            'usage_scope':'official testing/verification instructions; local nonredistribution; no separate broad data license inferred',
            'source':'https://github.com/difx/difx/wiki/datasets'}


def probe_archive(output):
    """Save only tar index headers and old 16-byte member timestamp headers."""
    out=Path(output)
    if out.exists():raise FileExistsError('choose a new header probe directory')
    out.mkdir(parents=True);began=time.monotonic();rows=[];received=0;stamp=None
    name='/vlbiarchive/DiFX_testdata/lba_4MHz/lba_4MHz.data.tar'
    def read(offset,count,label):
        nonlocal received,stamp
        if received+count>65536 or offset<0 or offset+count>160010240 or time.monotonic()-began>180:
            raise ValueError('header probe budget')
        f=ftplib.FTP('ftp.mpifr-bonn.mpg.de',timeout=10);blob=bytearray()
        try:
            f.login();f.voidcmd('TYPE I')
            if f.size(name)!=160010240:raise ValueError('archive size differs')
            current=f.sendcmd('MDTM '+name)
            if stamp is None:stamp=current
            if stamp!=current:raise ValueError('archive MDTM changed')
            stream=f.transfercmd('RETR '+name,rest=offset)
            try:
                while len(blob)<count:
                    block=stream.recv(count-len(blob))
                    if not block:raise EOFError('short header')
                    blob.extend(block);received+=len(block)
            finally:stream.close()
        finally:f.close()
        (out/label).write_bytes(blob)
        rows.append({'offset':offset,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'saved':label})
        return bytes(blob)
    entries=[];offset=0
    for index in range(12):
        header=read(offset,512,f'tar-header-{index:02d}.bin')
        if not header.strip(b'\0'):break
        item=tarfile.TarInfo.frombuf(header,'utf-8','strict')
        if not item.isfile() or not item.name.endswith('.lba') or item.name.startswith('/') or '..' in Path(item.name).parts:
            raise ValueError('limited regular LBA member required')
        content=read(offset+512,16,f'file-header-{index:02d}.bin');old_header(content)
        entries.append({'name':item.name,'size':item.size,'type':'0','header_offset':offset,'data_offset':offset+512,
                        'ASCII_header_prefix':content.decode('ascii')})
        offset+=512+((item.size+511)//512)*512
    else:raise ValueError('tar entry budget')
    result={'archive':name,'archive_bytes':160010240,'archive_full_SHA256':None,'archive_MDTM':stamp,
            'bounded_client_received_bytes':received,'TCP_wire_or_server_sent_bytes_measured':False,
            'entries':entries,'reads':rows,'elapsed_s':time.monotonic()-began}
    write_json(out/'probe.json',result);write_json(out/'acquire-plan.json',make_plan(result));return result


def acquire(plan_path, output):
    plan = json.loads(Path(plan_path).read_text());out = Path(output);partial = out.with_name(out.name+'.partial')
    if out.exists() or partial.exists():
        raise FileExistsError('choose a new fragment directory')
    if plan['archive_bytes'] != 160010240 or len(plan['stations']) != 4:
        raise ValueError('fixed four-station archive plan required')
    if shutil.disk_usage(out.parent if out.parent.exists() else Path.cwd()).free < 10*1024**3:
        raise ValueError('10 GiB free reserve required')
    partial.mkdir(parents=True);rows=[];received=0;began=time.monotonic()
    def snapshot():
        f = ftplib.FTP(plan['host'], timeout=10)
        try:
            f.login();f.voidcmd('TYPE I')
            if f.size(plan['archive_path']) != plan['archive_bytes'] or f.sendcmd('MDTM '+plan['archive_path']) != plan['archive_MDTM']:
                raise ValueError('remote archive SIZE/MDTM changed')
            return f
        except BaseException:
            f.close();raise
    def receive(offset, count, dest):
        nonlocal received
        if count <= 0 or offset < 0 or offset+count > plan['archive_bytes'] or received+count > 32*1024**2:
            raise ValueError('bounded acquisition byte plan violated')
        if time.monotonic()-began > 180:
            raise TimeoutError('acquisition budget')
        f = snapshot();blob=bytearray()
        try:
            stream=f.transfercmd('RETR '+plan['archive_path'],rest=offset)
            stream.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,65536)
            try:
                while len(blob) < count:
                    if time.monotonic()-began > 180:raise TimeoutError('acquisition budget')
                    chunk=stream.recv(min(65536,count-len(blob)))
                    if not chunk:raise EOFError('short original fragment')
                    blob.extend(chunk);received+=len(chunk)
            finally:stream.close()
        finally:
            f.close();dest.write_bytes(blob)
            rows.append({'file':str(dest.relative_to(partial)),'archive_offset':offset,'bytes':len(blob),'sha256':digest(dest)})
            write_json(partial/'transfer.json',{'received_client_bytes':received,'reads':rows})
        return bytes(blob)
    try:
        for station in plan['stations']:
            dest=partial/('station-'+station['id']);dest.mkdir()
            archive_header=receive(station['header_offset'],512,dest/'archive-header.bin')
            item=tarfile.TarInfo.frombuf(archive_header,'utf-8','strict')
            if not item.isfile() or item.name != station['member'] or item.size != station['member_bytes'] or hashlib.sha256(archive_header).hexdigest() != station['archive_header_sha256']:
                raise ValueError('tar checksum/name/size/header changed')
            header=receive(station['data_offset'],16,dest/'header.bin')
            if hashlib.sha256(header).hexdigest() != station['file_header_sha256']:
                raise ValueError('original file header changed')
            offset=window_offset(header,plan['selected_start_utc'],item.size-16)
            if offset != station['payload_offset']:
                raise ValueError('selected original byte offset differs')
            receive(station['data_offset']+16+offset,1048576,dest/'payload.bin')
        final=snapshot();final.close()
        hashes=[r['sha256'] for r in rows if r['file'].endswith('payload.bin')]
        if len(set(hashes)) != 4:raise ValueError('station payloads must be distinct')
        receipt={'state':'complete','plan':plan,'client_received_bytes':received,'reads':rows,
                 'archive_full_sha256':None,'original_member_full_sha256':None,'producer_checksum_verified':False,
                 'wire_or_server_sent_bytes_measured':False,'clock_accuracy_measured':False,'wall_s':time.monotonic()-began}
        write_json(partial/'receipt.json',receipt);partial.rename(out);return receipt
    except BaseException as error:
        write_json(partial/'failure.json',{'state':'incomplete','error_type':type(error).__name__,'received_client_bytes':received,'reads':rows})
        raise


def finite_dft(x):
    n=len(x)
    return np.array([complex(math.fsum(float(v)*math.cos(2*math.pi*k*j/n) for j,v in enumerate(x)),
                             -math.fsum(float(v)*math.sin(2*math.pi*k*j/n) for j,v in enumerate(x)))
                     for k in range(n//2+1)])


def run(inputs, output):
    inputs=Path(inputs);out=Path(output)
    if out.exists():raise FileExistsError('choose a new validation directory')
    receipt_path=inputs/'receipt.json';receipt_sha=digest(receipt_path);receipt=json.loads(receipt_path.read_text())
    if receipt['state'] != 'complete':raise ValueError('completed acquisition required')
    def unchanged():
        if digest(receipt_path) != receipt_sha:raise ValueError('receipt changed')
        for row in receipt['reads']:
            path=inputs/row['file']
            if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:raise ValueError('fragment changed')
    unchanged();out.mkdir(parents=True);began=time.monotonic()
    before=int(Path('/proc/self/statm').read_text().split()[1])*resource.getpagesize()
    actual=[];references=[];errors=[];components=0;payload_bytes=0;stations=[]
    for station in receipt['plan']['stations']:
        folder=inputs/('station-'+station['id']);header=(folder/'header.bin').read_bytes();raw=(folder/'payload.bin').read_bytes()
        if len(raw) != 1048576 or window_offset(header,receipt['plan']['selected_start_utc'],station['member_bytes']-16) != station['payload_offset']:
            raise ValueError('fragment dimensions/epoch differ')
        codes,levels=decode(raw);reference=scalar_reference(raw)
        np.testing.assert_array_equal(levels,reference)
        if repack(codes) != raw:raise AssertionError('bit round trip differs')
        assert levels.shape==(SAMPLES,2)
        np.savez_compressed(out/('station-'+station['id']+'.npz'),codes=codes,levels=levels)
        for band in [0,1]:
            for start in FFT_STARTS:
                x=levels[start:start+256,band].astype(np.float64)/32768.
                value=np.fft.rfft(x);expected=finite_dft(x)
                np.testing.assert_allclose(value,expected,rtol=1e-11,atol=1e-8)
                actual.append(value);references.append(expected);errors.append(float(abs(value-expected).max()))
        components+=levels.size;payload_bytes+=len(raw)
        stations.append({'id':station['id'],'recorded_pol_order':station['recorded_pol_order'],
                         'supplied_original_header_utc':old_header(header).isoformat(),'original_payload_offset':station['payload_offset'],
                         'code_counts':np.bincount(codes.ravel(),minlength=4).tolist()})
    np.savez_compressed(out/'finite-fft.npz',actual=np.array(actual),independent=np.array(references))
    unchanged()
    result={'state':'complete','input_kind':'provider-described real V177A LBA calibrator recording fragments',
            'representation_components_exact':components,'roundtrip_payload_bytes_exact':payload_bytes,
            'selected_supplied_start_utc':receipt['plan']['selected_start_utc'],'nominal_samples_per_station':SAMPLES,
            'nominal_sample_rate_hz':8000000,'nominal_duration_s':.262144,'rf_band_edge_hz':1719000000,
            'sideband':'U','bandwidth_hz':4000000,'real_polarizations':2,'stations':stations,
            'fft_cases':len(errors),'fft_bins_per_case':129,'fft_max_abs_error':max(errors),'rtol':1e-11,'atol':1e-8,
            'fft_scale':'fixed DiFX s16 code / 32768; not physical voltage calibration','MCSE':None,
            'new_MC_trials':0,'real_fringe_correlation_closure_image_or_RTL_validation':False,
            'input_receipt_sha256':receipt_sha,'archive_full_sha256':None,'original_member_full_sha256':None,
            'producer_checksum_verified':False,'clock_accuracy_measured':False,
            'wall_s':time.monotonic()-began,'import_current_RSS_bytes':before,
            'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            'conservative_additional_peak_bytes':max(0,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024-before)}
    write_json(out/'summary.json',result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',action='store_true');parser.add_argument('--acquire-plan');parser.add_argument('--input');parser.add_argument('--output',required=True)
    args=parser.parse_args()
    if sum([args.probe,bool(args.acquire_plan),bool(args.input)])!=1:parser.error('choose probe, acquire-plan or input')
    print(json.dumps(probe_archive(args.output) if args.probe else acquire(args.acquire_plan,args.output) if args.acquire_plan else run(args.input,args.output)))
