"""Serial subprocess jobs, persistent state and cancellation."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
from uuid import uuid4


ACTIVE={'queued','running'}
LABELS={'simulation':'模擬観測と画像復元','quality':'雑音・電波妨害の検証',
        'clock':'時計ずれの検証','fringe':'位相回転と再相関の検証','basic':'基本動作の自動試験'}


def write_json(path,data):
    temporary=path.with_name(path.name+'.'+uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(path)


def source_root():
    root=Path(__file__).resolve().parents[4]
    return root if (root/'pyproject.toml').is_file() and (root/'tools/run.py').is_file() else None


class JobManager:
    def __init__(self,workspace):
        self.workspace=Path(workspace).resolve();self.root=self.workspace/'outputs/gui'
        self.root.mkdir(parents=True,exist_ok=True)
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='vsora-job')
        self.lock=threading.RLock();self.processes={};self.futures={};self.closed=False
        for path in self.root.glob('*/status.json'):
            try:
                data=json.loads(path.read_text())
                if data.get('state') in ACTIVE:
                    data.update(state='interrupted',phase='前回の処理は中断されました');write_json(path,data)
            except (ValueError,OSError): pass

    def directory(self,job_id):
        if not re.fullmatch(r'[0-9]{8}T[0-9]{6}-[a-f0-9]{8}',job_id): raise FileNotFoundError('job unavailable')
        path=self.root/job_id
        if not path.is_dir(): raise FileNotFoundError('job unavailable')
        return path

    def status(self,job_id): return json.loads((self.directory(job_id)/'status.json').read_text())

    def list(self):
        result=[]
        for path in sorted(self.root.glob('*/status.json'),reverse=True):
            try: result.append(json.loads(path.read_text()))
            except (ValueError,OSError): pass
            if len(result)>=100: break
        return result

    def submit(self,request):
        with self.lock:
            if self.closed: raise ValueError('server is closing')
            if sum(r['state'] in ACTIVE for r in self.list())>=8:
                raise ValueError('実行待ちは8件までです。終了してから追加してください')
            stamp=datetime.now(timezone.utc)
            job_id=stamp.strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:8]
            directory=self.root/job_id;directory.mkdir()
            payload={'schema_version':1,'workspace':str(self.workspace),'request':request.model_dump()}
            write_json(directory/'request.json',payload)
            label=LABELS['simulation'] if request.kind=='simulation' else LABELS[request.validation]
            status={'id':job_id,'label':label,'kind':request.kind,'state':'queued','phase':'実行待ち',
                    'created_utc':stamp.isoformat(),'completed_steps':0,'total_steps':2 if request.kind=='simulation' else 1}
            write_json(directory/'status.json',status)
            self.futures[job_id]=self.executor.submit(self._run,job_id)
            return status

    def _run(self,job_id):
        directory=self.directory(job_id);path=directory/'status.json'
        with self.lock:
            if (directory/'cancel').exists() or self.closed: return
            data=self.status(job_id);data.update(state='running',phase='処理を開始しています');write_json(path,data)
            env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONUNBUFFERED='1')
            repo=source_root()
            if repo:
                roots=[repo,*sorted(repo.glob('apps/*/src')),*sorted(repo.glob('packages/*/src'))]
                env['PYTHONPATH']=os.pathsep.join(map(str,roots))+(os.pathsep+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
            try:
                log=(directory/'execution.log').open('w')
                process=subprocess.Popen([sys.executable,'-m','vsora_ui.worker','--job',str(directory)],
                        cwd=self.workspace,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            except Exception as exc:
                data.update(state='failed',phase='処理を開始できませんでした',error_type=type(exc).__name__);write_json(path,data)
                if 'log' in locals(): log.close()
                return
            self.processes[job_id]=process
        code=process.wait();log.close()
        with self.lock:
            self.processes.pop(job_id,None);data=self.status(job_id)
            if (directory/'cancel').exists(): data.update(state='cancelled',phase='中止しました')
            elif code!=0 and data['state'] not in ('failed','interrupted'):
                data.update(state='failed',phase='処理に失敗しました',exit_code=code)
            elif code==0 and data['state']!='complete': data.update(state='failed',phase='完了記録を確認できませんでした')
            write_json(path,data)

    def cancel(self,job_id):
        with self.lock:
            directory=self.directory(job_id);data=self.status(job_id)
            if data['state'] not in ACTIVE: return data
            (directory/'cancel').touch()
            process=self.processes.get(job_id)
            if process and process.poll() is None:
                try: os.killpg(process.pid,signal.SIGTERM)
                except ProcessLookupError: pass
            future=self.futures.get(job_id)
            if future: future.cancel()
            data.update(state='cancelled',phase='中止しました');write_json(directory/'status.json',data)
            return data

    def close(self):
        with self.lock:
            self.closed=True
            for job_id in list(self.futures):
                if self.status(job_id)['state'] in ACTIVE: self.cancel(job_id)
        self.executor.shutdown(wait=True,cancel_futures=True)
