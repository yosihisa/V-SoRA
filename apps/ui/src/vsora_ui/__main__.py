import argparse
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description='日本語のV-SoRA観測解析画面')
    p.add_argument('--workspace',default='.')
    p.add_argument('--port',type=int,default=8765)
    a=p.parse_args()
    if not 1024<=a.port<=65535: p.error('port must be 1024..65535')
    try:
        import uvicorn
        from .server import create_app
    except ImportError: p.error('GUI依存を導入してください: pip install -e ".[gui]"')
    print(f'Windowsのブラウザで http://localhost:{a.port} を開いてください',flush=True)
    uvicorn.run(create_app(Path(a.workspace)),host='127.0.0.1',port=a.port,log_level='warning')


if __name__=='__main__': main()
