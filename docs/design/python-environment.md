# Python実行環境

Python 3.12以上。依存はルートのpyproject.tomlに定義。独立環境では `python -m pip install -e '.[dev]'` を用いる。

この開発では既存の科学計算環境を参照するローカル `.venv` を使用した。外部環境への参照パスはGit管理外であり、公開文書にユーザーの絶対パスを記載しない。既存プロジェクトのソースコードはコピーしていない。

検証時の版：Python 3.12.3、NumPy 2.5.1、SciPy 1.18.0、Astropy 7.2.2、Matplotlib 3.11.1、pytest 8.4.2。段階011で既存環境への参照を持たない新規`.verification-venv`を作り、21依存を固定したwheel導入・全52テスト・checkout外CLI実行を確認した。[固定版](../../requirements/verified-linux.txt)はLinux Python 3.12で確認。

```sh
# 新しい環境名で作る。既存環境を上書きしない。
python3 -m venv .verification-venv
.verification-venv/bin/pip install -r requirements/verified-linux.txt
.verification-venv/bin/pip wheel . --no-deps -w dist
.verification-venv/bin/pip install --no-deps dist/v_sora-0.1.0-py3-none-any.whl
.verification-venv/bin/python -m pytest -q
.verification-venv/bin/vsora-simulate --config configs/experiments/ideal-point.json --output outputs/point
.verification-venv/bin/vsora-image --input outputs/point/visibility.npz --output outputs/point-image
```

wheelには匿名化したCas A参照画像を含む。旧実装はcheckout内の相対位置から画像を探していたため、wheel導入先では見つからない構造だった。`vsora_observation.reference`がcheckoutまたはwheelのshare/v-sora/referenceを探す。ソースを変更した後はwheelを再構築・再導入するか、開発用に`python tools/run.py ...`を使う。

段階004でBaseband 4.3.0をローカル環境へ導入した。NumPy 2.5との組合せでshape代入のDeprecationWarningがあるが、量子化・時刻・相関のテストは成功した。

```sh
python tools/run.py pytest -q
python tools/audit_public.py
```

`tools/run.py` は各apps/packagesのsrcを読み込むため、editable installなしでもソースを実行できる。
