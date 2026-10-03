from contextlib import asynccontextmanager
import json
from zipfile import BadZipFile
from pathlib import Path
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .jobs import JobManager
from .models import JobRequest,NoiseInputRequest


def create_app(workspace):
    manager=JobManager(workspace);static=Path(__file__).parent/'static'
    @asynccontextmanager
    async def lifespan(app):
        yield
        manager.close()
    app=FastAPI(title='V-SoRA local observer UI',lifespan=lifespan)
    app.state.jobs=manager
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1'])
    @app.middleware('http')
    async def local_requests(request:Request,call_next):
        if request.method in ('POST','PUT','DELETE'):
            origin=request.headers.get('origin')
            if request.headers.get('x-vsora-request')!='1' or (origin and origin!=str(request.base_url).rstrip('/')):
                return JSONResponse({'detail':'この画面から操作してください'},status_code=403)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'"
        return response

    @app.get('/')
    def home(): return FileResponse(static/'index.html')
    app.mount('/assets',StaticFiles(directory=static),name='assets')

    @app.get('/api/environment')
    def environment():
        return {'project':manager.workspace.name,'validation_available':(manager.workspace/'tools/run.py').is_file(),
                'frequency_hz':1.42e9,'sample_rate_hz':2048000,'max_baseline_m':600,
                'real_observation_verified':False}

    @app.post('/api/noise-input')
    def noise_input(request:NoiseInputRequest):
        from .noise import input_axes
        try:return input_axes(manager.workspace,request.input)
        except (ValueError,OSError,KeyError,EOFError,BadZipFile):
            raise HTTPException(400,'相関ファイルの読込に失敗しました。保存済みのspectral NPZを確認してください。') from None

    @app.get('/api/jobs')
    def jobs(): return manager.list()

    @app.post('/api/jobs',status_code=202)
    def submit(request:JobRequest):
        try: return manager.submit(request)
        except ValueError as e: raise HTTPException(400,str(e)) from None

    @app.get('/api/jobs/{job_id}')
    def detail(job_id:str):
        try:
            status=manager.status(job_id);directory=manager.directory(job_id)
            summary=directory/'summary.json'
            status['summary']=json.loads(summary.read_text()) if summary.exists() else None
            status['artifacts']=[{'path':str(p.relative_to(directory)),'bytes':p.stat().st_size}
                 for p in sorted(directory.rglob('*')) if p.is_file() and p.suffix in ('.png','.fits','.npz','.json','.npy','.log')]
            return status
        except FileNotFoundError: raise HTTPException(404,'実行が見つかりません') from None

    @app.post('/api/jobs/{job_id}/cancel')
    def cancel(job_id:str):
        try: return manager.cancel(job_id)
        except FileNotFoundError: raise HTTPException(404,'実行が見つかりません') from None

    @app.get('/api/jobs/{job_id}/artifacts/{name:path}')
    def artifact(job_id:str,name:str):
        try:
            directory=manager.directory(job_id).resolve();path=(directory/name).resolve()
            if not path.is_relative_to(directory) or not path.is_file() or path.suffix not in ('.png','.fits','.npz','.json','.npy','.log'):
                raise FileNotFoundError
            return FileResponse(path,filename=None if path.suffix=='.png' else path.name)
        except FileNotFoundError: raise HTTPException(404,'ファイルが見つかりません') from None
    return app
