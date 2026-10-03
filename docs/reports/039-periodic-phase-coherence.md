# 段階039：周期位相変動を加えたVDIFとClosure

- 作成日：2026-10-03
- 状態：完了（有限模擬条件・CLI/GUIの範囲）
- 比較元コミット：0c35257

## 読者向け概要

平均rateが同じになる速い位相の揺れは、4分割の推定や線形モデルの適合を通る場合があります。模擬IQ→VDIFでも、処理完了のまま約15%の減衰とClosure amplitudeの偏りが残る例を再現しました。GUIの「周期位相変動とClosure」で自分の環境でも試せます。

## 1. 目的・対象範囲・完了条件

段階036の数学的反例を物理IQ→VDIFへ広げ、平均rateの補正から位相安定を保証できないことを確認します。対照・速い周期・遅い周期の同じsky/noiseを生成し、減衰・Closure・停止を記録します。完了条件はsource/wheel・独立CLI・実Chromium・日本語GUI・レポート・匿名コミットです。OCXO実機、確率的phase noise、Cas A画像忠実度は対象外です。

## 2. 実際の作業・変更ファイル

- `workflows/vdif_closure_validation.py`：局ごとのcos位相変動を任意の仮定振幅/frequencyで生成。radとHzの値を記録。無効値は生成前に拒否。
- `workflows/periodic_phase_validation.py`：同じseed35の対照・32Hz・0.5HzのIQ→VDIFを生成して4条件を処理。補正は測定rateのみ。解析的coherenceと対照振幅比、Closure RMSを比較。
- correlator tests：周期平均とBessel関数、共通位相差0、無効生成条件を確認。
- UIの `models.py`、`jobs.py`、`worker.py`、`static/index.html`、`static/app.js`：日本語の動作検証、条件別完了/未完了、仮定した対照比・Closure表、図の説明。
- UI tests、`tools/verify_periodic_installed.py`、`tools/verify_periodic_ui.py`、guide06/07、公開記録。

生成式は各局の追加位相 `A_i * cos(2π f t)` radです。最大振幅差0.8rad。位相揺れの生成値は比較用で、rate solverへ渡しません。時計は既知の線形ADCモデルです。

## 3. 検証条件・結果

### 物理IQ→VDIF

4局、1.42GHz、2.048Msample/s、点源1000Jy、仮定SEFD10000Jy、固定の未知局gain、seed35、各記録3.06秒。全局の初期LO rateは0。cos位相振幅は[0,0.2,-0.3,0.5]rad。pilot2ms×1500、最終相関3秒です。

| 条件・モデル | 相関の状態 | 分割診断 | 最小振幅比（対照比） | Closure log amplitude RMS |
| --- | --- | --- | ---: | ---: |
| 変動なし・一定rate | 完了 | 整合 | 1.00000 | 0.03273 |
| 32Hz位相・一定rate | 完了 | 整合 | 0.84607 | 0.10466 |
| 32Hz位相・線形rate | 完了 | 整合 | 0.84590 | 0.10474 |
| 0.5Hz位相・線形rate | 未完了 | 変動検出 | 未計算 | 未計算 |

速い周期は各0.75秒部分に24周期あり、平均rateでは見えません。線形モデルreduced χ²は2.130で採用条件を通りましたが、減衰とClosure amplitude偏りは残りました。Closure phase RMSは対照0.02772rad、速い周期の一定/線形モデル0.02970/0.02962radです。

遅い周期は部分ごとに測れるrateが変わり、線形モデルと不整合となって停止しました。補正モデルにfallbackしたり、停止条件の結果を完成相関として使っていません。

同じ雑音/sky/gainの対照を用意できる検証なので、振幅比を計算できます。未知skyの実観測で、この比を直接測った結果ではありません。量子化・FIR・channel化・幾何近似を含む実VDIFの比と、生成位相＋測定補正から積分した計算coherenceの最大差は0.00304でした。

整数周期の計算はJ0(A_i-A_j)へ一致します。[NIST DLMF 10.9](https://dlmf.nist.gov/10.9)のBessel積分表現に対応します。実位相noise spectrumや実OCXOのコヒーレンス時間を測った実験ではありません。

### CLIと日本語GUI

- インストール済みproduction CLIをcheckout外で速い/遅い周期のVDIFへ実行。
- 速い周期の全visibility/weight/UVW/time/frequency/露光/power/SK/整数diagnosticsがsourceと一致。
- 遅い周期は同じ変動診断で停止し、最終相関を生成しないことを確認。
- インストール済みGUIから、checkout側の自己完結workflowを呼ぶことを明記して実Chromiumで検証。
- 表に相関の完了3条件/未完了1条件を区別し、84.59%と計算値、実機測定でないことを表示。
- Chromium153、日本語font成功、JS error0、外部request0、390px横はみ出しなし。

GUIの検証実行が完了したことと、各相関の状態を区別しています。RML画像はこの段階では生成していません。Windowsブラウザ・WSLg・実機は未検証です。メインlocalhostサーバーは実行中ジョブ0を確認して更新しました。

### 全回帰

初回はsource/wheelとも224件成功・1件失敗、警告21472件でした。新しい重いGUI試験が同時実行時に240秒の終了待ちを超えました。数値の合否条件を変更せず、この試験の待ち時間を480秒へ延長し、source/wheelを順番に再実行しました。初回を合格として集計していません。

- 最終source225件成功、警告21472件、372.91秒。
- 最終installed wheel225件成功、警告21472件、373.56秒。pip check成功。
- wheel 5,451,282bytes、SHA256 `99cba728a4ebcbaca25f6b64e982d61980a526dd7be7717119100d6bd4f9da2d`。

既存のBaseband/NumPy・Starlette deprecation警告を含みます。警告ゼロの検証ではありません。

## 4. 再実行・保存記録

```bash
python tools/run.py workflows.periodic_phase_validation --output outputs/new-periodic-phase
python tools/verify_periodic_installed.py --source-run outputs/stage039-periodic --output outputs/new-installed-periodic
python tools/verify_periodic_ui.py --output outputs/new-periodic-browser
```

browser toolにはPlaywright/Chromiumとcheckoutが必要です。自己完結workflowは数分、数百MBを使います。大きな原本と実行ログはGit外 `outputs/stage039-periodic/`、`outputs/stage039-installed-cli/`、`outputs/stage039-browser/`、`outputs/stage039-verification/`。公開の [生成条件・pilot SHA・数値](../../validation/runs/stage039/summary.json)、[CLI](../../validation/runs/stage039/installed-cli.json)、[browser](../../validation/runs/stage039/browser.json)、[全回帰/wheel](../../validation/runs/stage039/verification.json)、[数値比較の図](../../validation/runs/stage039/periodic-coherence.png)、[日本語画面](../../validation/runs/stage039/gui.png)を参照してください。

## 5. 制約・未解決事項

仮定した周期位相の一つのseed・固定gain・点源実験です。実機のphase noise、温度変動、突発位相、非線形ADC時計、低SNRや拡がったCas Aを網羅しません。分割診断/モデル適合が通っても、高速な揺れを測定したことにはなりません。位相中心/gainの補正と、平均中の損失を区別して確認する必要があります。

## 6. 次段階

測定したモデルのパラメータ誤差による損失と、モデル外の速い位相揺れを区別する診断を検討します。低SNRと実機条件での適用範囲も継続して評価します。
