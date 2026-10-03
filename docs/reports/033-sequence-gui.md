# 段階033：短区間列の日本語解析GUI

- 作成日：2026-10-03
- 状態：完了（模擬入力の操作確認。画像形状の復元合格とは別）
- 比較元コミット：0c6733a

## 読者向け概要

受信機ごとの発振周波数が違うと、局間の相関の位相が回り、長い積分で信号が弱くなります。同じ記録を短区間へ分けて各区間で周波数差を測り直す処理を、ブラウザの「区間列解析」へ接続しました。使った露光、測った周波数差、画像探索の停止を確認できます。

## 1. 目的・対象範囲

段階032の同一VDIFの短区間列を日本語で操作すること。入力、進捗、局周波数差の図、区間別条件、途中失敗、中止を扱います。WSLのローカルVDIFと時計JSONを使います。

## 2. 完了条件

- 実際の模擬VDIFの3区間をGUIで処理し、局周波数差・露光・相対fluxを確認。
- 短い記録による途中失敗と中止を、完了と区別。
- source、導入wheel、実Chromium、日本語font、狭い画面を確認。
- 個人情報・秘密情報を確認し、段階レポートとコミットを作成。

上記を実施しました。RMLの反復上限を収束成功には数えていません。

## 3. 実際に行った作業

- `apps/ui/src/vsora_ui/models.py`：区間列入力を追加。区間数2〜32、開始間隔は空欄でpilot全長を使います。NaN、無効数、未知キーを拒否。
- `jobs.py`・`worker.py`：3工程×区間数＋最終画像化の進捗、区間列処理、診断図、失敗した区間の情報と日本語説明。
- `static/index.html`・`app.js`・`style.css`：日本語画面、予定画像露光と基線の有効露光、区間別の周波数差・Nyquist・SK判定可能率、停止位置の表。
- `sequence.py`：合成後の相関値が100万個を超える入力を、各区間の処理前に拒否。
- `apps/ui/tests/test_server.py`・`apps/correlator/tests/test_sequence.py`：実子プロセス、途中入力不足、重なるpilot、数値上限を検証。
- `tools/verify_sequence_ui.py`：導入済みwheelを、独立した一時作業フォルダでブラウザ操作する検証。
- [GUI手順](../guide/06-gui.md)を更新。

周波数差の図は測った時刻の点だけを表示します。点を結んで区間間を補間しません。基準局の値0は相対値の約束であり、共通の周波数ずれを測った値ではありません。既存GUIのactive jobが0であることを確認して、今回起動したサーバーを更新しました。

## 4. 検証条件・結果

### 数値処理と配布

Python 3.12.3、NumPy 2.5.1、SciPy 1.18.0、Astropy 7.2.2、Baseband 4.3.0。GUIはFastAPI 0.142.2、Uvicorn 0.54.0、HTTPx 0.28.1、Playwright 1.63.0、Chromium 153.0.8010.12です。CPUのBLAS thread数を1としました。

| 検証 | 実行結果 |
| --- | --- |
| source全試験 | 169成功、118.28秒 |
| wheel導入後の全試験 | 169成功、120.85秒 |
| 依存関係 | pip check問題なし |
| 既知の警告 | 各13248件。BasebandのNumPy配列shape変更とStarlette TestClientの非推奨。未修正 |
| ブラウザ | 完了・入力不足・実行中中止を操作。JS例外0、外部request0 |
| 390px幅 | 入力・結果とも横overflowなし。日本語font読込確認 |

全試験は `python tools/run.py pytest -q` と、導入後の `python -m pytest -q` で実行しました。ブラウザは次で再実行できます。出力先は新しい場所を指定します。

```sh
PLAYWRIGHT_BROWSERS_PATH=/tmp/vsora-browser .verification-venv/bin/python tools/verify_sequence_ui.py \
  --output outputs/sequence-ui-new \
  --manifest outputs/stage032-sequence-final/input/manifest.json \
  --clock-model outputs/stage032-sequence-final/input/clock.json \
  --short-manifest outputs/stage023-vdif-closure/input/manifest.json \
  --short-clock outputs/stage023-vdif-closure/input/clock.json
```

### 3区間の模擬観測

段階032の4局・1.6秒の点源＋受信機雑音VDIFを再利用しました。1.42GHz、2.048Msample/s、各pilotは2ms×256＝0.512秒、開始は0.002、0.514、1.026秒です。局周波数差はpilot境界で変え、位相を連続にしています。各画像積分0.3秒、3区間の予定露光は0.9秒、欠損を除いた各基線の露光も約0.9秒でした。

生成時の局差との最大誤差は区間順に0.01587、0.01834、0.00769Hz。独立Closureはphase117、log amplitude78です。RMLは一初期値・100反復で、Closure χ²/測定数0.7412、総相対flux1、入力ADC²でした。選択探索は100反復の上限に達し、GUIにも「反復上限等を確認」と表示しました。短い記録の試験では区間1のみ完了し、区間2で入力不足として停止、区間1の相関値を保存しました。中止試験は実行中の子プロセスを止めた有限の一条件です。

詳細は [ブラウザ・数値記録](../../validation/runs/stage033/summary.json)、[検証とwheel識別](../../validation/runs/stage033/verification.json)にあります。[完了画面](../../validation/runs/stage033/sequence-result.png)、[停止画面](../../validation/runs/stage033/sequence-failed.png)、[狭い画面](../../validation/runs/stage033/sequence-mobile.png)を保存しました。

## 5. 制約・未解決事項

- 点源の処理経路を確認した検証です。Cas A形状の良好復元や実OCXOの安定性を確認した試験ではありません。
- 各pilot内の局周波数差・gain・skyは一定と仮定。入力した線形sample時計モデルを使います。区間内の非線形な位相変動は未対応。
- 時間Nyquistを超える初期差は別値へ折り返す可能性があります。図に見えた値だけで初期差の上限を実測した扱いにしません。
- 原本SHAは区間ごとに全体を再読取します。未読prefixのheader検査は別で、原本SHA確認だけではVDIFの構造全体を検査したことにはなりません。
- 中止・失敗からの自動再開は未対応。条件を変えて新しい実行を作ります。Windows browserとWSLg desktopは直接確認していません。
- 画像は総相対flux1で、絶対Jyや絶対位置を測りません。プログラムの処理完了、最適化の停止、天体形状の正しさは区別します。

## 6. 次段階

区間列の原本SHAを安全に共有して大きい記録の繰り返し読取を減らすこと。続いて区間内の局周波数変動と低SNRの影響を検証します。
