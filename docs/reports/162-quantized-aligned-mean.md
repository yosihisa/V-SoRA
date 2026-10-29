# 段階162：同じ有限電圧を実codecから整列平均へ通す

- 作成日：2026-10-30
- 状態：完了（新しい小模擬VDIFの限定参照）
- 比較元コミット：b6a9beb607b14a5bbb881212a8f6013d58ce8dab（161）

## 読者向け概要

量子化は、連続した電圧値を有限個の整数へ丸める処理です。値が範囲を超えると端の値に切り詰められます。この非線形処理の後に、量子化前と同じ「周波数ごとの電力和」が成り立つとは限りません。

今回は同じ4つの混合電圧を二つの固定scaleでVDIFへ書き、実際に復号してから整列・相関しました。独立に丸めた全復号値と、その波形へ独立係数を作用させた平均が一致しました。**固定した模擬入力の計算参照であり、実機の補正率や雑音モデル、画像復元の成功ではありません。**

## 1. 目的・変更範囲

004/006/014/153/159/161と実VDIF/scale/clip、Basebandのencode/decode/payload/frame一次コード、関連code/test/workflow/validationをreview。014は実codecを通す強い連続波の整列、153は別8probeのcodec/plain FX、159/161はreaderをdecoded frameへ差し替えた参照でした。今回の差は、同時混合3modeの同じ有限probeを、実codecから実整列平均まで通すことです。

新[workflow](../../workflows/quantized_aligned_mean_validation.py)、本report/索引/roadmap/[検証記録](../../validation/runs/stage162/README.md)だけを追加・更新。153の独立scalar量子化、146/152の独立tap・query係数helperを再利用し、helperのrunは再実行しません。製品コード/API/画像尤度/GUIは変更していません。

## 2. 固定入力・受入条件

161で定義済みのcolored配分を事前選択しました。

```text
f/Fs = [-89,25,108]/512、線電力質量=[.1,.3,.6]
符号H = [[1,1,1],[1,-1,-1],[-1,1,-1],[-1,-1,1]]
scale = 1、.125
```

3局/Fs2.048MHz、供給点8×8/64arcsecの(1,6)、固定合成局UVWは `[[0,0,0],[120,35,80],[-90,170,-60]]` m、delay=w/c。時計actual=nominal/offset0、rate0/gain1/受信機雑音なし。元の仮定SEFDは不使用です。記録用観測profileは32×32/16arcsecのまま、供給点形状の解析格子と区別します。

現codecの4096sample/frameに合わせ、草稿のraw512上限を正式選択時に4096へ改訂しました。4probe×3局×2scaleの24新VDIF、8bit複素EDV0/1frame、各8224byte、計197376byte/環境。sidecar24、新保存相関8も作成。131high_aからmetadata2件をSHA固定して借り、原本131の76SHAを保持しました。原本payloadは科学入力に使わず、原本の再生成/再相関はありません。

同じprobe/point/周波数を両scaleで共有し、両環境を含め独立観測数とは数えません。元の符号集合のmean0・二次moment Iは構成上の性質で、pseudo-momentもIのためproper complex/Gaussian標本ではありません。量子化後の統計へその性質を無条件に継承しません。MC0、seed/MCSE対象外。ADC²とnormalized点形状を絶対Jy較正へ変換しません。

全4096sampleの復号値は `array_equal`、補正電圧/局power/vis/有限平均は固定RTOL1e−9/ATOL1e−10で照合。clip率や量子化前後差は全件保存し、差が小さい・改善するという合格条件は設けません。worker120秒/追加保存64MiB/公開512KiB/段階1200秒を固定しました。

## 3. 実APIと独立計算

実write_vdif/read_vdifで全frame復号値、valid、局ID/UTC、sidecarのscale/単位/clipを確認。その新VDIFを実iter_vdif_framesからSampleBufferへ渡しました。**reader差替えはありません。** geometry_at_timesだけを上記固定値へ差し替え、FX subclassは電圧と内部power和を観察するために使います。

実manifest/時計JSON検査、今回の新VDIFのheader/payload decode、FIR状態/guard/補間/RF補正/FX/saveを実行。seek_input=False、FFT8×16block/start96/Fs/span62.5µs。実Astropy/EOP/地理変換精度、guarded seek、上位InputIdentity、未知clock/LO推定、採否、Closure/RMLは主比較外です。通常APIの説明ラベルを、実幾何精度や原本131のheaderを調べた証拠にはしません。

独立scalar式は、float32符号化の中間丸め、ties-to-even、0〜255へのclip、float32復号、供給scaleを明示。全sampleが実codecと完全一致しました。独立146のI0/sinc tap、152の任意query係数で `query=(t-delay)*Fs` と `exp(-2πi RF delay)` を合成し、係数が最初512raw内に収まることを確認。復号後の**全波形**へ作用させ、直接DFT/基線積/16block平均から参照を作りました。量子化後の参照へmode別電力和を流用しません。

SK/RFI選別を同時に変えずspectral_qualityを外し、RF guard重み0を残した全8channel/3基線visを照合。保存weightsでprobe平均を重み付けしていません。局powerはSK無効時に保存診断fieldがないため、実accumulator内部のpower和/countを独立DFTと照合しました。

## 4. 結果・正式検証

| scale | 全probe/局clip率の範囲 | 平均−量子化前平均の相対norm差 | 実平均−独立参照 最大絶対差 |
|---|---:|---:|---:|
| 1 | 0 | .001193349 | 1.987e−15 |
| .125 | .8046875〜.826171875 | .738761256 | 3.377e−16 |

clipは各複素sampleのどちらかの成分が符号化範囲を超えた割合です。固定電圧と二つの供給scaleでの記述であり、実機較正/保持率/coherence/補正係数ではありません。全補正電圧差2.67e−15以下、vis差2.65e−15以下、局power差3.11e−15以下で固定許容内でした。

### 初回・第二回の停止と修正

初回は復号値照合後、UTC文字列の小数3桁と9桁を直接比較して停止。全worker終了後、同じ時刻の差が1ns未満かを比較するよう直しました。第二回は電圧/vis照合後、SK無効時に存在しない `diagnostic_station_power` fieldの参照でKeyError停止。全worker終了後、実accumulator内部のpowerを観察するよう直しました。SK/採用maskを有効化せず、入力/scale/符号/周波数/科学許容は不変です。

両回のlog/部分入力・出力/修正前workflow/凍結をGit管理外に保持し、修正後は選択したsource/installed手順をすべて再実行。初回・第二回のsource対象成功を最終件数へ加算していません。製品側の修正はありません。

最終両14対象、source3.17秒/installed1.52秒、各105既存DeprecationWarning、除外0。警告はBasebandのNumPy shape代入です。対象はVDIF/時計/stream FX/既存実codec整列integrationで、主比較と対象内の模擬VDIFや時計試験を区別します。新unitなし。

全科学JSON/[21配列](../../validation/runs/stage162/arrays.npz)、各8保存NPZの80フィールド(metadata含む)、24VDIF+24sidecarの48file byteが完全一致。21製品moduleの正確source/prefix/byte、native checkout外/runner/PYTHONPATHなし、非上書き2を確認。再利用helperはcheckoutを要する検証依存です。

旧460+newworkflow凍結461、対象外tracked1536、原本13176/入力metadata2/引用29fileのSHA保持。151wheel SHA `c54348ec4b11b89bc70956c2f0d3ad77762b79093ca128834a4bebe053f2b2ec` と製品103+4assetsのsource/wheel/installed全byte不変。study本体wall約.300/.297秒、生涯peakRSS150441984/150945792byte、最終保存418575/419145byte。初回部分10290byte/第二33777byteも保持し、合計64MiB内です。単発wall・生涯RSS・保存量は別の値で全夜/GPU/PC仕様へ外挿しません。公開監査指摘0、文書リンク2207件で欠落0。

[全結果・一次コード/入力SHA](../../validation/runs/stage162/reference.json)、[正式検証](../../validation/runs/stage162/verification.json)。新full/collect/wheel/install/browser/画像fitは実行していません。最新全回帰/wheel/両実GUIは[151](151-sequence-capacity-guard.md)の両2328成功552.61/551.31秒・各30220警告を引用し、今回へ加算しません。通常GUI151も変更していません。

## 5. 制約・次段階

実codecを通したのは、供給scale/clock・固定合成幾何・有限混合probeの新しい小模擬入力です。153/159/161の別条件を、全主経路や未知実観測の成功へ合成しません。連続PSD積分、量子化後noise共分散/coverage、実131の8局4ms1024block/短積分は未校正です。

八条件、実Cas A、未知実LO/gain/SEFD、beam/RFI、実FFT独立性、低SNR画像尤度、全夜GPUは未検証。新production尤度/RML/画像再fit/GUI、外部追加反復、truth係数調整、Windows収録は保留。

次163は、同pilot推定と採用gateに新しい識別可能な対照があるか、040/042/098/101/107/143/144/147/154等を先にreviewする未選択候補です。147/154の再集計だけなら重複せず改訂し、識別不能な効果を未識別として残します。実入力新回答を優先し148照会は繰り返しません。次文書整理170/予定根本レビュー200、前提が崩れれば前倒しします。
