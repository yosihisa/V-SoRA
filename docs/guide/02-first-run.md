# Ubuntuで最初の模擬観測を試す

## 1. Python環境を用意する

リポジトリの最上位で実行します。Python3.12以上を使います。以下の`.user-venv`は新しい環境名の例です。既存の開発環境があれば、そのPythonを使えます。

```sh
python3 -m venv .user-venv
.user-venv/bin/pip install -r requirements/verified-linux.txt
.user-venv/bin/pip install --no-deps -e .
```

依存ライブラリの検証済み版を固定してから、V-SoRAを導入しています。詳しくは[実行環境](../design/python-environment.md)を参照してください。生成結果は`outputs/`に置き、ソースや文書と混ぜません。

## 2. まず点源で確認する

点源は「一つの画素に全fluxを置いた天体」です。複雑な形状より、位置・振幅・符号の誤りを見つけやすいため最初に使います。

```sh
.user-venv/bin/vsora-simulate --config configs/experiments/ideal-point.json --output outputs/my-point
.user-venv/bin/vsora-image --input outputs/my-point/visibility.npz --output outputs/my-point-image
```

この例は理想visibilityを直接生成します。VDIFや実受信機は使いません。`outputs/my-point-image/images.png`にdirty画像・点源応答・CLEAN成分・復元画像が並びます。`summary.json`には停止条件や推定fluxがあります。

同じoutputへ再実行すると、上書きを避けるため失敗します。`my-point-2`など新しい名前を選んでください。

## 3. Cas Aを模擬観測する

最初の設定をコピーし、`source.model`を`casa`に変更します。既存のL-band画像を形状の材料として使う設定です。`total_flux_jy=1000`は仮定する明るさで、実測値ではありません。

```sh
cp configs/experiments/ideal-point.json outputs/my-casa.json
```

エディタで設定を変更した後に実行します。

```sh
.user-venv/bin/vsora-simulate --config outputs/my-casa.json --output outputs/my-casa
.user-venv/bin/vsora-image --input outputs/my-casa/visibility.npz --clean-radius-arcsec 220 --output outputs/my-casa-image
```

4局・短時間の標準設定はCas Aの細部を十分に測れません。画像が一致しないこと自体が必ずしもプログラムの故障ではありません。局数・配置・観測時間を変えた比較は[段階003](../reports/003-casa-array-study.md)にあります。

## 4. 検証を再実行する

以下は開発者・検証担当向けです。checkout内の現在のソースを使います。

```sh
.user-venv/bin/pip install pytest
.user-venv/bin/python tools/run.py pytest -q
.user-venv/bin/python tools/run.py workflows.spectral_quality_validation --output outputs/my-quality
```

pytestは小さい自動試験をまとめて実行します。最後のコマンドは雑音と妨害を加えた模擬検証で、`summary.json`と`quality.png`を残します。passedはその試験条件を満たしたという意味で、実機すべての条件に対する保証ではありません。

## 5. WSLとファイル

大容量IQを処理する作業領域はWSLのLinux側ディスクを基準にします。WindowsのブラウザGUIからも、この作業領域の結果を見られる構成を次段階で追加します。現時点でWindowsの収録器を導入する必要はありません。
