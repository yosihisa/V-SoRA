# 段階147：同pilotのrate推定後powerと独立雑音pilotを比較する

- 作成日：2026-10-29
- 状態：完了（有限Gaussian visibility参照。rate推定失敗158件を含む）
- 比較元コミット：39fbaa302ade0aec7c24e6d76aa193da26f7c599（146）

## 読者向け概要

同じデータを使って位相の回転速度rateを求め、そのrateで信号を揃えて平均すると、固定rateを与えた場合と同じ雑音の扱いができるとは限らない。今回は学習pilotで一度求めたrateを、同じpilotと、別に発生させた雑音の評価pilotへ適用した。

推定が成功した群では、真値rateによる処理との差が、学習側は平均で正、独立評価側は負だった。全512組のうち推定成功は354組、失敗は158組であり、成功例だけを全体の性能とは扱わない。これは既知のGaussian相関値の結果で、実機のLO・画像誤差や同pilot依存を補正できた段階ではない。

## 1. 目的・対象範囲と既存検証

040の供給Gaussian rate誤差、042のsolver推定誤差と近似共分散、051の固定回転時のpower、098/101/107の既知template独立学習、143の同raw内parity評価を点検した。これらを再実装せず、**同じ推定rateを同pilotと独立雑音pilotへ適用した後のpower**を最小の追加対照とした。

[検証workflow](../../workflows/rate_fit_reuse_validation.py)は既存`estimate_station_rates`、`diagnose_rate_graph`、051の`time_power_moments`を呼ぶ。主比較はメモリ上のGaussian visibilityで、電圧生成・VDIF・FIR・相関・画像fitを行わない。047の局power/PSDゲートや051のfile診断全体を通した実験でもない。製品・閾値・RML・GUIは変更していない。

## 2. 固定条件・完了条件

3局/3基線、64cell×8ms＝0.512秒、1channel。真の局rateは0/7/−11Hz、固定複素平均は`exp(i[0.3,−0.7,1.1])`。各cell/基線の独立円対称Gaussian visibility誤差を仮定し、quadrature標準偏差σ=0.5/1の2条件を各256回、計512組実行する。weightは既知の`1/σ²`で、未知SEFDを推定したものではない。

乱数は`SeedSequence([147, 条件番号, 試行番号, role])`、role0が学習、role1が評価。共通の天空相当平均・rate・時刻を固定し、雑音だけを独立に発生させる。独立性はこの生成モデルの仮定であり、143の同一rawを分割して独立と呼んだものではない。条件間は別乱数で、条件間の対の差として比較しない。

推定へ渡すのは学習のvisibility/weight/time/pairだけ。真値rate・複素平均・評価pilotを渡さない。探索上限50Hz、Nyquist62.5Hz、既定min_snr8/min_peak_z8/整合chisq3を固定した。真値は生成と推定後の検証だけに使い、探索・seed・試行数を結果で変えない。

### 何を制御し、何を記述に留めるか

051からnoise差引mean powerを

```text
P = |mean_t [V_t exp(−2πi fitted_rate (t−center))]|² − 2σ²/N
```

として得る。固定した真値rateを使うoracleでは、全試行の平均powerの期待値は1、平均複素残差の期待値は0である。推定の成否で分母を減らさず、各平均を事前固定6 MCSE＋1e−11で検査した。MCSEは独立試行の標本SD（ddof1）/√Nであり、観測者のconfidenceではない。

独立評価側では、学習結果を固定した条件の下で、期待powerは`|mean exp(−2πi delta_rate (t−center))|²`になる。delta_rateは推定と真値の差で、等間隔のDirichlet/sinc式と直接和を照合した。これは推定後の真値を使う検証専用予測で、未知rateから実際の損失を予測する新APIではない。成功群N≥2なら評価powerとこの予測の平均差を固定6 MCSE内とし、N<2は未判定とする条件を先に定めた。

学習側の同じ差、および学習/評価それぞれのfit−oracleの対差は記述のみ。符号や改善を合否にしない。失敗のpowerを0へ補わず、全state・profileまたはfailure graph、負・1超の値を残す。source/native全JSON/配列、所属・非上書き・原本保持、関連試験・公開までを完了条件とした。worker各120秒、各出力/公開記録16MiB以下を固定した。

## 3. 推定の成否を分けた結果

| σ | 推定成功 / 256 | graph切断 | 局rate不整合 |
| --- | ---: | ---: | ---: |
| 0.5 | 233 | 0 | 23 |
| 1.0 | 121 | 131 | 4 |

全512組のstateを保持した。graph切断131件と、graphはconnectedでも局rate整合で停止した27件を区別して記録した。失敗158件のfit powerはnull、数値配列は成功indexと対応付け、0埋めや成功分母への混入をしなかった。

全試行のoracle複素平均/powerと、成功群に条件付けた独立評価側の既知予測との差は、全基線で固定6 MCSE内だった。学習側へ独立評価側の期待値を流用した合格判定はしていない。

### 同じ成功群でのfit−oracleの対差

下表はnoise差引mean powerの対差の平均±MCSE。単位は任意visibility単位の二乗で、coherence・振幅保持率・画像SNRではない。採用された学習試行に条件付けている。

| σ | 基線 | 同pilot（学習） | 独立雑音の評価pilot |
| --- | --- | ---: | ---: |
| 0.5 | 01 | 0.002371 ± 0.000290 | −0.002496 ± 0.000496 |
| 0.5 | 02 | 0.002668 ± 0.000321 | −0.002874 ± 0.000574 |
| 0.5 | 12 | 0.002572 ± 0.000306 | −0.002395 ± 0.000450 |
| 1.0 | 01 | 0.007940 ± 0.003997 | −0.018715 ± 0.004421 |
| 1.0 | 02 | 0.005221 ± 0.003200 | −0.016072 ± 0.003799 |
| 1.0 | 12 | 0.009520 ± 0.002886 | −0.020034 ± 0.003247 |

平均の符号が揃っても、各試行・基線で同じ符号になるとは限らない。成功354組×3基線＝1,062対のうち、fit−oracleが負だったのは学習267対、評価676対だった。noise差引powerそのものの負値は今回は0、1超は全oracle3,072値中1,469、fit2,124値中1,120あり、切り詰めていない。期待値1のモデルでも、各実現値の上限が1になる意味ではない。

σ1の学習側powerと独立評価専用予測の平均差は基線ごとに約0.154/0.115/0.0867だった。**同pilotのfitと、推定器が元から持つ検出・整合gateの条件付けを分離した効果ではない。** これらを純粋なrate推定の偏り、実機の補正係数やconfidenceへ読み替えない。147は独立雑音の対照を加えたもので、学習側の依存を除去・校正する方法を実装したわけではない。

## 4. 正式検証・変更・記録

source/nativeの全科学JSONと[33数値配列](../../validation/runs/stage147/arrays.npz)が直接完全一致し、各studyで製品16moduleの正確なsource位置/導入prefixを確認した。nativeはcheckout外・runner/PYTHONPATHなしで、workflow自体はcheckoutを必要とする。[全512組とprofile/graph](../../validation/runs/stage147/reference.json)、[正式検証](../../validation/runs/stage147/verification.json)、[資源](../../validation/runs/stage147/measurements.json)、[再実行条件](../../validation/runs/stage147/README.md)を保存した。

既存5fileの101対象はsource5.74秒・導入4.22秒で成功、各640既存警告・除外0。新unitなし。凍結451項目を維持し、初回正式手順で完了した。推定失敗158件は主比較が記録すべき結果であり、正式workflowの未完了や除外ではない。既存原本131の76SHA、非上書き拒否2件を確認した。

workflow本体wallはsource0.465秒・導入0.465秒、生涯peakRSSは約86.2/86.6MiB。OMP/OpenBLAS各1。wallはPython/importの起動前を含まず、RSSはimportを含む。単発CPU値で全夜/GPU/最低PCの保証ではない。

製品103file＋4assetは138 wheel/source/導入先と全byte一致。新full/collect/wheel/導入/browser/raw生成/再相関/画像fitは行っていない。138の両全2321成功542.82/541.45秒・各30220警告/除外0、両実GUI28worker/56downloadは引用のみで147の新合格へ加算しない。通常GUI138も変更していない。公開監査指摘0、文書リンク1947件で欠落0。

## 5. 制約・未解決事項

既知平均・既知雑音分散・独立円対称Gaussian visibilityの参照で、一般の局電圧から作った全基線の実際の分布ではない。時間/channel/基線の共有雑音、FIR/量子化/mask、実FFT独立性、未知gain/SEFD/LO、実OCXO、実Cas A、低SNR画像尤度は未校正。探索上限とaliasの条件も外部仮定である。

成功群のMCSEは学習側の採否に条件付けた量で、全観測の検出性能や画像のconfidenceではない。2条件の差を同じ乱数による対の性能差とせず、source/nativeの再実行を独立な追加512試行とも数えない。条件付きrate不確かさAPIやRMLのweightは変更しない。

## 6. 次段階

145の八条件は引き続き残り、新画像/GUI接続は保留する。148〜149は実入力・測定手段の確認へ戻る候補とし、実機が使えるかを確認してから測定を選ぶ。使えない項目を実測済みにせず、138/139の同等試験を繰り返して段階数を増やさない。原本131が模擬であること、必要なI/Q・sample0/UTC・rate・LO・感度/beam・RFIの情報を区別し、150の文書整理・専用根本レビューへ渡す。148以降と150自体は今回未実装・未実施。期限2026-11-06 15:00JST、追加reset禁止を維持する。
