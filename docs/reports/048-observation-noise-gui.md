# 段階048：相関ファイルの雑音診断GUI

- 作成日：2026-10-04
- 状態：完了（条件付き診断のGUI接続の範囲）
- 比較元コミット：acfc4c6

## 読者向け概要

相関ファイルに保存された局power・基線の複素相関・共通FFT数から、一つの時刻・RF周波数の雑音を条件付きで計算します。条件を入力するだけでなく、実際に保存された時刻と周波数を選んで診断できる日本語画面を追加しました。実機で雑音モデルが正しいと保証する画面ではありません。

## 1. 目的・対象範囲

段階047の診断を日本語GUIへ接続します。履歴・直接パスで相関NPZを選び、相対時刻・RFを読み、条件付き推定・未判定・無効を処理の完了と分けて表示します。

## 2. 完了条件

相関NPZの軸確認、実subprocess診断、旧ファイルの未判定、低SNRの無効Closure表示、入力不正・失敗を確認すること。最終wheelの実ブラウザで日本語・390px表示・外部通信・JSエラーを確認し、source/wheel全回帰、レポート、匿名コミットを完成させること。

## 3. 実際に行った作業

- `apps/ui/src/vsora_ui/models.py`、`jobs.py`：相関入力・整数の時刻/channel番号を受け付ける`noise`ジョブ。余分な引数、不正整数・boolを拒否。
- `apps/ui/src/vsora_ui/noise.py`、`server.py`：保存済みNPZの軸を読むAPI。入力の前後statを比較し、相対時刻・RF・UTC原点の有無・基線FFT数の保存有無を返す。未保存のUTC原点を仮定して補わない。
- `apps/ui/src/vsora_ui/worker.py`：別processで段階047の診断APIを呼び、JSONと履歴を保存。範囲外・入力なしの理由を日本語に翻訳。
- `static/index.html`、`static/app.js`：雑音診断メニュー、解析・区間列の履歴選択、軸読込、RF選択、状態と公称FFT数、基線SNR、Closureの一次近似σ。無効行を「未判定／—」と表示し、ゼロ誤差と扱わない。
- `apps/correlator/src/vsora_correlator/noise_diagnostics.py`：診断JSONへ基線・三角形・四角形の局番号を追加。相関・共分散の数値計算は変更していない。
- `apps/ui/tests/test_noise_gui.py`、`tools/verify_observation_noise_ui.py`：[日本語操作説明](../guide/06-gui.md)、[JSON規約](../../interfaces/observation-noise-diagnostic.md)、小容量結果を追加。

現在のRML重み・採否を変更しません。表示数は冗長なClosure行を含み、独立な画像測定数とは異なります。

## 4. 検証条件・結果

### 対象試験と実worker

対象40件成功、警告641件、3.29秒。段階047の30件と、新しいGUI入力・実workerの10件です。構成した2時刻・3channel・4局の半正定値統計を使い、選択したcellのJSONが直接APIと一致すること、入力SHA256が変わらないこと、JSONダウンロードを確認。

旧情報不足は未判定、全重み0は無効、4FFTの低SNR例は条件付き推定でも全Closureが無効でした。存在しない入力と範囲外channelはジョブ失敗として残し、summaryは未生成。入力読込の不正は日本語エラーとして返しました。

初回は39件成功・1件失敗。fixtureを再保存しようとして、保存APIの上書き拒否が働きました。fixtureを保存前に変えるよう修正し、製品の拒否条件は緩めていません。

### 最終wheelの実Chromium

Python3.12.3・Playwright1.63.0・Chromium153.0.8010.12、WSLのheadlessブラウザ。checkout外の独立workspaceでinstalled GUI/worker/診断APIを確認。段階047で固定した模擬VDIF由来のNPZをコピーし、原本SHA256を保持して使用しました。

| ブラウザ入力 | 処理 | 診断状態 | 有効Closure行 |
| --- | --- | --- | ---: |
| 固定模擬NPZ | 完了 | 条件付き推定、192000FFT、RF1420MHz | 6 |
| 基線FFT数を除いたfixture | 完了 | 未判定 | 0 |
| 重みを0にしたfixture | 完了 | 無効 | 0 |
| 相関値を小さくした低SNR fixture | 完了 | 条件付き推定 | 0 |

後3例は保存統計を変えたGUI用fixtureで、各状態を起こす実電圧を新しく生成した試験ではありません。履歴選択も、独立workspaceへ用意した固定履歴fixtureを使いました。新しいVDIF解析を実行したという意味ではありません。

入力軸の読込・履歴選択・診断実行・状態・σの表示・JSONダウンロード・入力なしのエラーを実際に操作。低SNRの無効行はσを「—」と表示し、保存値0を誤差0にしないことを確認。固定NPZの結果はinstalled APIと一致し、前段階の保存JSONの29項目も一致しました。

JSエラー0件、外部通信0件、日本語フォント読込成功、390pxの入力・結果の両画面で横はみ出しなし。画像は目視でも確認しました。初回ブラウザ試験は検証ツールのwait式がCSPのunsafe-eval禁止に拒否されました。function形式の待機条件へ直して成功し、製品のCSPは変更していません。Windows/WSLgの実ブラウザは未検証。

### 全回帰・配布・保存

source全回帰365件成功、警告23312件、420.28秒。installed全回帰365件成功、警告23312件、407.44秒。source・実ブラウザ・installed全回帰を順番に実施しました。試験除外なし。pip check成功。既存のBaseband/NumPy・Starlette等のdeprecation警告を含みます。

wheel5468468bytes、SHA256 `31a4f969879e16fa87cb9a4e5de5f3bd0e613beb15e915f15a4eff71352648d2`。

[実ブラウザ記録](../../validation/runs/stage048/browser.json)、[診断画面](../../validation/runs/stage048/noise-gui.png)、[390px・低SNR画面](../../validation/runs/stage048/noise-gui-mobile.png)、[回帰と識別情報](../../validation/runs/stage048/verification.json)を保存。wheel・完全ログ・途中のブラウザ試験はGit外`outputs/stage048-*/`です。

```bash
python tools/verify_observation_noise_ui.py --input correlation/shard-00000.npz --output outputs/new-noise-gui-check
```

最終wheelを導入したPython、PlaywrightとChromiumが必要です。この検証はブラウザと科学処理を一つずつ動かします。

常用localhost:8765サーバーは実行中ジョブがないことを確認して最終wheelで再起動し、既存39件の履歴を保持しました。独立workspaceのブラウザ試験は常用履歴へ混ぜていません。

## 5. 制約・未解決事項

公称FFT数を独立標本数とする、独立・平均0・proper Gaussian電圧・一定の局共分散という条件付き計算です。共分散のensemble不偏性と、一回の推定精度やClosure一次近似の信頼区間は区別します。

実際のFFT独立性、FIR・補間、量子化、RFI、時間変化、実機信頼区間、Cas A画像品質は未検証です。原本の軸読込はファイルを固定する操作ではありません。診断時の実際の時刻・RF・SHA256も確認します。

## 6. 次段階

Gaussian入力・既知の線形FIR/補間のモデルでFFT間の相関を検証し、公称FFT数を独立標本数と見なす近似の範囲を調べます。
