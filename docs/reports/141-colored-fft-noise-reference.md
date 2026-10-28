# 段階141：既知の色付き入力を固定FIR・FFTの全雑音参照へ接続

- 作成日：2026-10-29
- 状態：完了（固定Gaussianモデルの有限検証。実FFT独立性や画像誤差の校正ではない）
- 比較元コミット：ffd80c5fccf14be76c251a81de85792e74b62d34（140）

## 読者向け概要

重ねないFFTでも、手前のfilterが隣の電圧を混ぜると、異なるFFTの雑音が関係する。白色入力と固定filterの確認は049に既にあったため、同じ実験を新しい段階として繰り返さず、入力を短い既知filterで色付けする差だけを追加した。「色付き」は周波数ごとのpowerが一様でないという意味である。

既存APIへ合成した固定係数を渡し、別の行列計算と直接の電圧処理に照合した。今回の色付きモデルでは独立FFTを仮定した分散との差がchannelごとに変わったが、実観測の有効FFT数を測定したものではない。

## 1. 目的・対象範囲

140の候補141で既存042/049/051のcode・試験・正式記録を先に点検した。049には既存FIR/sinc/FFTとの直接4条件照合と6モデルのGaussian試行があり、白色の同等API・benchmarkを追加しないと決めた。候補142のうち、固定した短い入力色付けだけを前倒しした。

[既存049 API](../../apps/simulator/src/vsora_simulator/filtered_noise.py)の固定operatorを合成して使う。[新workflow](../../workflows/colored_fft_noise_validation.py)は検証用で、製品・RML・重み・GUIの変更はない。色付き入力は既知のproper Gaussianで、131のFFT周期天空、実ADC/VDIF、時変clock/幾何/rate、欠損、量子化、同pilot推定・SNR選別は対象外である。

## 2. 完了条件

1. 全局/時刻の大きい共分散行列と実Gaussian二次形式のtraceによる独立計算を、既存049のlag和による平均・全Re/Im共分散へ1e−11許容で照合する。
2. 実lfilterの色付け→65tap FIR→既存interpolate_samples→FFTを通す。各color先頭2試行で全8channelのkernel積と実FXAccumulatorを直接照合する。
3. 固定seed141・各color4096試行で全平均/全共分散要素を事前固定6 MCSE＋丸め許容内へ照合する。source/導入の全JSON・全配列、所属、非上書き、原本SHAを確認する。
4. 関連試験、製品byte不変、文書/監査/匿名commit/pushまで完了する。新full/wheel/ブラウザは不変確認の上で138を引用する。

## 3. 条件と計算の独立性

4局、FFT8、非重複16block、局別offset[0,0.25,0.5,0.75]sample、shift済みchannel3/4/5（−Fs/8・DC・＋Fs/8）。局共分散は共通成分1、位相[0,.4,1.1,2.2]radの成分0.7、独立受信機成分1.5で既知とする。

白色対照はg=[1,0,0]、色付きはg=[1,0.75i,0.25]/√1.625。両方ともfilter次数2を含む同じquery原点98+offsetを使う。既存049のhにreverse(g)をconvolutionした係数はraw0からの参照になる。推定された実スペクトルではない。

独立計算は全出力時刻の局共分散を作り、実ベクトルzの共分散R、二次形式zᵀA zについて、平均tr(AR)、共分散2tr(ARBR)を計算する。049の時刻lag和やvisibility_noise_momentsの式をこの独立側で呼ばない。visibility自体の分布をGaussianと仮定するものでもない。

同じ生Gaussian乱数を白色/色付きに使い、3channelも同じ電圧から作る。各環境には4096個の独立な生試行があり、2color×3channelを独立24576観測と数えない。sourceと導入の再実行も新たな独立性能試行へ加算しない。rawはbatch32で破棄し、新VDIFは保存しない。

## 4. 検証結果

### 全共分散と有限電圧

| 入力 | channel | モデル分散 / IID仮定の分散の範囲 | 平均差の最大 / MCSE | 共分散差の最大 / MCSE |
| --- | ---: | ---: | ---: | ---: |
| white | 3 | 1.00000845〜1.00046268 | 2.436 | 2.103 |
| white | 4 | 0.99999769〜1.00030097 | 1.585 | 2.082 |
| white | 5 | 1.00003514〜1.00035341 | 1.430 | 2.337 |
| colored | 3 | 1.03073987〜1.03490548 | 1.363 | 2.395 |
| colored | 4 | 1.00527710〜1.00559831 | 1.755 | 2.059 |
| colored | 5 | 1.00163903〜1.00198047 | 1.497 | 1.987 |

全6条件で独立traceと049の全平均/共分散が一致し、全基線・全Re/Imの平均と残差積平均が固定6 MCSE内だった。MCSEはMonte Carloで求めた平均の標準誤差で、観測結果の信頼区間ではない。共分散のMCSEには、既知平均からの残差積の標本SD/√4096を使う。

表の倍率は既知モデルの計算値であり、4096試行から0.1〜3.5%程度の小さい差を精密に測れたという意味ではない。whiteのごく僅かな1未満も含め、値を1へ切り上げない。局別係数では共分散全体を単一の有効Mへ換算しない。実効FFT数やRMLの補正係数として用いない。

先頭2試行×2colorの全8channel直接積との最大差は約5.7e−15、実FXと同じFFTの手計算visibilityとの差は0だった。これ以外の全試行も既存補間と実FFTの電圧を通すが、FXAccumulator自体の個別呼出しは先頭2試行に限る。

### 正式試験・導入・保持

source/導入で全科学JSONと42数値配列を直接完全一致確認した。両workerの製品8moduleを正確なsource位置/導入prefixへ確認し、nativeはcheckout外・runner/PYTHONPATHなし。wrapper自体はcheckoutを必要とする。全出力の非上書き2件、元131の76入力SHA保持を確認した。

既存filtered_noise/visibility_momentsの対象試験はsource52成功1.40秒、導入52成功1.38秒、警告0・除外0。新unitは追加していない。正式検証中はcode/試験/tool/workflow446件を凍結した。

初回source対象52成功後、新workflowのNumPy advanced indexingがbatch軸を先頭に保たず、最初のMC batchでshape(6,32)と(6,)の演算が失敗した。全処理の終了後、新workflowだけでchannelを先に取り出す形へ修正し、ログと未完成出力を保持した。製品変更・seed/反復数/許容変更はない。source対象から導入までの正式手順を全て再実行し、初回52成功を正式件数へ足していない。

有限workflow本体wallはsource6.037秒・導入5.830秒、生涯peakRSSは各約113.4MiB。workflow内wallはPython起動/import前を含まず、RSSはLinux RUSAGE_SELFで依存読込も含む。OMP/OpenBLAS各1、各出力16MiB未満。単発のCPU測定で、全夜/GPU/最低PCへの保証ではない。

製品103file＋4assetは138 wheel/source/導入先と全byte一致。新全回帰/collect/wheel/導入/browserは行っていない。[138正式記録](../../validation/runs/stage138/verification.json)の両全2321成功542.82/541.45秒・各30220警告/除外0と両実GUI28worker/56downloadを引用し、141の新成功へ加算しない。通常GUI8765は更新していない。

[全科学概要](../../validation/runs/stage141/reference.json)、[全配列](../../validation/runs/stage141/arrays.npz)、[正式検証](../../validation/runs/stage141/verification.json)、[実行資源](../../validation/runs/stage141/measurements.json)、[再実行条件](../../validation/runs/stage141/README.md)を保存した。公開監査指摘0、文書リンク1855件で欠落0。

## 5. 制約・未解決事項

合成した固定operatorで既知の色付きGaussianを扱えたことと、131の周期色付き入力・時変幾何・補間・量子化や未知実データへ妥当な誤差を付けられることは別である。名目FFT数、共通標本集合、IID、coverageを混同しない。同pilotのrate推定と選別、cell内損失、未知gain/SEFD、実Cas A、低SNR画像尤度は未校正のまま。今回のモデル倍率で136のpower比をcoherenceへ変換しない。

## 6. 次段階

142は141の固定FIR色付けを再実行せず、131の周期スペクトルと時変処理のうち未接続の最小差を点検して正式目的を決める候補とする。既存API/検証で足りるなら重複段階を作らない。143の同pilot推定・144の選別という別課題も維持する。150は文書整理と専用根本レビュー、期限は2026-11-06 15:00JST。
