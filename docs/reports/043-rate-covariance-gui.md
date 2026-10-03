# 段階043：rate共分散検証の日本語GUI

- 作成日：2026-10-03
- 状態：完了（仮定雑音・日本語GUIの検証範囲）
- 比較元コミット：a97d83c

## 読者向け概要

rate推定の近似σが仮定した雑音でどこまで妥当か、動作検証メニューから再実行できるようにします。モデルが採用された割合と、採用例だけの誤差統計を区別して表示します。

## 1. 目的・対象範囲

段階042の8条件×1024試行をGUIへ接続し、公称95%誤差領域と実際の有限試行の割合を読み分ける日本語表を作ります。実観測や画像化の合否を決める機能ではありません。

## 2. 完了条件

実API・installed GUI・Chromiumから処理と説明を確認し、日本語font・390px幅・JS/外部requestを検証すること。source/wheel全回帰、レポート・索引・匿名コミットを完成させること。

## 3. 実際の作業

- `models.py`、`jobs.py`、`worker.py`、`static/index.html`：段階042の自己完結した共分散検証を動作検証メニューへ追加。
- `static/app.js`：8条件の採用数／全試行、採用例の誤差距離、公称95%領域内割合を日本語表で表示。σ・ρ、選別の影響、条件間のSNRが揃っていないことを数値の近くに説明。数値がない場合は「未評価」とする。
- `apps/ui/tests/test_server.py`：実APIから1024試行×8条件を実行し、選別後の統計・未採用例・図の取得を確認。
- `tools/verify_uncertainty_ui.py`：従来のGaussian計算と共分散実験を選べるようにし、installed GUI・独立workspace・実Chromiumで説明と各行の数値を確認。
- `docs/guide/06-gui.md`：実行手順と統計の読み方を追記。

検証workflowはcheckoutから実行します。GUIの配布wheelだけではcheckout側の検証を実行できません。推定・補正・相関・RMLのアルゴリズムは段階042と同じです。

## 4. 検証条件・結果

### 実API・配布版GUI・実Chromium

対象API検証1件成功、39.35秒、警告1件（Starlette deprecation）。配布版GUIを独立した一時workspaceで起動し、メニューから8条件×1024試行を再実行しました。表の8行の採用数と公称95%領域内割合がsummaryと一致すること、未採用を除いた統計の説明、実IQ・VDIF／実OCXOを使っていない説明、SNRが揃っていない説明を確認しました。

Chromium153.0.8010.12、日本語font成功、JavaScript error0・外部request0。390px幅で横はみ出しなし。Windowsブラウザ・WSLgは未検証です。メインlocalhost:8765は実行中ジョブ0を確認して更新し、environment APIの応答を確認しました。

[ブラウザ記録](../../validation/runs/stage043/browser.json)、[小画面](../../validation/runs/stage043/covariance.png)を保存しました。

### 全回帰・配布

- source全回帰270件成功、警告22672件、420.99秒。
- installed全回帰270件成功、警告22672件、420.02秒。
- source、実ブラウザ、installed全回帰を順番に実行。pip check成功。既存のBaseband/NumPy・Starlette等のdeprecation警告を含みます。

wheel 5457628bytes、SHA256 `446764662999f8cc2660d9b3874ba4da82c49571f41c9d3c2b34373776aac738`。[検証の識別情報](../../validation/runs/stage043/verification.json)を保存しました。大容量の各試行、完全なブラウザ画面、ログ、wheelはGit外の`outputs/stage043-*/`です。

```bash
python tools/verify_uncertainty_ui.py --validation covariance --output outputs/new-covariance-gui
```

インストール済みv-sora、Playwright/Chromium、checkoutが必要です。既存のGaussian計算検証は`--validation uncertainty`で再実行できます。

## 5. 制約・未解決事項

仮定した相関値雑音と選別後の統計です。実ADC/FIR/VDIF・Cas A画像・実OCXOの信頼区間は未検証です。実機へ使う経験的な補正係数をGUIで作りません。

## 6. 次段階

共有雑音がClosureの誤差評価へ与える影響を検証します。
