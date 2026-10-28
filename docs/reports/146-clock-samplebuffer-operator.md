# 段階146：供給clockの傾きと実SampleBufferの有限係数を照合する

- 作成日：2026-10-29
- 状態：完了（合成decoded frameによる有限作用素の検証。実VDIF・実機・画像雑音の校正ではない）
- 比較元コミット：85f0defb7463cfdcf1f52fb4a411214d91f91298（145）

## 読者向け概要

入力と出力の関係が線形なら、入力の各位置に1を置いた結果を並べると、処理の全係数を得られる。これを「有限作用素」と呼ぶ。145で残した、固定offsetの参照とclockに応じて変わる実補間の差を、この方法で点検した。

既存のSampleBufferを実行し、その全係数が独立に作ったFIR・補間・FFTの係数と一致した。readerだけを合成decoded frameへ差し替えており、VDIFのデコードや量子化、未知clockの推定を確認した結果ではない。既知係数での確認を、実FFTの独立性や画像の誤差保証へ拡大しない。

## 1. 目的・対象範囲と既存検証

049には固定offsetのFIR/sinc/FFTとkernel、clockには独立な連続波によるdrift、SampleBufferには実VDIFの逐次/seek一致の試験が既にある。055/059/061/078の時間共分散や三次統計も再利用対象であり、新しい同等APIは作らない。今回は、**供給clockの傾きで変わるqueryを通した実SampleBufferの全係数**だけを追加の接続対象とした。

変更は[検証workflow](../../workflows/clock_operator_validation.py)、本レポートと索引、[小容量記録](../../validation/runs/stage146/README.md)である。SampleBuffer・FX・統計API・RML・GUIの製品コードは変更していない。

## 2. 固定条件・完了条件

3局、入力512 complex標本、FFT8×16block、名目Fs2.048MHz、固定offsetは0/0.25/0.5標本。queryは`(96+offset+出力標本番号)×actual_rate/nominal_rate`で、SampleBufferがFIR群遅延を補う32標本を追加する。input_startを`−(96+offset)/Fs`に固定し、局clockは0/0/0 ppmと−200/0/+200 ppmの2条件。実sample rateでFIR設計も変わる。幾何delayとRF/rate補正位相は0で、これらの経路を実行していない。

実SampleBufferのreaderだけへ、64標本ずつ・全validの合成decoded frameを供給し、`seek_input=False`で実FIR状態・guard・補間を使う。独立側はI0関数によるKaiser窓、正規化sinc、FIR畳み込み、正規直交DFTを直接合成する。全512実基底×3局×2条件＝3,072回のbuffer呼出で、全8channel・16blockの複素係数393,216要素を照合する。これは固定valid・量子化なしの複素線形処理に限った基底検査であり、3,072独立の観測試行ではない。

seed146/147の既知proper Gaussian電圧（局共分散`I+0.3×全要素1`）は、同じseedの電圧を両clock条件で共有する。128標本一括と32標本chunkのbufferを比較し、実FXを一括/chunkで計8回finishする。2seedはMonte Carlo校正ではない。全係数・電圧・FX・モーメントの許容は事前固定のrtol1e−11/atol1e−12。

clock0は既存049のkernel/visibilityモーメントへ照合する。時変条件は全局・時刻の既知共分散を有限作用素から作り、既存142の二次形式traceと別の全block対Wick和で、全平均・複素/擬/全実共分散を照合する。Monte Carloは0回、MCSEは対象外とした。差の大きさや改善を合否にしない。

source/nativeの全JSON・全数値配列、module所属、非上書き、原本保持、関連試験・公開までを完了条件とした。worker各120秒、出力各16MiB以下を実行前に固定した。

## 3. 実際の係数・電圧・FXの結果

| 条件 | 基底buffer呼出 | 全係数の最大絶対差 | 独立FIR tap最大差 | 2seedの出力FFT最大差 | chunk電圧最大差 | FX相関最大差 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0/0/0 ppm | 1536 | 1.033e−15 | 0 | 4.011e−15 | 0 | 1.144e−16 |
| −200/0/+200 ppm | 1536 | 1.063e−15 | 1.301e−16 | 4.362e−15 | 0 | 1.688e−16 |

全係数は事前許容内だった。合成decoded frameは基底入力で各条件7,680枚、計15,360枚を供給したが、実VDIF frameを読んだ枚数ではない。seed電圧によるbufferは別に24回呼び出した。reader差替えは各呼出の範囲で戻し、製品の状態・コードを変更していない。

clock0のraw作用素原点は32標本で、既存049の固定kernelを32＋block×8の位置へ置いたものと一致した。clock傾き変更後の`||H−H0||F/||H0||F`は約0.03327だった。この量は係数行列の差であり、振幅保持率・coherence・推定clockの誤差ではない。

## 4. 既知モデルでの雑音計算

全局・block共分散を`C_ij[a,b]=S_ij Σ_r H_i[a,r] conj(H_j[b,r])`として作り、既存142 helperと直接block対の縮約が一致した。clock0は既存049の全平均/共分散にも一致した。以下は同じ小さい白色Gaussianモデルの**計算値**で、測定された分散ではない。

| clock条件 | channel | 分散 / 名目IID反実仮想の対角比範囲 | clock0との共分散差の規格化最大値 |
| --- | ---: | ---: | ---: |
| 0/0/0 ppm | 3 | 1.000119〜1.000270 | 0 |
| 0/0/0 ppm | 4 | 1.000073〜1.000194 | 0 |
| 0/0/0 ppm | 5 | 1.000119〜1.000270 | 0 |
| −200/0/+200 ppm | 3 | 1.000104〜1.000285 | 0.0090481 |
| −200/0/+200 ppm | 4 | 1.000062〜1.000206 | 0.0016132 |
| −200/0/+200 ppm | 5 | 1.000104〜1.000285 | 0.0090481 |

最後の列は`max(abs(Cvis−Cvis0))/max(abs(Cvis0))`で、全Re/Im visibility共分散同士の比較である。IID反実仮想は、各条件の平均局出力共分散と名目16blockを042へ渡したもの。実効Mや補正係数へ読み替えない。3channelは同じ電圧を共有し、独立な追加観測ではない。

## 5. 正式検証・実行記録

source/nativeの全科学JSONと[53数値配列](../../validation/runs/stage146/arrays.npz)が直接完全一致した。各studyで製品21moduleの正確なsource位置/導入prefixを確認し、nativeはcheckout外・runner/PYTHONPATHなし。外側workflowと再利用した142 helper自体はcheckoutを必要とする。

関連既存46対象はsource3.62秒・導入1.76秒で成功、各90既存警告/除外0、新unitなし。正式手順中はコード・設定・asset等450件を凍結し、初回正式試験/数値手順で完了した。開始前のGit外の凍結manifest作成では`.py`だけを数えて件数assertが停止したため、既存449全項目＋新workflowへ直した。正式処理や科学条件を変えず、記録を保存した。

原本131の76SHA保持、study非上書き拒否2件、138 wheel/source/導入先の製品103file＋4assetの全byte一致を確認した。[正式検証](../../validation/runs/stage146/verification.json)、[科学概要](../../validation/runs/stage146/reference.json)、[資源](../../validation/runs/stage146/measurements.json)を参照。公開監査指摘0、文書リンク1935件で欠落0。

workflow本体wallはsource1.319秒・導入1.333秒、Linux生涯peakRSSは約156.5/157.2MiB。OMP/OpenBLAS各1、各出力16MiB未満。wallはPython/importの起動前を含まず、RSSはimportを含む。単発CPU値で最低PC・全夜/GPUの性能保証ではない。

新full/collect/wheel/導入/browser/画像fitは実行していない。138の両全2321成功542.82/541.45秒・各30220警告/除外0、両実GUI28worker/56downloadは引用のみで新合格へ加算しない。通常GUI138も変更していない。主比較はbinary VDIFを使わず、関連`sample_seek`回帰が作る一時VDIFによる既存codec/seek確認とは分ける。

## 6. 制約・次段階

今回の入力は既知白色電圧で、131の周期帯域制限や量子化を同時に扱っていない。3局/FFT8/16blockの出力は名目62.5µsであり、実131の8局/4ms/1024blockや0.3〜3秒を校正していない。供給clock傾きを使っただけで、未知clock/LO/gain/SEFDの推定、幾何/RF/rate補正、欠損/選別、実FFT独立性、coverage、低SNR画像尤度、実Cas A、全夜GPUは未検証。

[145の八条件](../../interfaces/image-noise-applicability.md)のうち、固定参照と実SampleBufferの時変queryの接続を小条件で進めた。他条件が自動的に成立したとは扱わず、新RML・画像比較・GUI接続は引き続き保留する。147は残る推定依存/採否等を既存rate不確かさ・独立学習参照と照合し、重複しない一条件だけを選ぶ候補で、未実装・未検証である。150の文書整理・専用根本レビューは未実施。期限2026-11-06 15:00JST、追加reset禁止を維持する。
