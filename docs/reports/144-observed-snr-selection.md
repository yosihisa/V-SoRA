# 段階144：観測SNRで選別した群と全試行の雑音推定を区別する

- 作成日：2026-10-29
- 状態：完了（既知IID Gaussianの有限比較。採用後の不偏性・coverageや実機の校正ではない）
- 比較元コミット：f7fceb438b2594b4f8883e172a3be262da40532d（143）

## 読者向け概要

全試行の平均では正しい雑音推定でも、「観測した信号が大きい」と選んだ試行だけでは、同じ性質をそのまま使えない。今回は既存の推定とSNR判定を変えず、全試行と採用群を分けて保存した。

既知モデルでは全試行の平均は固定検証条件を満たした一方、閾値付近の採用群ではvisibilityの実部平均が上側へ移った。これはこの固定Gaussianモデルの結果であり、実Cas Aの誤差補正や画像尤度を実装した段階ではない。

## 1. 目的・対象範囲とreview結果

既存046は全試行でのensemble不偏性、044は観測値で選ばない既知平均SNRを検証していた。098/101/104/107の独立二天空/score評価は、今回の同標本雑音推定後のSNR選別とは別である。同じ推定APIや既存試験を増やさず、[選別比較workflow](../../workflows/snr_selection_validation.py)だけを追加した。

047の外側のinactive/unverified gateはweight・power・flag・count等による。既定min_snr5は内側のjoint Closure有効行maskであり、低SNRをcell全体のinactiveへ変える閾値ではない。productionのform_closures(min_snr10)は弱信号weightを使うため、046全共分散からのjoint min_snr10と数値的に同じ選別ではない。

046のbatch_covariance、公開estimate_visibility_noise、044 joint_closure_noise、production form_closures、047 cell APIを再利用した。製品・既定閾値・RML・GUIは変更していない。

## 2. 固定条件・完了条件

4局、S=I+rho×全要素1、rho=0/0.45/1.6、M128。各4096独立proper Gaussian試行、seed144000+case番号、batch32。既知のquadrature SNRは0/4.9655/9.8462であるが、この真値は検証だけに使い、推定・選別へ渡さない。

baseline01とphase triangle012を先に固定した。集合はall、joint baseline/triangleの閾値5と10、production baseline/triangleの閾値10の計7種類。同じ試行を再利用する集合であり、7倍の独立観測とは数えない。既存batch推定を先頭2試行/caseで公開APIへ照合し、全試行で実joint5/10と実production10を呼ぶ。各case先頭1試行は047のcell stateと内側maskも照合する。

全試行は平均残差・真値からの二次残差・平均推定共分散を固定6 MCSE＋1e−11scaleで検査する。採用群は記述だけで、変化や改善を合否にしない。N0は統計をnull、N1は中心化共分散/SEを未定義とする。seed/試行数/閾値を結果で変えない。source/native全JSON/全配列、所属・非上書き・原本保持、関連試験・公開まで確認する。

## 3. 全試行と選別後の結果

全3caseで、全試行の全平均・全二次残差・全推定共分散平均が、既知visibility共分散に対して固定6 MCSE内だった。これは046の全試行の性質を今回の選別比較の対照として再確認したもので、採用群にも同じ検証目標を流用しない。

下表は実際の採用数と、固定baseline01の実部から既知meanを引いた平均。棄却数は4096−採用数で全件記録し、10個のN0集合を0誤差へ置換しなかった。今回はN1は発生していない。

| rho | 集合 | 採用 / 4096 | baseline01実部の平均誤差 |
| --- | --- | ---: | ---: |
| 0.0 | all | 4096 | -0.000830 |
| 0.0 | joint_baseline5 | 0 | null |
| 0.0 | joint_triangle5 | 0 | null |
| 0.0 | joint_baseline10 | 0 | null |
| 0.0 | joint_triangle10 | 0 | null |
| 0.0 | production_baseline10 | 0 | null |
| 0.0 | production_triangle10 | 0 | null |
| 0.45 | all | 4096 | 0.002189 |
| 0.45 | joint_baseline5 | 2182 | 0.068167 |
| 0.45 | joint_triangle5 | 878 | 0.086799 |
| 0.45 | joint_baseline10 | 0 | null |
| 0.45 | joint_triangle10 | 0 | null |
| 0.45 | production_baseline10 | 0 | null |
| 0.45 | production_triangle10 | 0 | null |
| 1.6 | all | 4096 | -0.002940 |
| 1.6 | joint_baseline5 | 4096 | -0.002940 |
| 1.6 | joint_triangle5 | 4096 | -0.002940 |
| 1.6 | joint_baseline10 | 1760 | 0.144838 |
| 1.6 | joint_triangle10 | 738 | 0.208781 |
| 1.6 | production_baseline10 | 1724 | 0.146913 |
| 1.6 | production_triangle10 | 712 | 0.210356 |

rho0.45のjoint triangle5採用群では、平均誤差約0.0868、真値からのMSE約0.01235、平均推定分散約0.00980だった。rho1.6のjoint triangle10採用群は約0.2088、MSE約0.06274、平均推定分散約0.04230。MSEは、選別後平均からの中心化分散と平均誤差の二乗を合わせた量で、同じ名前の共分散と混同しない。全Re/Im行列、中心化共分散、MSE、平均推定共分散と各MCSEを配列へ保存した。

この差を、そのまま実機用の係数・coverage・未知尤度の補正へ使わない。採用群の結果は固定モデルの記述で、全試行の不偏性を条件付き選別後へ引き継いだという主張ではない。

### 二つのSNR10と、047の外側state

rho1.6ではjoint10とproduction10のbaseline01 maskが36試行、triangle012 maskが26試行で異なった。productionは `2M/(観測局power積)` の弱信号weight、jointは046の全共分散の平均quadrature分散を使う。同じ数値10でも同じ判定という保証はない。今回の件数を他のSNR/入力の差へ一般化しない。

先頭試行の047は全caseでconditional_estimateだったが、内側の有効Closure行はrho0/0.45/1.6で0/3/6行だった。無効行の0値/0共分散を、誤差0の測定として採用しない。047の合成入力に付けたADC²は形式用のラベルであり、物理ADCの較正ではない。

## 4. 正式検証・変更・記録

source/nativeの全科学JSONと107配列（観測値・選別mask・各群統計）が直接完全一致。製品10moduleを正確なsource位置/導入prefixへ照合し、nativeはcheckout外・runner/PYTHONPATHなし。wrapper自体はcheckoutを必要とする。全study非上書き2件、原本131の76SHA保持を確認した。

既存046/044/047関連targetはsource84成功3.64秒、導入84成功2.42秒、各640既存警告/除外0。新unitなし、code/試験/tool/workflow449件を凍結し、初回正式手順で完了。主比較はメモリ上のGaussian電圧で、関連回帰内の一時模擬VDIF/相関は別に扱う。

workflow本体wallはsource4.701秒・導入4.604秒、生涯peakRSSは約79.3/79.8MiB。OMP/OpenBLAS各1、出力各16MiB未満。wallは起動/import前を含まず、RSSはLinux RUSAGE_SELFでimportを含む。単発CPU測定で全夜/GPU/最低PCの保証ではない。

製品103file＋4assetは138 wheel/source/導入先と全byte一致。新full/collect/wheel/導入/browserは行っていない。[138正式記録](../../validation/runs/stage138/verification.json)の両全2321成功542.82/541.45秒・各30220警告/除外0と両実GUI28worker/56downloadを引用し、144の新合格数へ加算しない。通常GUI8765も変更していない。

変更はworkflow、本レポートと索引、小容量[概要](../../validation/runs/stage144/reference.json)・[107配列](../../validation/runs/stage144/arrays.npz)・[正式検証](../../validation/runs/stage144/verification.json)・[資源](../../validation/runs/stage144/measurements.json)・[再実行条件](../../validation/runs/stage144/README.md)である。公開監査指摘0、文書リンク1892件で欠落0。

## 5. 制約・次段階

既知IID・一定局共分散・zero meanの参照で、filter/時変gain・rate fit/量子化/mask/未知SEFD・beam/実FFT独立性/実Cas A/低SNR画像尤度/全夜GPUは未校正。今回のSNRや選別後MSEをRMLの重みへ自動代入しない。

145は141〜144の成立範囲と未検証条件を、現在の画像誤差モデルへ接続できるか整理する候補。新尤度や係数調整を始める前に受入条件と予算を定める。残量回復後へ継続し、150で文書整理と専用根本レビューを行う。期限2026-11-06 15:00JST、追加reset禁止を維持する。
