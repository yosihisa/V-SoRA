# 段階058：三基線積の雑音と短積分の日本語GUI

- 作成日：2026-10-04
- 状態：完了（固定仮定の比較GUIの範囲）
- 比較元コミット：dfa588b

## 読者向け概要

三基線積の偏りを除いても、短い積分には雑音が残ります。天体なしの分散検証と、仮定した点源の短積分・間引き・反復数の比較を日本語画面へ接続しました。計算秒数を実際のCas Aの必要観測時間として扱わない条件を表示します。

## 1. 目的・対象範囲

段階057の5条件のゼロ源Gaussian検証と、32条件の点源比較を表示。1m円形開口の仮定に相当する8行を表示し、全32行も展開できます。

## 2. 完了条件

実worker、最終wheelの実Chromiumで5分散行・32仮定行をJSONと照合。日本語/390px/図/JS/外部通信/checkout依存、source/wheel全回帰、公開情報確認、レポート・匿名コミット。

## 3. 実際に行った作業

- `apps/ui/src/vsora_ui/models.py`、`jobs.py`、`worker.py`：`bispectrum_sensitivity`検証要求、日本語履歴名、段階057workflowの別process実行。
- `static/index.html`、`static/app.js`：検証選択、正確なゼロ源分散・反復分散比/MC SE、点源の積分/間引き/M/SEFD・一窓尺度・同条件窓数/秒、全32条件の展開、図と制約。
- `apps/ui/tests/test_server.py`、`tools/verify_uncertainty_ui.py`：実workerと最終wheelのブラウザ検証。
- [操作ガイド](../guide/06-gui.md)、索引、小容量記録。

## 4. 検証条件・結果

対象worker1件成功、警告1件、1.83秒。5分散条件・32仮定計算、未実機/天体あり分散未計算/未画像化flag、PNG保存を確認。

source540件成功、警告23952件、433.55秒。installed540件成功、警告23952件、428.75秒。試験除外なし、source→最終wheel実ブラウザ→installed全回帰の順。既存deprecation警告を含み、pip check成功。

Python3.12.3、Playwright1.63.0、Chromium153.0.8010.12、WSL headless。checkout外の独立workspaceで最終wheelのGUI/workerを起動し、実ブラウザから検証を実行しました。5行の分散/比/MC SE、参考8行と全32行の保持M・一窓尺度・窓数・条件付き秒を保存JSONと照合。全32行を実際に展開して確認し、画面は参考8行を表示する状態で保存しました。実機独立数未測定、天体ありの分散未計算、目標5は検出確率ではないという説明を確認。

GUI/workerはwheel由来、科学workflowはcheckoutの`tools/run.py`由来です。JSエラー0、外部通信0、日本語フォント成功、390pxで横はみ出しなし。desktop/mobile画面を目視確認済み。Windows/WSLg実ブラウザは未検証。常用localhost:8765は実行中ジョブがないことを確認して最終wheelへ再起動しました。

wheel5485300bytes、SHA256 `241ece5a3816115f046d4c0da1dbe3f3964c5b57ef731568fcc4b6a95b0168ba`。

[実ブラウザ記録](../../validation/runs/stage058/browser.json)、[表示画面](../../validation/runs/stage058/result.png)、[390px](../../validation/runs/stage058/mobile.png)、[回帰・wheel](../../validation/runs/stage058/verification.json)。完全ログ・wheelはGit外`outputs/stage058-*/`。

```bash
python tools/verify_uncertainty_ui.py --validation bispectrum_sensitivity --output outputs/new-bispectrum-sensitivity-ui
```

最終wheelのPython、checkout、Playwright・Chromiumが必要です。

## 5. 制約・未解決事項

ゼロ源分散と固定点源の尺度です。実機M/SEFD/時計、拡がったCas Aの相関flux、uv変化、天体ありの分散、検出確率、角度の信頼区間、画像復元は未確認。計算秒を実際の必要観測時間として採用できません。三基線積のRMLへの適用は未実施です。

## 6. 次段階

天体信号があるGaussianモデルでU₃の雑音共分散・擬共分散を検証し、ゼロ源尺度との違いと共有三角形の依存を整理します。
