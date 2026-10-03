# 段階054：三次統計検証の日本語GUI

- 作成日：2026-10-04
- 状態：完了（既知Gaussianモデルの検証GUIの範囲）
- 比較元コミット：1122bec

## 読者向け概要

既知Gaussian電圧の三基線積について、普通の積の偏りと、異なる標本を使うU₃の平均を日本語画面で比較します。非常に弱い信号の真値が分解できないことも表示します。平均の偏りを除くことと、天体を検出して画像化できることを区別します。

## 1. 目的・対象範囲

段階053の5条件×16384試行を動作検証GUIへ接続。モデル・既知真値・通常積の理論偏り・U₃平均/MC SE・固定基準・未分解・図とJSONを表示します。

## 2. 完了条件

実workerで5条件・図保存を確認。最終wheelの実Chromiumで全行数値と未分解、checkout依存、日本語/390px/外部通信/JSを確認。source/wheel全回帰、レポート、匿名コミットを完成させること。

## 3. 実際に行った作業

- `apps/ui/src/vsora_ui/models.py`、`jobs.py`、`worker.py`：`bispectrum`検証要求・日本語履歴名・段階053workflowの別process呼出し。
- `static/index.html`、`static/app.js`：検証項目、5条件表、既知基線SNR・真値・偏り・U₃複素平均と実虚MC SE、固定6SE基準、既知真値の未分解、図と仮定の説明。
- `apps/ui/tests/test_server.py`、`tools/verify_uncertainty_ui.py`：実workerと最終wheelの実ブラウザ確認。
- [操作ガイド](../guide/06-gui.md)、索引、小容量記録。

## 4. 検証条件・結果

実worker対象1件成功、警告1件、1.12秒。5条件×16384試行、観測値による選別なし、全平均の理論整合、非常に弱い真値の未分解、PNG保存を確認しました。

source484件成功、警告23952件、423.85秒。installed484件成功、警告23952件、424.05秒。試験除外なし、source→実ブラウザ→installed全回帰の順。既存Baseband/NumPy・Starlette等のdeprecation警告を含み、pip check成功。

Python3.12.3・Playwright1.63.0・Chromium153.0.8010.12、WSL headless。checkout外の独立workspaceで最終wheelのGUI/workerを起動し、実ブラウザで選択・実行・5行の真値/偏り/U₃平均/SEを数値と照合。弱信号の未分解、角度・振幅の不偏性を保証しない説明、保存平均だけでは再構成できない説明を確認しました。

初回の共通ブラウザツールは、新しいworkflowの実機未検証flagの項目名へ未対応で停止しました。存在する実機flagを明示的に確認し、全てfalseであることを要求するようツールを修正して再実行成功しました。flagがない結果やtrueの結果は成功にしません。科学workflowはcheckoutの`tools/run.py`から実行しています。GUI/workerがwheel由来であることと、検証workflowがcheckout由来であることを区別します。

JSエラー0・外部通信0・日本語フォント成功、390pxで横はみ出しなし。図と画面を目視確認しました。Windows/WSLg実ブラウザは未検証です。常用localhost:8765は実行中ジョブがないことを確認して最終wheelへ再起動し、39件の履歴を保持しました。

wheel5480095bytes、SHA256 `58f9049ad10c36ade3c9d85fb09751b2f6b72dc958d1b43fc2d9d1f33c4445f6`。

[実ブラウザ記録](../../validation/runs/stage054/browser.json)、[表示画面](../../validation/runs/stage054/result.png)、[390px画面](../../validation/runs/stage054/mobile.png)、[回帰・wheel](../../validation/runs/stage054/verification.json)。完全ログ・wheelはGit外`outputs/stage054-*/`。

```bash
python tools/verify_uncertainty_ui.py --validation bispectrum --output outputs/new-bispectrum-ui
```

最終wheelを導入したPython、checkout、Playwright・Chromiumが必要です。

## 5. 制約・未解決事項

独立Gaussian電圧・一定gainの検証です。実FFTの独立性・実機感度・角度/振幅の不偏性・画像品質は未確認。MC SEは固定仮定の有限試行誤差で、未知観測の検出確率・信頼区間とは異なります。非常に弱い信号の感度不足は残ります。現行相関器/RMLの統計・採否には未適用です。

## 6. 次段階

時間相関が残るGaussian電圧で、異標本量の条件が崩れる例を調べ、既知の有限フィルターで標本を間引く場合の条件と感度の損失を確認します。
