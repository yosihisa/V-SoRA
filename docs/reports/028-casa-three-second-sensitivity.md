# 段階028：Cas Aの3秒VDIF合成と低感度の形状誤差

- 作成日：2026-10-02
- 状態：有限比較完了。良好な画像復元の確認には至らず
- 比較元コミット：c3297e2

## 読者向け概要

段階024ではSEFD10000Jy・1秒でrate推定が途中停止しました。今回は3秒を使い、8時刻をすべて処理できました。ただし復元した形状は真値から約34〜37%違いました。Closureへの適合が良くても、画像の正しさを保証しないことを示す結果です。

## 1. 目的・対象範囲

同じ8局・4時間に分散する8時刻・Cas A形状を、3秒pilotと3秒積分で試す。未知gain/rate、原本VDIF、Gaussian事前幅の依存を検証。実機の感度・位相安定時間、低SNR likelihood・連続長記録は対象外。

## 2. 完了条件

- 8時刻の成功または失敗を保存し、1秒条件と区別する。
- rate誤差・Closure数・相対形状誤差・optimizer停止を記録する。
- 同じ雑音データで事前幅160/240/320秒角を比較し、真値を画像化へ渡さない。
- 全回帰、学部生向け説明、レポートと公開監査・コミット。

## 3. 実際に行った作業

- `workflows/vdif_synthesis_validation.py`：0.3/1/3秒、3.04秒原本、750pilot、8局RF幾何を1秒以下へ分割、正確な中点sky covariance、生成近似の位相差概算。
- `workflows/synthesis_prior_validation.py`：同一合成NPZを3初期値・2000反復で事前幅比較。真値は最終の誤差評価のみ。
- 実観測入門を現在の処理順へ更新。OCXO初期差と時間Nyquistを説明。例えば1.42GHzの0.1ppm差は142Hzで、4ms pilotのNyquist125Hzを超える。広い初期差のcoarse探索は後続課題。
- packaged libraryは段階027から変更せず、配布wheelは027を維持。

## 4. 検証条件・結果

Python3.12.3/NumPy2.5.1/SciPy1.18.0/Astropy7.2.2/Baseband4.3.0。8局spread600m、1.42GHz、Fs2.048MHz、FFT8・1024blocks＝4ms、750pilot＝3秒。1520frame＝3.04秒原本、3秒再相関。4時間に8時刻を分散し、一局の使用露光は24秒。4時間連続露光ではない。

Cas A総flux1000Jy・SEFD10000Jyを生成側で仮定。連続colored Gaussian、sky covarianceは中心RF・中点で固定。正確な公称sample時計、各露光内で一定の未知gain/rate。受理channel中心3個・各256kHz。skyのnarrowband位相近似≤0.00625rad、時間変化を固定する位相概算≤0.00192rad（最初の時刻）。原本SHA/生成seed/LO差はsummaryに保持。

| 確認 | 観測結果 |
| --- | --- |
| 8時刻の工程 | 8/8完了。1秒条件の途中停止とは区別 |
| 最大station rate誤差 | 0.019761Hz |
| 残差rateから計算した最小coherence | 約99.14%。実OCXOの実測ではない |
| 全Closure | phase134、log amplitude116 |
| 独立RML集合 | phase118、log amplitude93、合計211 |
| 相対画像 | 有限・非負・総量1、ADC²から絶対Jy換算せず |
| 事前240秒角 | 位置合わせ前NRMSE35.62%、後33.99%、形状相関0.9352 |
| 事前160秒角 | 位置合わせ後NRMSE35.47%、χ²/測定数0.5837 |
| 事前320秒角 | 位置合わせ後NRMSE36.61%、χ²/測定数0.5700 |
| 事前240のχ²/測定数 | 0.5740。良好な形状の判定には使えない |
| optimizer | 各条件の選択探索は停止条件未到達、2000反復上限 |
| 回帰 | source130成功、3034既知deprecation warning |

比較は総量1・110秒角のGaussian平滑化・平行移動だけ。移動量も保存。事前160/320で位置合わせが探索境界付近へ達しており、広い位置登録探索での再確認も残る。これは統計的信頼区間ではない。生成は段階024の約0.5秒sky中点を正確なspan/2へ直し、RFをpiecewiseにしているため、雑音の乱数実現も含め完全に同一の1秒/3秒ペアではない。

段階024のSEFD1000Jy・1秒の形状誤差約2.8%と、今回の10000Jy・3秒の約34%を同じ達成結果として扱いません。実機SEFDは未測定です。

```bash
python tools/run.py workflows.vdif_synthesis_validation --sefd-jy 10000 --integration-s 3 --output outputs/stage028-vdif-casa-3s-sefd10000
python tools/run.py workflows.synthesis_prior_validation --synthesis-run outputs/stage028-vdif-casa-3s-sefd10000 --output outputs/stage028-priors
python tools/run.py pytest -q
```

[全生成条件・科学結果](../../validation/runs/stage028/summary.json)、[画像比較](../../validation/runs/stage028/comparison.png)、[事前幅比較](../../validation/runs/stage028/prior-summary.json)、[回帰と残差coherence](../../validation/runs/stage028/verification.json)。原本VDIF/相関/画像はGit外outputs/stage028-*。公開記録に個人を含むローカルパスを入れない。

## 5. 制約・未解決事項

一定gain/rateの模擬条件。3秒が実OCXOの安定時間という結果ではない。実データ・主ビーム・RFI・非線形LO・未知sample時計は未検証。SNR10のGaussian選別、baseline自己雑音/filtered FFT相関近似、少数露光、局所解と反復上限がある。初期LO差が時間Nyquistを超える場合のcoarse探索も未実装。

## 6. 次段階

高精度gain較正を要求しない主経路を維持し、低SNRの統計・露光数/局配置・広い初期LO差と短時間追跡・CPU/GPU高速化へ進む。実アンテナの有効面積/Tsys、OCXOの初期差と位相揺れ、sample時計を測った値で仮定を置き換える。Windows収録フロントエンドはハードウェアの進捗に合わせる。
