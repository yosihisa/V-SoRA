# Python実行環境

Python 3.12以上。依存はルートのpyproject.tomlに定義。独立環境では `python -m pip install -e '.[dev]'` を用いる。

この開発では既存の科学計算環境を参照するローカル `.venv` を使用した。外部環境への参照パスはGit管理外であり、公開文書にユーザーの絶対パスを記載しない。既存プロジェクトのソースコードはコピーしていない。

検証時の版：Python 3.12.3、NumPy 2.5.1、SciPy 1.18.0、Astropy 7.2.2、Matplotlib 3.11.1、pytest 8.4.2。別環境では同じ版を用いた再検証が望ましい。この段階ではクリーン環境からの依存インストールは未検証。

```sh
python tools/run.py pytest -q
python tools/audit_public.py
```

`tools/run.py` は各apps/packagesのsrcを読み込むため、editable installなしでもソースを実行できる。
