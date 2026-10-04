# 段階060：三角形間の誤差相関を確認する日本語GUI

- 作成日：2026-10-04
- 状態：完了（既知モデル検証の日本語GUI）
- 比較元コミット：1bacde3

## 読者向け概要

段階059の既知モデル検証をGUIから実行し、天体信号による三基線積の分散増加と、複数の三角形が持つ誤差相関を比較します。

## 1. 目的・対象範囲

5条件×8192試行を日本語画面へ接続。標本数、分散比、実成分間の最大相関、全実共分散の比較量、固定6 MC SEの検証結果を表示します。観測共分散の推定やRMLの変更は対象外です。

## 2. 完了条件

実workerでworkflowと図を確認。source全回帰→wheel導入→実Chromiumで全5条件の表示値とモデルの制約をJSONと照合→installed全回帰。日本語font、390px表示、JSエラーと外部通信、図の目視、公開情報監査、段階レポートと匿名コミット。

## 3. 実際に行った作業

- `apps/ui/src/vsora_ui/models.py`、`jobs.py`、`worker.py`：検証種別`bispectrum_moments`を追加し、段階059のworkflowへ接続。
- `apps/ui/src/vsora_ui/static/index.html`、`app.js`：日本語の選択肢、5条件の比較表、既知S・完全共通信号・非Gaussian尤度の未確認範囲を表示。
- `apps/ui/tests/test_server.py`：実workerを起動する回帰を追加。
- `tools/verify_uncertainty_ui.py`：導入済みGUIの実Chromium検証で全5条件の表示値をJSONと照合。
- [GUIガイド](../guide/06-gui.md)、索引、小容量記録。

## 4. 検証条件・結果

対象の実worker試験1件成功、1.21秒、既存deprecation警告1件。5条件×8192試行、全実共分散の8×8行列、固定6 MC SE基準、図の取得を確認しました。

初回ソース回帰572件成功（424.66秒）の後、導入版の実ブラウザでも表の全数値は一致しました。目視で図の説明に一般の「画像復元の比較」が使われていることを発見し、三基線積の分散・相関・共分散比較へ修正しました。進行中の旧wheelのinstalled回帰は中断し、最終ソース／wheel／実ブラウザ／installed回帰を再実行しました。中断した回帰は成功として数えません。

最終source572件成功、警告23952件、427.05秒。最終installed572件成功、警告23952件、424.86秒。試験除外なし、source→installed実ブラウザ→installed全回帰の順、既存deprecation警告を含み、pip check成功。Python3.12.3、NumPy2.5.1、SciPy1.18.0、Matplotlib3.11.1、Pytest8.4.2、Playwright1.63.0、Chromium153.0.8010.12、WSL Ubuntu。

実Chromiumで全5条件のM・試行数・分散比範囲・最大相関・最大標準化差をJSONと照合し、固定6 MC SEとモデルの制約文、図の説明も確認しました。日本語font読込、390px幅で横overflowなし、JSエラー0、外部通信0。最終のdesktop/mobile図を目視確認しました。GUI/workerは導入済みwheel、workflowと`tools/run.py`はcheckout所有のコードを独立workspaceから参照します。Windowsブラウザ／WSLgは今回未検証です。

wheel5488087bytes、SHA256 `b22b4d16075231bd5aaac3dbf15115fb1659c69d622de0d754f9e1ef118bbb4b`。通常GUIは実行中ジョブ0を確認し、最終導入版へ更新しました。

[ブラウザ記録](../../validation/runs/stage060/browser.json)、[desktop](../../validation/runs/stage060/result.png)、[mobile](../../validation/runs/stage060/mobile.png)、[回帰とwheel](../../validation/runs/stage060/verification.json)。完全ログ・wheelはGit外`outputs/stage060-*/`。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PLAYWRIGHT_BROWSERS_PATH=/tmp/vsora-browser python tools/verify_uncertainty_ui.py --output outputs/new-bispectrum-moments-gui --validation bispectrum_moments
```

## 5. 制約・未解決事項

既知S・独立proper Gaussian電圧の検証です。実FFT独立性、非GaussianなU₃尤度、実機と画像の信頼度は未確認です。

## 6. 次段階

三次統計の追加の和を、FFT標本から少ないメモリで蓄積する機能を検証します。
