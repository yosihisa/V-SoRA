# 段階050：FFT雑音検証の日本語GUI

- 作成日：2026-10-04
- 状態：完了（既知モデルの検証GUIの範囲）
- 比較元コミット：3cf2f0f

## 読者向け概要

フィルターでFFT間の雑音が関係する場合を、既知のGaussian入力のモデルで確認します。日本語画面から6条件を比較でき、対角分散だけでは見えない基線間の共分散も表示します。モデルから求めた独立数の換算は、実際の受信機で測った値とは異なります。

## 1. 目的・対象範囲

段階049の6条件の検証を日本語GUIへ接続し、モデル換算数・局別係数・乱数標本との差・全共分散の構造差を確認できるようにします。

## 2. 完了条件

実workerと最終wheelの実ブラウザで6条件×8192試行、表示の数値、モデルの範囲、日本語・390px・外部通信/JSを確認。source/wheel全回帰、レポート、匿名コミットを完成させること。

## 3. 実際に行った作業

- `apps/ui/src/vsora_ui/models.py`、`jobs.py`、`worker.py`：`filtered_noise`検証の受付・日本語履歴名・段階049workflow呼出し。
- `static/index.html`、`static/app.js`：検証項目、6条件の表、理論分散倍率、モデル換算数、MC差、全共分散の構造差、図と仮定の説明。局別係数の場合に換算数を作らない。
- `apps/ui/tests/test_server.py`：別processの実workerで6条件の結果とPNG保存を確認。
- `tools/verify_uncertainty_ui.py`：実ブラウザのfiltered_noise経路、全行の数値とmodel-only表記を確認。画像待機はfunction形式へ統一し、製品CSPは変更していない。
- [GUI操作ガイド](../guide/06-gui.md)、レポート索引、小容量の検証記録を追加。

## 4. 検証条件・結果

対象の実worker試験1件成功、警告1件、15.52秒。6条件それぞれ8192試行、既知raw共分散・観測による選別なし、整数kernel例で対角倍率1でも全共分散差が0.2を超えること、図ダウンロードを確認しました。

source全回帰401件成功、警告23312件、420.42秒。installed全回帰401件成功、警告23312件、420.93秒。source→実ブラウザ→installed全回帰を順番に実施、試験除外なし。既存Baseband/NumPy・Starlette等のdeprecation警告を含みます。pip check成功。

Python3.12.3・Playwright1.63.0・Chromium153.0.8010.12、WSL headless。checkout外の独立workspaceで最終wheelのGUI/workerを起動し、実ブラウザで項目選択・実行・6行の表と図を確認しました。科学検証はcheckoutにある`tools/run.py`とworkflowを明示して使用しています。wheelだけで全workflowが配布された扱いにはしません。

JSエラー0、外部通信0、日本語フォント成功、390pxで横はみ出しなし。デスクトップ画像を目視確認しました。常用localhost:8765は実行中ジョブがないことを確認して最終wheelへ再起動し、39件の履歴を保持しました。ブラウザ検証のfixtureは独立workspaceです。

wheel5471849bytes、SHA256 `22712371f0f10ed692e3cf86e5ba71209ac2aa4726377ae5a1d8e9bde9b06686`。

[ブラウザ記録](../../validation/runs/stage050/browser.json)、[表示画面](../../validation/runs/stage050/result.png)、[390px画面](../../validation/runs/stage050/mobile.png)、[回帰・wheel識別](../../validation/runs/stage050/verification.json)を保存。完全ログ・wheelはGit外`outputs/stage050-*/`です。

```bash
python tools/verify_uncertainty_ui.py --validation filtered_noise --output outputs/new-filtered-noise-ui
```

最終wheelを導入したPython、checkout、Playwright・Chromiumが必要です。

## 5. 制約・未解決事項

入力の局共分散と線形係数が既知の模擬検証です。4条件は固定FIR/補間/FFT、2条件は雑音相関を説明する例示kernelです。実ADC・時間変化する時計・実機の信頼区間・Cas A画像は未確認。RMLの重み・採否は変更していません。Gaussian入力の仮定を、実機の独立性の確認へ読み替えません。

## 6. 次段階

保存pilotの時間変動を調べる診断を実装・検証し、rate部分整合でも高速位相変動を見逃す問題への追加情報を検討します。
