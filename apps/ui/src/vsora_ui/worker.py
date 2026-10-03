"""Fixed scientific operations run outside the web server process."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from .jobs import write_json
from .models import SimulationRequest,ValidationRequest,RmlRequest,AnalysisRequest,SequenceRequest,SynthesisRequest,SensitivityRequest,NoiseDiagnosticRequest,TimeScatterRequest


def plot_sequence_rates(result,path):
    """Measured local rates only: scatter without interpolating between pilots."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    windows=result['windows'];station_ids=windows[0]['rate_estimate']['station_ids']
    fig,ax=plt.subplots(figsize=(7.5,3.7))
    for index,station in enumerate(station_ids):
        color=f'C{index}'
        ax.scatter([row['rate_estimate']['time_reference_s'] for row in windows],
                   [row['rate_estimate']['station_rates_hz'][index] for row in windows],label=station,color=color)
        for row in windows:
            model=row['rate_estimate']
            if model['type']=='station_rate_linear':
                lo,hi=model['valid_time_range_s'];epoch=model['time_reference_s']
                ax.plot([lo,hi],[model['station_rates_hz'][index]+model['station_rate_slopes_hz_per_s'][index]*(t-epoch) for t in (lo,hi)],color=color,linewidth=.8)
        parts=[p for row in windows for p in (row.get('rate_consistency') or {}).get('subpilots',[]) if p['state']=='complete']
        ax.scatter([p['time_reference_s'] for p in parts],[p['station_rates_hz'][index] for p in parts],
                   color=color,marker='x',s=18,alpha=.7)
    ax.set(xlabel='Seconds from observation UTC origin',ylabel='Relative station rate (Hz)',
           title='Pilot (circle), subparts (x), selected linear model within pilot')
    ax.grid(alpha=.2);ax.legend(ncol=len(station_ids));fig.tight_layout();fig.savefig(path,dpi=140);plt.close(fig)


def plot_rate_parts(diagnosis,path,model=None):
    parts=[p for p in diagnosis.get('subpilots',[]) if p['state']=='complete']
    if not parts:return
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7.5,3.7))
    for index,station in enumerate(diagnosis['station_ids']):
        color=f'C{index}'
        ax.scatter([p['time_reference_s'] for p in parts],[p['station_rates_hz'][index] for p in parts],label=station,color=color)
        if model and model.get('type')=='station_rate_linear':
            lo,hi=model['valid_time_range_s'];epoch=model['time_reference_s']
            ax.plot([lo,hi],[model['station_rates_hz'][index]+model['station_rate_slopes_hz_per_s'][index]*(t-epoch) for t in (lo,hi)],color=color,linewidth=.8)
    ax.set(xlabel='Seconds from observation UTC origin',ylabel='Relative station rate (Hz)',
           title='Four-part pilot rates; consistency does not prove coherence')
    ax.grid(alpha=.2);ax.legend(ncol=len(diagnosis['station_ids']));fig.tight_layout();fig.savefig(path,dpi=140);plt.close(fig)


def layout(stations,kind):
    import numpy as np
    if kind=='line': return np.column_stack([np.linspace(-300,300,stations),np.zeros(stations),np.zeros(stations)]).tolist()
    if kind=='ring':
        a=np.arange(stations)*2*np.pi/stations
        return np.column_stack([300*np.cos(a),300*np.sin(a),np.zeros(stations)]).tolist()
    points=np.array([[-200,-130,0],[-180,-100,0],[160,-180,0],[220,170,0],
                     [-240,160,0],[-40,40,0],[40,-80,0],[180,20,0]],float)[:stations]
    return (points*600/np.linalg.norm(points[:,None]-points[None,:],axis=-1).max()).tolist()


def simulation_config(request):
    from vsora_observation import validate_config
    return validate_config({
        'schema_version':1,'site':{'latitude_deg':35.,'longitude_deg':135.,'height_m':0.,
                                    'description':'Assumed synthetic site for GUI simulation'},
        'source':{'frame':'icrs','ra_deg':350.8664166662,'dec_deg':58.8117777793,
                  'model':request.model,'total_flux_jy':request.flux_jy},
        'observation':{'start_utc':'2026-10-02T08:00:00Z','duration_s':request.duration_s,
                       'integration_s':request.integration_s,'frequency_hz':1.42e9,
                       'bandwidth_hz':2048000.,'elevation_min_deg':15.},
        'stations':[{'id':f'ST{i+1:02d}','enu_m':p,'sefd_jy':request.sefd_jy}
                    for i,p in enumerate(layout(request.stations,request.layout))],
        'image':{'pixels':64,'pixel_arcsec':16.},'noise':{'enabled':request.noise,'efficiency':1.},'seed':request.seed})


def run(job):
    data=json.loads((job/'request.json').read_text());workspace=Path(data['workspace'])
    raw=data['request'];request={'simulation':SimulationRequest,'validation':ValidationRequest,'rml':RmlRequest,
                              'analysis':AnalysisRequest,'sequence':SequenceRequest,
                              'synthesis':SynthesisRequest,'sensitivity':SensitivityRequest,'noise':NoiseDiagnosticRequest,'time_scatter':TimeScatterRequest}[raw['kind']](**raw)
    status=json.loads((job/'status.json').read_text())
    def phase(text,done=0):
        if (job/'cancel').exists(): raise InterruptedError('cancelled')
        status.update(state='running',phase=text,completed_steps=done);write_json(job/'status.json',status)
    try:
        if request.kind=='simulation':
            from vsora_simulator.__main__ import simulate
            from vsora_imaging.__main__ import image_visibility,compare_models
            import numpy as np
            from astropy.io import fits
            phase('模擬相関値を生成しています')
            config=simulation_config(request);write_json(job/'observation.json',config)
            visibility=simulate(config,job/'simulation')
            phase('画像を復元しています',1)
            result=image_visibility(visibility,job/'imaging',None if request.model=='point' else 220)
            truth=np.load(job/'simulation/truth.npy');model=fits.getdata(job/'imaging/model.fits')
            metrics,a,b=compare_models(truth,model,16)
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from vsora_observation.geometry import observation_geometry
            g=observation_geometry(config);uv=g['uvw_lambda'].reshape(-1,3)
            positions=np.asarray([s['enu_m'] for s in config['stations']])
            fig,ax=plt.subplots(1,4,figsize=(13,3.1))
            ax[0].scatter(positions[:,0],positions[:,1]);ax[0].set(title='Station layout',xlabel='East (m)',ylabel='North (m)');ax[0].set_aspect('equal')
            ax[1].scatter(uv[:,0],uv[:,1],s=1);ax[1].scatter(-uv[:,0],-uv[:,1],s=1)
            ax[1].set(title='uv coverage',xlabel='u (wavelength)',ylabel='v (wavelength)');ax[1].set_aspect('equal')
            for axis,title,image in zip(ax[2:],['Truth, common beam','Recovered, common beam'],[a,b]):
                axis.imshow(image,origin='lower',cmap='inferno',vmin=0,vmax=a.max());axis.set_title(title)
            fig.tight_layout();fig.savefig(job/'comparison.png',dpi=140);plt.close(fig)
            write_json(job/'summary.json',{'type':'simulation','assumptions':'Ideal visibility, synthetic site, no receiver timing or calibration errors',
                        'config':config,'metrics':metrics,'imaging':result})
        elif request.kind=='rml':
            from vsora_imaging.experiment import run_simulation
            phase('短積分の模擬相関からClosure＋RMLを実行しています')
            result=run_simulation(simulation_config(request),job/'rml-simulation',snapshots=request.snapshots,
                starts=request.starts,max_iterations=request.max_iterations,prior_fwhm_arcsec=request.prior_fwhm_arcsec,
                entropy=request.entropy,tsv=request.tsv)
            write_json(job/'summary.json',result)
        elif request.kind in ('analysis','sequence'):
            from vsora_correlator.closure_pipeline import process_closure_session
            def input_path(value):
                path=Path(value);path=path if path.is_absolute() else workspace/path
                if path.suffix.lower()!='.json' or not path.is_file():raise ValueError('existing local JSON file required')
                return path.resolve()
            phase('VDIFの確認とsample整列を実行しています')
            options=request.model_dump(exclude={'kind','manifest','clock_model'})
            messages={'aligned_pilot':'周波数差を推定しています','model_free_rate':'IQを補正して短積分相関を実行しています',
                      'rate_corrected_short_correlation':'Closureを取り出しています','closure_extraction':'RMLで相対画像を探しています',
                      'relative_rml':'入力と結果を保存しています'}
            if request.kind=='sequence':
                from vsora_correlator.sequence import process_sequence
                def sequence_progress(step,done):
                    if step=='sequence_relative_rml':return phase('入力と結果を保存しています',done)
                    window,label=step.split(':');index=int(window.removeprefix('window_'))
                    text={'aligned_pilot':'局周波数差を推定しています',
                          'model_free_rate':'IQを補正して短積分相関を実行しています',
                          'rate_corrected_short_correlation':'区間の相関結果を保存しています'}[label]
                    if done==3*request.window_count:text='複数区間のClosureからRML画像を探しています'
                    phase(f'区間 {index+1}/{request.window_count}：{text}',done)
                result=process_sequence(input_path(request.manifest),input_path(request.clock_model),job/'sequence',
                                       progress=sequence_progress,**options)
                plot_sequence_rates(result,job/'sequence/rates.png')
            else:
                result=process_closure_session(input_path(request.manifest),input_path(request.clock_model),job/'analysis',
                                progress=lambda step,done:phase(messages[step],done),**options)
                plot_rate_parts(result['rate_consistency'],job/'analysis/rate-parts.png',result['rate_estimate'])
            write_json(job/'summary.json',result)
        elif request.kind=='noise':
            from vsora_correlator.noise_diagnostics import diagnose_noise_file
            from .noise import spectral_input
            phase('相関の保存情報と共通FFT集合を確認しています')
            result=diagnose_noise_file(spectral_input(workspace,request.input),job/'noise.json',
                                      request.channel_index,request.time_index)
            write_json(job/'summary.json',result)
        elif request.kind=='time_scatter':
            from vsora_correlator.time_scatter import diagnose_time_file
            from .noise import spectral_input
            phase('pilotの時間cellと仮定した雑音を確認しています')
            profile=None
            if request.rate_profile is not None:
                profile=Path(request.rate_profile)
                profile=profile if profile.is_absolute() else workspace/profile
                if profile.suffix.lower()!='.json' or not profile.is_file():raise ValueError('existing local JSON file required')
            result=diagnose_time_file(spectral_input(workspace,request.input),job/'time-scatter.json',request.channel_index,profile)
            write_json(job/'summary.json',result)
        elif request.kind=='sensitivity':
            from vsora_simulator.sensitivity import dish_area,sefd_from_area,write_plan
            phase('仮定した感度と短積分のClosure情報を計算しています')
            area=dish_area(request.diameter_m,request.aperture_efficiency) if request.antenna_mode=='dish' else request.effective_area_m2
            sefd=sefd_from_area(request.system_temperature_k,area)
            simulation=SimulationRequest(model='casa',stations=request.stations,layout=request.layout,
                duration_s=14400,integration_s=120,flux_jy=request.flux_jy,sefd_jy=sefd)
            result=write_plan(simulation_config(simulation),job/'sensitivity',integration_s=request.integration_s,bandwidth_hz=request.bandwidth_hz)
            result['antenna_assumptions']={'effective_area_m2':area,'system_temperature_k':request.system_temperature_k,
                'mode':request.antenna_mode,'diameter_m':request.diameter_m if request.antenna_mode=='dish' else None,
                'aperture_efficiency':request.aperture_efficiency if request.antenna_mode=='dish' else None}
            write_json(job/'summary.json',result)
        elif request.kind=='synthesis':
            from vsora_imaging.synthesis import image_synthesis
            phase('別時刻の短積分を確認してClosure＋RMLで合成しています')
            paths=[(Path(value) if Path(value).is_absolute() else workspace/value).resolve() for value in request.inputs]
            if any(path.suffix.lower()!='.npz' or not path.is_file() for path in paths):raise ValueError('existing spectral NPZ inputs required')
            options=request.model_dump(exclude={'kind','inputs'})
            result=image_synthesis(paths,job/'synthesis',**options)
            write_json(job/'summary.json',result)
        else:
            phase('検証を実行しています')
            runner=workspace/'tools/run.py'
            if not runner.is_file(): raise ValueError('validation requires project checkout')
            modules={'bispectrum':'workflows.bispectrum_distinct_validation','filtered_noise':'workflows.filtered_noise_validation','closure_noise':'workflows.closure_noise_validation','covariance':'workflows.rate_covariance_validation','uncertainty':'workflows.rate_uncertainty_validation','phase':'workflows.periodic_phase_validation','rate':'workflows.closure_rate_validation','closure':'workflows.closure_validation','quality':'workflows.spectral_quality_validation','clock':'workflows.clock_validation','fringe':'workflows.iq_fringe'}
            if request.validation=='basic':
                subprocess.run([sys.executable,str(runner),'pytest','-q'],cwd=workspace,check=True)
                write_json(job/'summary.json',{'type':'validation','validation':'basic','status':'passed',
                                                'description':'See execution.log for counts and warnings'})
            else:
                subprocess.run([sys.executable,str(runner),modules[request.validation],'--output',str(job/'validation')],
                               cwd=workspace,check=True)
                summary=job/'validation/summary.json'
                if summary.exists(): write_json(job/'summary.json',json.loads(summary.read_text()))
        phase('結果を保存しています',status['total_steps'])
        status.update(state='complete',phase='処理完了');write_json(job/'status.json',status)
    except Exception as exc:
        message=str(exc)
        failure_file=job/'analysis.partial/failure.json' if request.kind=='analysis' else None
        if request.kind=='sequence' and (job/'sequence.partial/failure.json').is_file():
            failure=json.loads((job/'sequence.partial/failure.json').read_text())
            status['sequence_failure']={'completed_window_count':len(failure['completed_windows']),
                'total_window_count':len(failure['planned_windows']),
                'current_window_index':failure['current_window_index'],'phase':failure['phase']}
            if failure['current_window_index'] is not None:
                failure_file=job/f"sequence.partial/window-{failure['current_window_index']:04d}.partial/failure.json"
        if failure_file is not None and failure_file.is_file():
            failure=json.loads(failure_file.read_text())
            if failure.get('rate_consistency'):
                status['rate_consistency']=failure['rate_consistency']
                try:plot_rate_parts(failure['rate_consistency'],job/'rate-parts.png')
                except Exception:status['diagnostic_plot_unavailable']=True
        translations={'integer channel index':'周波数の番号が入力の範囲外です。入力情報を読み直して選んでください。',
            'double-correct':'保存相関はrate補正済みです。追加profileを空欄にするか、補正前のpilotを選んでください。',
            'UTC origin differs':'相関とrate profileのUTC原点が一致しません。同じ観測のファイルを選んでください。',
            'station order differs':'相関とrate profileの局ID・順序または形式が一致しません。',
            'positive real integration':'正の時間露光が保存されていません。pilot相関の保存形式を確認してください。',
            'integer time/channel indices':'時刻または周波数の番号が入力の範囲外です。入力情報を読み直して選んでください。',
            '指定したWSL側の相関NPZ':'指定したWSL側の相関NPZが見つかりません。入力ファイルの場所を確認してください。',
            'input changed during diagnostic':'診断中に入力が変更されました。保存済みのファイルを固定して再実行してください。',
            'four verified subpilot':'線形モデルに必要な4部分の推定が揃いません。pilotの長さと感度を確認してください。',
            'inconsistent with a linear rate model':'分割rateが線形モデルと整合しません。pilotと積分を短くした比較、実機の位相変動を確認してください。',
            'curvature too large within subpilot':'各部分内の変動が大きすぎます。pilotの刻み・全長と積分を見直してください。',
            'outside supplied baseline rate bound':'線形モデルの端で基線周波数差が探索範囲を超えました。装置の初期差とpilot条件を確認してください。',
            'required subpilot rate consistency':'分割rateの整合を必須にしたため停止しました。変動検出または未判定の診断を確認し、pilotと積分の長さ・感度を見直してください。',
            'windows must not overlap':'区間の開始間隔がpilotより短くなっています。空欄で自動設定するか、間隔を広げてください。',
            'covered by each pilot':'画像積分全体を各pilotで覆ってください。pilotの積分数か一回の積分を調整してください。',
            'input ends':'必要な区間までVDIFがありません。開始時刻・区間数・間隔と記録時間を確認してください。',
            'beyond VDIF record':'指定した開始時刻がVDIFの記録範囲を超えています。',
            'input files changed':'処理中に入力ファイルが変更されました。収録済みの原本を固定して新しく実行してください。',
            'input identity changed':'区間の間で原本の識別情報が変わりました。入力を固定して新しく実行してください。',
            'one million spectral':'相関値の個数が参照実装の上限を超えます。区間数・pilot数かchannel数を減らしてください。',
            'disconnected':'周波数差を測れる基線が局間をつないでいません。pilotのSNRと局数を確認してください。',
            'extrapolation':('診断区間がrate profileの有効時間をはみ出しました。対応するpilotとprofileを選んでください。' if request.kind=='time_scatter' else '画像積分がpilotの有効時間をはみ出しました。短い積分か有効期間を覆うpilotを設定してください。'),
            'duplicate synthesis':'入力の観測時刻が重複しています。同じ露光を二度含めないよう入力を見直してください。',
            'overlapping synthesis':'入力の積分区間が重なっています。独立した短露光を選んでください。',
            'axes differ':'局・位置・天体・単位・周波数が一致しません。同じ処理条件のデータを選んでください。',
            'no high SNR':'SNR条件を満たす独立Closureがありません。感度・積分時間・局配置を確認してください。',
            '128 MiB':'直接Fourier行列が参照実装の128MiB上限を超えます。選ぶ短露光または画素数を減らしてください。',
            'existing local JSON':'指定したWSL側のJSONファイルが見つかりません。ファイルの場所を確認してください。',
            'existing spectral NPZ':'指定したWSL側のspectral NPZが見つかりません。ファイルの場所を確認してください。'}
        explanation=next((japanese for key,japanese in translations.items() if key in message),'詳細ログで入力条件と停止理由を確認してください。')
        status.update(state='cancelled' if isinstance(exc,InterruptedError) else 'failed',
                      phase='中止しました' if isinstance(exc,InterruptedError) else '処理に失敗しました',
                      error_type=type(exc).__name__,error_message=explanation)
        write_json(job/'status.json',status);raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);a=p.parse_args();run(Path(a.job))
