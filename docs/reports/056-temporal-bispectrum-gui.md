# 段階056：時間相関と三基線積の日本語GUI

- 作成日：2026-10-04
- 状態：完了（既知雑音モデルの検証GUIの範囲）
- 比較元コミット：d479483

## 読者向け概要

近くの電圧標本に時間相関があると、標本番号を変えても三基線の積に雑音の偏りが残る場合があります。段階055の5条件を日本語画面で比較し、偏りを避けるために間引くと保持数が減ることも表示します。

## 1. 目的・対象範囲

時間相関の既知モデル検証をGUIへ接続。白色・長い平均・基準FFT・各間引きの条件、モデル平均・反復平均/MC SE、保持数、仮定を表示します。

## 2. 完了条件

実workerで5条件・図保存。最終wheelの実Chromiumで全行数値・モデル残留偏り・保持数・日本語/390px/JS/外部通信/checkout依存を確認。source/wheel全回帰・公開情報確認・レポート・匿名コミットを完成させること。

## 3. 実際に行った作業

- `apps/ui/src/vsora_ui/models.py`、`jobs.py`、`worker.py`：`temporal_bispectrum`の検証要求、日本語履歴名、段階055workflowの別process実行。
- `static/index.html`、`static/app.js`：5条件の三基線積表、保持数・間引き間隔、既知モデルの共分散、通常積/U₃理論平均、U₃反復平均/実虚MC SE、固定6SE基準、モデル偏りの分解可否、図と条件。
- `apps/ui/tests/test_server.py`、`tools/verify_uncertainty_ui.py`：実workerと最終wheelの実ブラウザ確認。
- [操作ガイド](../guide/06-gui.md)、索引、小容量記録。

## 4. 検証条件・結果

対象worker1件成功、警告1件、1.53秒。5条件×8192試行、モデル平均との固定基準、長い平均の残留偏り、平均の間引き後15保持、PNG保存を確認。

source512件成功、警告23952件、423.46秒。installed512件成功、警告23952件、425.01秒。試験除外なし、source→最終wheel実ブラウザ→installed全回帰の順、既存deprecation警告を含み、pip check成功。

Python3.12.3、Playwright1.63.0、Chromium153.0.8010.12、WSL headless。checkout外の独立workspaceで最終wheelのGUI/workerを起動し、実ブラウザから検証を実行。全5行の通常積/U₃モデル平均、反復平均/SE、保持数/間隔をJSONと照合。長い平均のモデル偏りは分解、基準FFTの極小偏りは未分解と表示する条件を確認。実機独立数の測定結果や一律の間引き推奨と扱わない説明を確認。

科学workflowはcheckoutの`tools/run.py`で実行しています。GUI/workerがwheel由来であることと、workflowがcheckout由来であることを区別します。JSエラー0、外部通信0、日本語フォント成功、390pxで横はみ出しなし。desktop/mobile画面は目視確認済み。Windows/WSLgの実ブラウザは未検証です。常用localhost:8765は実行中ジョブがないことを確認して最終wheelへ再起動しました。

wheel5482383bytes、SHA256 `389e6db884060d15fa9bb46ecd6b38e4317a80e6198cdfa1e7044b1e43e9e89e`。

[実ブラウザ記録](../../validation/runs/stage056/browser.json)、[表示画面](../../validation/runs/stage056/result.png)、[390px](../../validation/runs/stage056/mobile.png)、[回帰・wheel](../../validation/runs/stage056/verification.json)。完全ログ・wheelはGit外`outputs/stage056-*/`。

```bash
python tools/verify_uncertainty_ui.py --validation temporal_bispectrum --output outputs/new-temporal-ui
```

最終wheelを導入したPython、checkout、PlaywrightとChromiumが必要です。

## 5. 制約・未解決事項

天体ゼロ・局間雑音独立・既知Gaussian時間共分散を仮定しています。実ADC/VDIF/raw畳み込み・未知共分散推定・実機独立性・感度・画像は未確認。既知モデルの極小偏りは今回の試行数で分解できません。MC SEは未知観測の検出確率や信頼区間ではありません。現行相関器とRMLの統計・重み・採否は変更していません。

## 6. 次段階

短積分における三基線積の雑音の大きさを、ゼロ源モデルと既知の相関係数から検討し、保持標本数を減らす場合の感度条件を整理します。

今回の継続作業は5時間枠の残量9%・週間枠56%を確認したため、この段階の全検証と記録・コミットを完了して区切ります。次段階の感度計算は一時ファイルでの準備案までで、リポジトリへの実装・検証・コミットは未実施です。
