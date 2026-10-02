# Python実行環境

## 通常の導入

Ubuntu上のPython3.12以上を使います。以下はリポジトリ最上位から実行する例です。venvはプロジェクト専用のPython環境で、他のソフトの依存ライブラリと混ざることを防ぎます。

```sh
python3 -m venv .user-venv
.user-venv/bin/pip install -r requirements/verified-linux.txt
.user-venv/bin/pip install --no-deps -e .
```

`-e`はソース変更を反映する開発用導入です。[固定したライブラリ一覧](../../requirements/verified-linux.txt)はLinux/Python3.12で実際に導入確認しました。既存venvを上書きせず、必要なら新しい名前で作ってください。

## 実行と検証

```sh
.user-venv/bin/vsora-simulate --config configs/experiments/ideal-point.json --output outputs/point
.user-venv/bin/vsora-image --input outputs/point/visibility.npz --output outputs/point-image
.user-venv/bin/python tools/run.py pytest -q
```

`outputs/`は生成データの保存先で、Git管理外です。同じ出力先の上書きは拒否します。`tools/run.py`はcheckout内の現在のソースを選ぶ開発用の入口です。

## 配布用wheelの確認

wheelはPythonの配布用ファイルです。別の計算機へ渡したときにも、必要な参照画像とコマンドが揃うかを確認します。

```sh
.user-venv/bin/pip wheel . --no-deps -w dist
.user-venv/bin/pip install --force-reinstall --no-deps dist/v_sora-0.1.0-py3-none-any.whl
.user-venv/bin/python -m pytest -q
```

wheelには匿名化したCas A画像を含めます。ソース変更後はwheelも再構築する必要があります。開発中はeditable導入または`tools/run.py`を使うと、古いwheelを実行する取り違えを避けられます。

## 実際に使った環境と注意点

Python3.12.3、NumPy2.5.1、SciPy1.18.0、Astropy7.2.2、Matplotlib3.11.1、Baseband4.3.0、pytest8.4.2を確認しました。初期の`.venv`は既存科学計算環境を参照しましたが、段階011で独立した`.verification-venv`へ導入し直し、wheelとcheckout外の実行を確認しました。

BasebandとNumPyの組合せにはshape代入のDeprecationWarningがあります。これは将来使えなくなるAPIへの警告です。現在のテストは成功していますが、警告件数をレポートに残し、実際の失敗と区別します。

CASAは依存が大きいため別環境です。[CASA導入記録](casa-environment.md)を参照してください。
