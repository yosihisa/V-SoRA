# 段階029：短い刻みの広範囲LO探索

- 作成日：2026-10-03
- 状態：参照実装・有限検証完了
- 比較元コミット：1f59510

## 読者向け概要

位相を一定間隔で読むと、その間に整数回多く回転した分を区別できません。pilot（周波数差を見積もる短い相関列）を0.25ms刻みにすることで、最大1185Hzの未知の基線周波数差を処理できました。画像には補正後の1秒積分を使います。実機のOCXO差を測った結果ではありません。

## 1. 目的・対象範囲

モデル不要のLO探索を大きな初期周波数差へ拡張。pilot刻みと画像積分を別指定し、CLI・日本語GUI・保存配列上限を整備。未知sample時計、非線形LO、低SNR統計、実機の初期差測定は対象外。

## 2. 完了条件

- 原本VDIFで100Hzを超える未知LO差を、既知gain/skyなしで推定・再相関・Closure画像化。
- 0.25ms pilotと1秒画像、入力格子・Nyquist・配列上限の拒否を検証。
- 折り返しが検出不能となる例も保存し、探索範囲を実機保証としない。
- source/wheel回帰、GUIブラウザ、checkout外CLI/APIを確認し、記録・匿名公開監査・コミット。

## 3. 実際に行った作業

- `aligned.py`：16384積分まで対応。span3秒・time×channel×baseline100万cell上限を読取前に検査。IQ bufferは従来の分割上限を維持。
- `closure_pipeline.py`：`pilot_integration_s`を追加。省略時はmanifestの値。FFT整数個、VDIF frameの整数分割/整数個、時間Nyquistを検査。刻み・span・探索端sinc coherence・SK判定可能割合を保存。
- `rate.py`：Nyquistと、初期差の外部上限が必要なことをprofileへ記録。未知複素値と時間rateを推定する方法は維持。
- GUI `models.py`、`index.html`、`app.js`：日本語入力・結果・SK未判定表示。`test_rate.py`、`test_pilot_dimensions.py`、GUI試験を追加。
- `vdif_closure_validation.py`：生成rate/FFTの指定を追加。`wide_rate_validation.py`、配布/ブラウザ検証ツール、入力規約と学部生向け説明を更新。

## 4. 検証条件・結果

Python3.12.3、NumPy2.5.1、SciPy1.18.0、Astropy7.2.2、Baseband4.3.0。4局、1.42GHz、Fs2.048MHz、FFT8、530frame=1.06秒。連続band-limited Gaussian点源1000Jy、受信機SEFD10000Jy、未知の一定gain。正確な公称sample時計とzero offsetを供給。生成sky/fluxはpipelineへ渡さず、入力source.model=unknown。

pilotは64FFT/cell=0.25ms、4096時刻=1.024秒。Nyquist2000Hz、探索1500Hz、最終積分1秒。基準局との差[0, 420, -375, 810]Hz、全基線の最大差1185Hz。これらは生成条件であり実測OCXO値ではない。

| 確認 | 観測・計算結果 |
| --- | --- |
| 原本VDIFからの5工程 | 完了、ADC²の相関・総相対flux1の画像 |
| 最大station rate誤差 | 0.008899Hz（模擬データでの観測値） |
| Closure | phase12、log amplitude6。独立phase9、amplitude6 |
| RML | 選択探索は停止条件到達、χ²/測定数0.4285 |
| CPU処理時間 | 22.21秒／約1秒の入力。単回WSL計測、実時間性能の保証なし |
| 探索端のcoherence | sinc(1500×0.00025)=約78.4%（計算値） |
| pilotのSK判定可能割合 | 0%。64FFTはmin_sk_blocks=128未満。判定済みとはしない |
| 不正刻み・Nyquist・span/cell超過・bool時刻数 | 読取前に拒否、完成/partial出力なし |
| source / installed wheel回帰 | 各140成功、3418既知deprecation warning |
| Chromium153実操作 | VDIF解析・模擬・感度・RFI検証・中止成功。JS例外0、外部通信0、390px横溢れなし |
| checkout外 | installed module由来確認、6入口help、CLI/GUI解析と感度GUI完了 |

解析的なvisibilityだけを使う別試験では、真の局差[0, 4100, -4075, 8210]Hzが[0, 100, -75, 210]Hzと誤認され、全局のrate解が整合しました。これは4000Hzの整数倍が同じ位相列になるためです。範囲外の差を常に検出できる処理ではありません。この試験の初回assertionは「誤差>8000Hz」でしたが、正確な差は8000Hzなので期待値を修正。推定器は変更していません。

```bash
python tools/run.py workflows.wide_rate_validation --output outputs/stage029-wide-rate
python tools/run.py pytest -q
```

詳細：[科学結果・原本SHA](../../validation/runs/stage029/summary.json)、[画像](../../validation/runs/stage029/rml.png)、[ブラウザ結果](../../validation/runs/stage029/browser.json)、[GUI画面](../../validation/runs/stage029/analysis-screen.png)、[checkout外検証](../../validation/runs/stage029/installed.json)、[回帰・wheel識別](../../validation/runs/stage029/verification.json)。大容量VDIF/wheel/ログはGit外outputs/stage029-*。

## 5. 制約・未解決事項

初期の全基線LO差が探索範囲内という外部条件が必要。指定した探索幅は測定した上限ではない。短いcellでSK未判定となるため、実RFIの確認と対処が必要。pilot内の一定gain/rate、独立雑音、filtered FFTとself-noiseの近似、未校正の探索誤検出率がある。点源の処理接続確認で、Cas Aの良好な形状復元・実機の1秒安定性は未確認。3秒以内の参照処理、長記録/自動追跡/GPUは後続。

## 6. 次段階

低感度Cas Aの画像評価で位置登録が探索境界へ達した点を再確認する。平行移動の広い探索と、画面外へ移動したfluxを誤差から消さない比較を整備し、既存画像を再評価する。画像を作り直した改善と比較方法の変更を区別する。
