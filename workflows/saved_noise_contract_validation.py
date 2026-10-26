"""既存の条件付き雑音APIを保存相関へ接続する。production RMLは変更しない。"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
from vsora_correlator.noise_diagnostics import diagnose_noise_cell, diagnose_noise_file
from vsora_formats.spectral import load_spectral
from vsora_imaging.closure import form_closures, independent_closures
from vsora_imaging.closure_noise import joint_closure_noise


def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()


def write_json(path,value): Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def identities(values):
    return {k:{'dtype':v.dtype.str,'shape':list(v.shape),'sha256':hashlib.sha256(v.tobytes(order='C')).hexdigest()}
            for k,v in values.items()}


def compare_noise(data,channel,diagnostic):
    """同じ有効行・production基底で比較。空の情報はnull、相関0へ置換しない。"""
    if diagnostic['state']!='conditional_estimate':
        return {'state':'not_available','reason':diagnostic.get('reason'),'metrics':None},{}
    if (diagnostic['channel_index']!=channel or diagnostic['time_index']!=0
            or diagnostic['frequency_hz']!=float(data['frequencies_hz'][channel])
            or diagnostic['visibility_unit']!=data['metadata']['visibility_unit']):
        raise ValueError('matching cell and visibility units required')
    v=data['visibilities'][0,channel];w=data['weights'][0,channel];pairs=data['pairs']
    full=joint_closure_noise(v,np.asarray(diagnostic['estimated_visibility_covariance']),pairs,min_snr=10.)
    ordinary=form_closures(v,w,pairs,min_snr=10.);split=full['phase_count']
    ip,cp=independent_closures(ordinary['phase_matrix'],ordinary['phase_valid']&full['joint_valid'][:split],ordinary['baseline_variance'])
    ia,ca=independent_closures(ordinary['logamp_matrix'],ordinary['logamp_valid']&full['joint_valid'][split:],ordinary['baseline_variance'])
    selected=np.r_[ip,split+ia];count=len(selected);approx=np.zeros((count,count))
    approx[:len(ip),:len(ip)]=cp;approx[len(ip):,len(ip):]=ca
    joint=full['joint_covariance'][np.ix_(selected,selected)]
    arrays={'selected_joint_rows':selected,'joint_comparison_covariance':joint,'production_comparison_covariance':approx,
            'joint_baseline_valid_snr10':full['baseline_valid'],'production_baseline_valid_snr10':ordinary['baseline_valid']}
    info={'state':'compared' if count else 'no_common_independent_closures','phase_rank':len(ip),'logamp_rank':len(ia),
          'production_min_snr':10.,'comparison_min_snr':10.,'diagnostic_default_min_snr':5.,
          'same_support_and_production_qr_basis':True,'phase_unit':'rad','logamp_unit':'1','metrics':None}
    if count:
        dj=np.diag(joint);da=np.diag(approx)
        if np.any(dj<=0) or np.any(da<=0):raise ValueError('positive selected covariance diagonal required')
        corr=joint/np.sqrt(np.outer(dj,dj));corr_a=approx/np.sqrt(np.outer(da,da));ratio=dj/da
        minimum=float(np.linalg.eigvalsh(corr).min())
        if minimum < -1e-10:raise ValueError('joint comparison covariance is not positive semidefinite')
        arrays.update(joint_comparison_correlation=corr,production_comparison_correlation=corr_a,diagonal_variance_ratio=ratio)
        limits=lambda a:None if not len(a) else [float(a.min()),float(a.max())]
        info['metrics']={'phase_variance_ratio_range':limits(ratio[:len(ip)]),'logamp_variance_ratio_range':limits(ratio[len(ip):]),
                         'maximum_correlation_difference':float(np.max(np.abs(corr-corr_a))),
                         'maximum_phase_logamp_correlation':None if not len(ip) or not len(ia) else float(np.max(np.abs(corr[:len(ip),len(ip):]))),
                         'minimum_joint_correlation_eigenvalue':minimum}
    return info,arrays


def diagnostic_projection(diagnostic):
    keys=('pairs','triangles','quadrangles','station_sample_covariance_real','station_sample_covariance_imag',
          'estimated_visibility_covariance','baseline_snr_conditional','closure_joint_valid','estimated_joint_closure_covariance')
    arrays={k:np.asarray(diagnostic[k]) for k in keys if k in diagnostic}
    return {k:v for k,v in diagnostic.items() if k not in keys},arrays


def run(reference,record133,output,*,installed=False,expected=None):
    reference=Path(reference).resolve();record133=Path(record133).resolve();out=Path(output).resolve();checkout=Path(__file__).resolve().parents[1]
    if out.exists():raise FileExistsError('choose new diagnostic study output')
    record=json.loads(record133.read_text());assert record['stage']==133 and len(record['input_correlation_sha256'])==12
    out.mkdir(parents=True);rows=[];timing=[]
    for case,digest in record['input_correlation_sha256'].items():
        input_path=reference/case/'pipeline/correlation/shard-00000.npz';assert sha(input_path)==digest
        data=load_spectral(input_path);assert data['visibilities'].shape[:2]==(1,8)
        for channel in range(8):
            root=out/case/f'channel-{channel}';root.mkdir(parents=True);path=root/'diagnostic.json';start=time.monotonic()
            command=[sys.executable,'-m','vsora_correlator.noise_diagnostics','--input',str(input_path),'--output',str(path),
                     '--time-index','0','--channel-index',str(channel)]
            if installed:
                q=subprocess.run(command,capture_output=True,text=True,timeout=30);(root/'cli.log').write_text(q.stdout+q.stderr)
                if q.returncode:raise RuntimeError(q.stderr[-2000:])
                diagnostic=json.loads(path.read_text())
            else:diagnostic=diagnose_noise_file(input_path,path,channel)
            timing.append({'case':case,'channel':channel,'elapsed_s':time.monotonic()-start})
            assert diagnostic['input_sha256']==digest and not diagnostic['iid_fft_independence_verified']
            assert not diagnostic['covariance_confidence_calibrated'] and not diagnostic['production_rml_noise_model_changed']
            comparison,arrays=compare_noise(data,channel,diagnostic);scalar,diagnostic_arrays=diagnostic_projection(diagnostic)
            arrays={**{'diagnostic_'+k:v for k,v in diagnostic_arrays.items()},**arrays}
            np.savez_compressed(root/'arrays.npz',**arrays)
            row={'case':case,'channel_index':channel,'diagnostic_json_sha256':sha(path),
                 'diagnostic_scalar_fields':scalar,'comparison':comparison,'arrays':identities(arrays)}
            if expected is not None and expected['cells'][len(rows)]!=row:raise ValueError('source/native cell mismatch')
            before=sha(path)
            if installed:
                repeated=subprocess.run(command,capture_output=True,text=True,timeout=30)
                assert repeated.returncode!=0 and 'FileExistsError' in repeated.stderr
            else:
                try:diagnose_noise_file(input_path,path,channel)
                except FileExistsError:pass
                else:raise AssertionError('existing diagnostic overwritten')
            assert sha(path)==before;rows.append(row)
            write_json(root/'science.json',row);write_json(out/'progress.json',{'state':'running','cells_completed':len(rows)})
        assert sha(input_path)==digest
        print(json.dumps({'case':case,'cells_completed':len(rows),'conditional':sum(v['diagnostic_scalar_fields']['state']=='conditional_estimate' for v in rows)}),flush=True)
        if sum(p.stat().st_size for p in out.rglob('*') if p.is_file())>128*1024**2:raise ValueError('128 MiB study limit exceeded')
    # 同じvisibilityでも診断用metadataを落としたfitterは入口が異なることを確認する。
    fitter=checkout/'outputs/stage133-source-study-final/high_a_t0.3/fitter.npz'
    assert sha(fitter)==next(v['fitter_archive_sha256'] for v in record['cases'] if v['case']=='high_a_t0.3')
    probe=diagnose_noise_cell(load_spectral(fitter),0,3)
    assert probe['state']=='unverified' and probe['reason']=='missing_station_power_flags_or_fft_counts'
    origins={n:m.__file__ for n,m in sys.modules.items() if n.startswith('vsora_') and getattr(m,'__file__',None)}
    write_json(out/'runtime-private.json',{'project_origins':origins});write_json(out/'measurements.json',{'cells':timing})
    result={'stage':135,'state':'complete','cells':rows,'fitter_probe':probe,'input_correlation_sha256':record['input_correlation_sha256'],
            'record133_sha256':sha(record133),'fixed_cells':96,'comparison_min_snr':10.,'diagnostic_default_min_snr':5.,
            'truth_read':False,'production_rml_changed':False,
            'limits':'Conditional nominal-iid Gaussian estimate on existing filtered/quantized data. No measured independence, coverage, low-SNR likelihood, image improvement or real receiver validation. Same support and production QR basis for covariance comparison.'}
    if expected is not None and result!=expected:raise ValueError('source/native science differs')
    write_json(out/'summary.json',result);write_json(out/'progress.json',{'state':'complete','cells_completed':96});return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference',required=True);p.add_argument('--record133',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.reference,a.record133,a.output)
