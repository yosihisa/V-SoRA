# 段階011：独立環境とwheel導入

- 作成日：2026-10-02
- 状態：完了（Linux Python 3.12）
- 比較元コミット：28a85d1

## この段階の読み方

開発機に偶然あるライブラリやファイルに依存していないかを確認しました。新しいPython環境へ配布パッケージを導入し、リポジトリ外からコマンドを動かしました。

専門用語は[用語集](../guide/glossary.md)、画像と誤差の意味は[結果の読み方](../guide/03-results.md)を参照してください。以下の数値・失敗・実行条件は当時の記録です。

## 1. 目的・対象範囲

既存科学計算環境への参照を使わず、依存固定・wheel導入・checkout外CLI実行を確認する。数値結果の再現性と実行入口を整える。

## 2. 完了条件

新規venvへ固定依存とwheelを導入して全テスト成功。参照画像がwheelに含まれ、Cas Aシミュレーターと画像CLIを別cwdから実行可能。pip check成功。機械固有pathを公開保存しない。

## 3. 実際に行った作業

- `requirements/verified-linux.txt`：科学計算・検証依存21個の実使用版を固定。`tools/freeze_science.py`でdependency closureを取得。
- `pyproject.toml`：vsora-simulate/image/correlate entrypointと、匿名化した科学参照画像のwheel dataを追加。
- `vsora_observation/reference.py`：checkoutまたはインストール先shareから参照画像を取得。source-treeの位置に依存した旧構造を修正。
- `.verification-venv`を作成。既存venvやOSのPythonは変更していない。
- `tools/verify_installed.py`：wheel由来import/assetを確認し、checkout外でentrypointを実行。ログ・wheelはGit管理外。
- `docs/design/python-environment.md`：独立導入の再実行方法を追記。

## 4. 検証条件・結果

```sh
python3 -m venv .verification-venv
.verification-venv/bin/pip install -r requirements/verified-linux.txt
.verification-venv/bin/pip wheel . --no-deps -w outputs/wheels
.verification-venv/bin/pip install --no-deps outputs/wheels/v_sora-0.1.0-py3-none-any.whl
.verification-venv/bin/python -m pytest -q
.verification-venv/bin/python tools/verify_installed.py --output outputs/wheel-smoke
```

Python3.12.3、NumPy2.5.1、SciPy1.18.0、Astropy7.2.2、Matplotlib3.11.1、Baseband4.3.0、pytest8.4.2。**installed wheelに対して52件成功**、既知Baseband warning553件。pip check成功。

参照画像SHA256 `cb9ef1efbcd4011bcfd8ea9b6b9553f36005d08f8c9d26a65439b45e18130663` は導入先のassetから確認。checkout外でCas A simulate/image実行とcorrelator help成功。

このsmokeは4局・10時刻の疎な配置を使う。CLEANは収束したがmodel fluxは-6.67 Jy、peak56.37 Jy/beamであり、**画像忠実度の合格を意味しない**。欠けた短基線等によりこの入力でCas A形状・総fluxを回収できない。配置を含む科学評価は段階003の別条件で行った。

詳細：[summary](../../validation/runs/stage011/summary.json)。導入・buildログはローカル`outputs/stage011-environment`に保存し公開していない。

## 5. 制約・未解決事項

- Linux/Python3.12の固定版を確認。別OS・Python版、Windows収録、GPU backendは未検証。
- hash付きdependency lockやオフラインwheelhouseの配布は未実装。固定requirementsは版固定であり、将来の取得可能性を保証しない。
- Cas A参照は古いL-band画像のshape。1.42 GHz実測値ではない。
- Baseband/NumPyのDeprecationWarningが残る。現テストでは失敗しないが将来版更新時は再確認が必要。
- wheelへ導入したソースは変更後に再buildが必要。以後の開発では独立venv＋tools/run.pyを使って最新版を検証する。

## 6. 次段階

Cas Aの分解されたshapeを較正モデルにできるよう拡張し、点源仮定による誤較正を避ける。未知局応答を含むCas A IQから画像までの検証を進める。
