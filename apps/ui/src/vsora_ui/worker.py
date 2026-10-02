"""Fixed scientific operations run outside the web server process."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from .jobs import write_json
from .models import SimulationRequest,ValidationRequest


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
    raw=data['request'];request=SimulationRequest(**raw) if raw['kind']=='simulation' else ValidationRequest(**raw)
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
        else:
            phase('検証を実行しています')
            runner=workspace/'tools/run.py'
            if not runner.is_file(): raise ValueError('validation requires project checkout')
            modules={'quality':'workflows.spectral_quality_validation','clock':'workflows.clock_validation','fringe':'workflows.iq_fringe'}
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
        status.update(state='cancelled' if isinstance(exc,InterruptedError) else 'failed',
                      phase='中止しました' if isinstance(exc,InterruptedError) else '処理に失敗しました',error_type=type(exc).__name__)
        write_json(job/'status.json',status);raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);a=p.parse_args();run(Path(a.job))
