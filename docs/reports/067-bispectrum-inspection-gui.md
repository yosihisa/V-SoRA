# 段階067：保存三次統計の日本語GUI

- 作成日：2026-10-05
- 状態：完了（保存値・入力照合・日本語GUIの範囲）
- 比較元コミット：`19fb653`

## 読者向け概要

保存した追加統計と元相関を選び、時刻・RFごとに三角形の値と状態を確認する画面です。元相関との照合と保存値の確認であり、雑音や画像の信頼度の推定は含みません。

## 1. 目的・対象範囲

WSL側の二つのNPZ、完了解析履歴、時刻/RF選択、三角形ごとの三局共通FFT数・実部/虚部・未計算/品質マスク/形式上利用可、JSON保存を日本語で提供します。軸を読んだ時の原本SHAをジョブにも渡し、選択後の入力の置換は再読込を求めます。

## 2. 完了条件

API/workerが段階066の値と完全一致。元相関不整合、読込中/選択後の変更、厳密な添字・SHAを検査。実Chromiumで保存済みVDIFの利用可とマスク、M0/1/2のnull、履歴選択、JSON、欠損/不整合エラー、日本語字体、390px、JS/外部通信0。source/wheel全回帰、個人情報監査、段階コミット。

## 3. 実際に行った作業

- `apps/ui/src/vsora_ui/raw_bispectrum.py`：閉じたrawと元相関の照合、時刻/RF軸、入力SHA、ジョブ実行時の選択原本の再確認。段階066のcell APIを使います。
- `models.py`、`server.py`、`jobs.py`、`worker.py`：厳密な添字/SHA、既存のlocalhost操作制約、ジョブ管理、停止理由の日本語化、有限JSON保存。
- `static/index.html`、`static/app.js`：専用の「保存三次統計」画面。完了した単一・区間列解析から二つのファイルを組で選択し、三角形の複素数と状態を表示します。
- `apps/ui/tests/test_raw_bispectrum_gui.py`：実workerを含む18件。
- `apps/correlator/tests/test_bispectrum_inspect.py`：関連する読込中の原本変更テストも、時刻が確実に変わる手順へ合わせました。
- `tools/verify_bispectrum_inspection_ui.py`：source版と導入版を区別した実Chromiumの検証。
- [GUI操作ガイド](../guide/06-gui.md)、[入力と結果の規約](../../interfaces/bispectrum-inspection.md)、段階レポート索引と小容量の実行記録。

表示値は指数表記で丸め、ダウンロードJSONは元の浮動小数点値を保持します。入力の編集で時刻/RF選択を無効にし、原本のSHAが選択後に変わればジョブを停止します。

## 4. 検証条件・結果

個別18件成功、2.01秒。実ジョブでM0/1/2/7、利用可・マスク・未計算、APIとJSONの全項目一致、入力の不変性、厳密な添字・SHA、欠損・不整合、読込中の変更、選択後の対応原本一式の置換を確認しました。

最初のsourceブラウザ検証は成功しました。保存済み段階064のVDIF相関の利用可cell（時刻0/channel10）とマスクcell（時刻1/channel16）、別に独立な合成スペクトルのM0/1/2を用意しました。M0/1/2はADC/FIR/VDIF経路ではなく、表示状態の確認用です。単一・区間列の履歴は閉じた相関を置いたfixtureで、新たな科学解析の成功例とは扱いません。

### 初回の全回帰で見つかったテスト条件の問題

初回sourceは760件成功・1件失敗、警告25596件、463.53秒でした。原本変更テストが読込後にtouchを行いましたが、ファイル時刻が同じままだと変更は観測できず、期待する例外が出ませんでした。単独8回は成功したため、失敗を隠す再実行では完了にしていません。

隔離した一時ファイル200回では、書込直後のtouchでmtime/ctimeが同じ例が199回ありました。ファイルシステムの時刻刻みを考慮し、テストはmtimeを明示的に1秒増やす方法へ変更しました。関連する段階066のテストも同じ手順に合わせました。本番の検査と合格条件を緩めていません。関連38件は1.81秒で成功しました。

### 最終検証

修正後のsource全回帰761件成功、警告25596件、462.10秒。導入済みwheelの実Chromiumも成功しました。リポジトリ外の独立workspace・PYTHONPATH除去で実行し、全行の局ID・FFT数・状態・実部/虚部を確認しました。JSONは段階066のAPIと全項目一致です。字体は同梱の日本語字体、JavaScriptエラー0、外部通信0、390pxの入力・結果とも横方向overflow0でした。

| 入力 | 時刻番号 / channel | 共通FFT数 | 状態 |
| --- | --- | --- | --- |
| 保存済み合成VDIF相関 | 0 / 10 | 2935、2935、3068、3067 | 形式上利用可 |
| 同じ保存相関のRFマスク | 1 / 16 | 全て3200 | 品質マスクで利用不可 |
| 合成スペクトルM0/1/2 | 0 / 1 | 各0、1、2 | U₃は未計算、null |

M0では通常の積もnullです。M1/2では通常の積は計算できてもU₃は未計算として表示します。二つの表示時刻へ同じ合成統計を配置した状態確認fixtureであり、時刻間独立性や実受信機を検証していません。

履歴の単一・区間列から二つの入力が組で選べること、入力編集で選択を無効にすること、不在・不整合原本の実HTTP400応答、JSONダウンロードも確認しました。図を目視し、PNGメタデータに個人情報がないことを確認しました。メインGUIでも新しい入力照合APIが2時刻・32channelを返しました。

[導入版ブラウザ記録](../../validation/runs/stage067/browser.json)、[sourceブラウザ記録](../../validation/runs/stage067/source-browser.json)、[初回失敗と修正記録](../../validation/runs/stage067/initial-failure.json)、[入力画面](../../validation/runs/stage067/input.png)、[利用可の表示](../../validation/runs/stage067/usable-result.png)、[マスクの表示](../../validation/runs/stage067/masked-result.png)、[共通FFTなし](../../validation/runs/stage067/no-common-fft.png)、[390px入力](../../validation/runs/stage067/mobile-input.png)、[390px結果](../../validation/runs/stage067/mobile-result.png)。

導入版全回帰761件成功、警告25596件、459.65秒。試験除外なし。Python3.12.3、NumPy2.5.1、SciPy1.18.0、Matplotlib3.11.1、FastAPI0.142.2、Pytest8.4.2、Playwright1.63.0、Chromium153.0.8010.12、WSL Ubuntu、BLAS/OMP各1thread。Windows/WSLgブラウザの実操作は未確認です。

wheel5502352bytes、SHA256 `3322bea2cca3d1a385d16843084eabed190a0c9b24d9ef8289f251921c0e938f`。配布物の全パッケージファイル70個がsourceと一致、pip check成功。[回帰・配布物記録](../../validation/runs/stage067/verification.json)。完全ログ・wheel・ブラウザの私的実行ログはGit外 `outputs/stage067-*/`。

文書リンク614個に不足0、公開前監査0件、差分の空白検査成功。公開JSONには一般化した入力名と数値・SHAだけを残し、PNGメタデータと画面を確認しました。公開用author/committerで段階コミットを行います。

```bash
python tools/run.py pytest -q apps/ui/tests/test_raw_bispectrum_gui.py apps/correlator/tests/test_bispectrum_inspect.py
PLAYWRIGHT_BROWSERS_PATH=/tmp/vsora-browser python tools/verify_bispectrum_inspection_ui.py --input validation/runs/stage064/raw-bispectrum.npz --source-visibility validation/runs/stage064/spectral-visibility.npz --output outputs/new-raw-inspection-ui
```

## 5. 制約・未解決事項

実FFT/品質選別の独立性、低SNRの尤度、未知gain正規化、実機、画像品質は未検証。現在のRMLに適用しません。

## 6. 次段階

保存経路を使い、低SNRと実FFTの依存性を検証します。まず既知Gaussian電圧モデルで短積分U₃の等重み平均を比較し、正確な共分散があってもGaussianの公称領域が妥当とは限らない点を調べます。RMLへの適用は別途判断します。
