# 段階157：既定110arcsec平滑化と局所near-null部分空間

- 作成日：2026-10-29
- 状態：完了（固定比較作用素の計算参照）
- 比較元コミット：51bb5c31a7daef7d1c584a110b0d1e2d4ba6bc42（156）

## 読者向け概要

156では、固定priorの近くで予測Closureがほとんど変わらない画像方向を調べました。今回は、その方向を既存比較で使う110arcsecのGaussian kernelで平滑化したとき、どの程度のnormが残るかを確認しました。

これは**比較用の平滑化**で、実アンテナの一次beamではありません。signed方向は非負の復元画像でも、観測が許す画像誤差の信頼区間でもありません。局所部分空間と固定作用素の関係を、基底の選び方に依存しない量で記録します。

## 1. 目的・対象範囲

020/028〜030/115/119/125〜129/133/155/156と現experiment/registration/assessment/格子・full-support試験をreviewしました。既存`compare_relative`は非負画像をunit fluxへ揃え、Gaussian平滑化後に平行移動を評価します。保存Jacobianの数値null/near-null部分空間への作用は未接続でした。

新規 `workflows/smoothed_null_validation.py` と本レポート/索引/roadmap/[小容量記録](../../validation/runs/stage157/README.md)のみを変更。156を再微分せず、保存summary/J/priorと元133の入力3SHAを保持します。truth・生成sky・保存fit画像は読みません。新画像fit、尤度、RML、weight、GUIの変更はありません。

## 2. 固定平滑化作用素の照合

32×32/16arcsec、FWHM110arcsecからsigma=2.91954368849 pixelを固定。SciPy既定truncate4・mode constant/cval0・kernel半径12・平行移動0時のpad14で、**全支持60×60**へ写す線形作用素Bを作りました。独立な1D正規化Gaussian kernelの直接行列K1により `B(X)=K1 X K1^T` とし、GramをKronecker積で構成します。

中心点・端点・uniform・signed checkerboard・保存priorで既存`gaussian_filter`へ照合。最大差は4.63e−18以下、各入力画素の列sum1、signedの総和、線形性、既定の大paddingへの埋込みを固定許容で確認しました。kernel/支持/正規化をデータやtruthに合わせて変更していません。

既存`compare_relative`へは非負unit点対だけを `max_shift_pixels=0` で一度渡し、raw/zero-translation NRMSEと返す表示cropを独立Bへ照合。signed方向を非負画像APIへ渡さず、主比較で平行移動最適化を行いません。端点の全支持fluxは約1、表示crop内は約.322992であり、norm計算を表示cropへ置き換えていません。

## 3. 部分空間と基底に依存しない量

156と同じintensityの総和0接空間へ、固定Helmert正規直交基底H（1024×1023）を使います。保存JHのSVDから相対cut1e−6/1e−8/1e−10を固定し、rankが156保存値と一致することを確認しました。数値null/near-null基底をNとして、

```text
a = ||B N||_F² / ||B H||_F²
b = ||B N||_2  / ||B H||_2
```

を計算します。aは各正規直交方向へ作用させた二乗normの**和の比**、bは単位L2方向への最大作用素normの比です。画素基底・局所点・観測近似・cutに条件付きです。画像power保持率、失われた情報の割合、posterior分散ではありません。

Gram traceと、観測row-spaceを直接blurして全接空間から引く補空間恒等式を独立に照合。最大eigenpair residualと、対応する実signed方向のblur norm二乗を確認しました。固定angle.37radでnull基底を回したGramのtrace/最大eigenvalueも一致。単一の任意SVDベクトルだけを代表にしていません。

## 4. 数値結果

| 保存入力 | 相対cut | rank / 部分空間次元 | a：Frobenius二乗norm比 | b：spectral norm比 |
|---|---:|---:|---:|---:|
| high_a .3秒 | 1e−6 | 57 / 966 | .642651 | .993360 |
| high_a .3秒 | 1e−8 | 69 / 954 | .556046 | .988457 |
| high_a .3秒 | 1e−10 | 82 / 941 | .353354 | .953833 |
| high_a 3秒 | 1e−6 | 76 / 947 | .564251 | .989163 |
| high_a 3秒 | 1e−8 | 92 / 931 | .422053 | .983882 |
| high_a 3秒 | 1e−10 | 114 / 909 | .257268 | .944254 |

全接空間のBの二乗Frobenius normは約8.75507、spectral normは約.856877。主cut1e−10でも、平滑化作用が大きい単位signed方向がこの局所数値部分空間に残りました。方向の相対`||Jd||/||J||`は約2.48e−13/3.78e−12でした。全6対照の補空間恒等式差は2.67e−15以下、基底回転の最大eigenvalue差は2.23e−16以下です。

**これを「95%の画像信号が保持された」「画像誤差の35%が未観測」などとは読みません。** 単位L2のsigned方向に実際どれだけの振幅が許されるか、非負画像の有限変化で局所近似が通用するかは未確認です。二つの積分は同raw/取得pilotを共有し、support・重み・uvwも異なるため、値の差を露光時間だけの因果効果や性能順位へ変換しません。

weak_a .3秒は156の既存`no_high_snr_closures`をそのまま保持し、部分空間の結果はnullです。J=0という測定結果を補ってnorm比1の観測に変えていません。

## 5. 正式検証・保持

初回の科学計算・正式対象は成功しましたが、公開前の個人情報scanがPythonの行列積と属性参照の連続表記をメールアドレスとして誤検出し、Git add前に停止しました。全worker終了後に新workflowの演算子前後の空白だけを修正し、AST一致を確認。凍結を更新し、両環境の全選択を再実行しました。初回log/出力/凍結を保持し、成功件数へ合算しません。最終source**59成功/1.61秒**、installed**59成功/.79秒**、両警告0・除外0。入力・数式・閾値・許容は不変で、修正前後の全科学JSON/16配列も完全一致しました。新unitなし。主比較のtranslation optimization0と、既存registration試験内部の探索は区別します。全科学JSON・[16配列](../../validation/runs/stage157/arrays.npz)が完全一致し、13製品moduleの正確source/prefix/byte、native checkout外/runner/PYTHONPATHなし、非上書き2を確認しました。

既存456+new workflowの凍結457、156 archive2/元133入力3の5SHA、原本131の76SHA、対象外tracked1506、引用24fileを保持。151wheel SHA `c54348ec4b11b89bc70956c2f0d3ad77762b79093ca128834a4bebe053f2b2ec` と製品103file+4assetのsource/wheel/installed全byte不変です。

study本体wall約1.120/1.080秒、生涯peakRSS239497216/239960064byte（import/線形代数等を含む）、出力207916/208282byte。各worker120秒/追加保存64MiB/公開512KiB/段階1200秒以内。保存量とpeakRSSを区別し、全夜/GPU/必要RAMを保証しません。公開監査指摘0、文書リンク2125件で欠落0。

[作用素対照・全結果・入力/一次コードSHA](../../validation/runs/stage157/reference.json)、[正式検証](../../validation/runs/stage157/verification.json)。新full/collect/wheel/install/browser/MC/VDIF/再相関/画像fitなし。最新全回帰/wheel/両実GUIは[151](151-sequence-capacity-guard.md)の両2328成功552.61/551.31秒・各30220警告の引用で今回へ合算しません。通常GUI151も変更していません。

## 6. 制約と次段階

固定prior・観測高SNR/基線独立近似・同種同cell共分散・intensity尺度の局所参照です。真のFisher、posterior、実beam分解能、実画像confidence/誤差率/改善を較正しません。156の二step直接FDの未達とRichardsonへの正式手順改訂は過去記録のまま保持し、157の数値成功で消していません。実Cas A、未知実LO/gain/SEFD、実FFT独立性、beam/RFI、低SNR画像尤度、全夜GPUは未検証。新尤度/RML/画像再fit/GUI、外部追加反復/truth調整/Windows収録は保留です。

次158は、このsigned方向を有限の非負・総和1の候補へ動かすとき、局所近似がどの範囲まで対応するかを点検する候補です。既存115/156の評価・有限微小対照を先にreviewし、同じ確認を増やしません。truthに係数や振幅を合わせず、正supportから決まる規則・分岐/モデルzero・全候補を実行前固定します。非負候補の数値評価も実際に許される振幅confidenceや画像改善とは区別し、再fitはしません。実入力の新回答を優先し、148質問は繰り返しません。次160文書整理/予定200根本レビューです。
