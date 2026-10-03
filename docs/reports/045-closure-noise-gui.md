# 段階045：Closure雑音検証の日本語GUI

- 作成日：2026-10-03
- 状態：完了（既知の模擬共分散・日本語GUIの検証範囲）
- 比較元コミット：460f240

## 読者向け概要

天体自身の共有雑音がClosureにどう残るかを、動作検証から再実行します。電圧を作って相関する方式と、相関値へGaussian雑音を加える近似方式を区別して表示します。

## 1. 目的・対象範囲

段階044の8条件×16384試行をGUIへ接続し、一次近似と標本の差、独立円対称雑音の式との違いを読み分ける日本語画面を作ります。

## 2. 完了条件

実API・installed GUI・Chromiumで8行の数値と説明を確認し、日本語font・390px幅・JS/外部requestを検証すること。source/wheel全回帰、レポート・索引・匿名コミットを完成させること。

## 3. 実際に行った作業

- `models.py`、`jobs.py`、`worker.py`、`static/index.html`：段階044の自己完結したClosure共有雑音検証を動作検証メニューへ接続。
- `static/app.js`：4モデル×2生成方式の表。既知の平均SNR、標本分散／一次近似分散、一次近似／独立円対称式の分散比を表示。Gaussian visibility近似とGaussian電圧の標本相関を区別し、phase/log amplitude交差共分散を詳しい数値に保存する説明を追加。
- `apps/ui/tests/test_server.py`：実APIから各16384試行を実行し、観測値選別なし・2生成方式・production RML変更なし・図の取得を確認。
- `tools/verify_uncertainty_ui.py`：Closure雑音検証を選べるよう拡張し、installed GUIの8行の分散比と説明を実Chromiumで照合。
- `docs/guide/06-gui.md`：実行手順、一次近似・分散比・適用範囲を追記。

推定・補正・相関・RMLのアルゴリズムは段階044と同じです。検証workflowにはcheckoutが必要です。開発中の静的ファイルをすぐ配信しないよう、メインGUIの起動をインストール済み版へ切り替えました。

## 4. 検証条件・結果

### 実API・配布版GUI・実Chromium

対象API検証1件成功、6.65秒、警告1件（Starlette deprecation）。installed GUIを独立した一時workspaceで起動し、メニューから8条件×16384試行を実行しました。各行の2種類の分散比の最小〜最大がsummaryと一致し、既知共分散・2生成方式・観測値選別なし・phase/log amplitudeの交差共分散・RML変更なしの説明を確認しました。

Chromium153.0.8010.12、日本語font成功、JavaScript error0・外部request0。390px幅で横はみ出しなし。Windowsブラウザ・WSLgは未検証です。[ブラウザ記録](../../validation/runs/stage045/browser.json)、[小画面](../../validation/runs/stage045/closure-noise-gui.png)を保存しました。

メインlocalhost:8765は実行中ジョブ0を確認して配布版へ更新し、environment APIの応答を確認しました。console launcherの停止指定が実際のargvと合わず、最初の再起動はport使用中で失敗しました。実際のargvを確認して本タスクの旧サーバーだけを停止し、`python -m vsora_ui`で再起動して解消しました。科学計算や履歴への影響はありません。

### 全回帰・配布

- source全回帰298件成功、警告22672件、448.31秒。
- installed全回帰298件成功、警告22672件、428.10秒。
- source、実ブラウザ、installed全回帰を順番に実行。pip check成功。既存のBaseband/NumPy・Starlette等のdeprecation警告を含みます。

sourceのcollection後に次段階046の新規試験を作成したため、installedではその未コミット試験だけを`--ignore=apps/simulator/tests/test_visibility_noise_estimate.py`で対象外にし、段階045の同じ298件を実行しました。段階045とそれ以前の試験は除外していません。段階046のAPIはこのwheelに含まれません。

wheel 5460256bytes、SHA256 `519a4576b7975ca46677b8da163f13bc8d1a758a53c089395202f9420e49cdd6`。[検証・識別情報](../../validation/runs/stage045/verification.json)を保存しました。完全ログ・wheel・完全画面はGit外`outputs/stage045-*/`です。

```bash
python tools/verify_uncertainty_ui.py --validation closure_noise --output outputs/new-closure-noise-gui
```

インストール済みv-sora、Playwright/Chromium、checkoutが必要です。

## 5. 制約・未解決事項

既知の模擬共分散と高SNRの一次近似です。実ADC/FIR/VDIF、実OCXO、Cas A画像の合格や実機の補正係数を作る検証ではありません。

## 6. 次段階

既知の真値を要求せず、標本から推定する雑音共分散の条件と偏りを検証します。
