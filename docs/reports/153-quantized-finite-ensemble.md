# 段階153：量子化前後の固定電圧集合の平均と共分散

- 作成日：2026-10-29
- 状態：完了（限定した決定論的codec・FX参照）
- 比較元コミット：e2fc82359328628e52c371d23cb57b79cc7848d0（152）

## 読者向け概要

量子化は連続した電圧を有限個の数値へ丸める操作です。大きな値は上限へ張り付きます。152は復号後の電圧から整列結果を照合しましたが、復号前後の電圧が同じとは確認していません。今回は同じ8種類の電圧を二つのscaleで保存し、実codecを通した相関の平均と共分散が、仕様から直接計算した値へ一致することを確認しました。実受信機の補正係数を得た段階ではありません。

## 1. 目的・対象範囲

[004](004-vdif-fx.md)には量子化幅以内の誤差と平均相関の照合があり、[061](061-streaming-bispectrum-sums.md)にはdecoded FFTの追加統計の照合があります。[006](006-casa-compatibility.md)はCASA互換でありcodecの独立統計検証ではありません。これらを再実行せず、未接続だった**固定した同じ集合の量子化前後の全channel平均・全ReIm共分散**だけを選びました。

製品変更なし。新規 `workflows/quantized_ensemble_validation.py` と本レポート、索引、roadmap、[小容量記録](../../validation/runs/stage153/README.md)を追加・更新しました。新API、尤度、画像weight、実効M、GUIの変更はありません。

## 2. 完了条件

実行前にGit外の正式目的へ入力・scale・許容・失敗条件を固定しました。実write/readで得る全sampleを、scalar Python roundによる符号化とfloat32復号の独立参照へ完全一致させます。全channel FXは独立DFT直接和とRTOL1e-9/ATOL1e-10で照合。8probeを同じ確率とみなした有限平均と、分母8の全ReIm共分散を直接outer和と行列積で照合します。不偏標本共分散や推定誤差のconfidenceではありません。

source/installedの全JSON・配列・小VDIF/sidecar、正しい製品module位置/byte、非上書き、既存原本/製品の保持を確認。関連targetのみ両環境で実行します。各worker120秒、追加64MiB/環境、公開512KiB、段階1200秒以内。MC0、seed/MCSEは対象外です。

## 3. 実際に行った作業

2局・各4096sample（1frame）・Fs2048000・FFT8・512block。probe位相p=2πk/8（k=0..7）、振幅1+.15cos(p)。入力はこの振幅に `exp(i(2π*.03125*n+p))+.3exp(i(2π*.1875*n-2p))` を乗じ、局gainを1と.83exp(.6i)へ固定。scale1と.125で同じ入力を共有します。既知の有限集合であり、GaussianやIID標本を生成していません。

UTCは2026-10-02T08:00:00Z、station1/2、全valid、供給ADC単位。実codec/保存/全frame読取り/plain FXを使用。各環境32VDIF、32×8224=263168byte。131の固定原本を再生成せず、小さい別の模擬入力だけを作りました。実Basebandのencode/decodeとフレーム代入の一次コードを読み、[参照行範囲SHA](../../validation/runs/stage153/reference.json)を記録しました。

## 4. 検証条件・結果

[正式結果](../../validation/runs/stage153/verification.json)と[条件・数値](../../validation/runs/stage153/reference.json)。最終source/installedは**各9対象成功、各73既存警告、各0.31秒、除外0**。studyの親計測wallは約.47/.52秒。新unit、full、collect、wheel作成、install、browser、MC、画像fitは行っていません。

| 条件 | clip比の範囲 | 全channel FXの最大絶対差 | 平均差のノルム比 | 共分散差のノルム比 |
|---|---:|---:|---:|---:|
| scale1 | 0 | 3.45e-15以下 | .00258124 | .01332290 |
| scale.125 | .9375〜1 | 4.45e-16以下 | .67039412 | .99575381 |

右二列は量子化後−前のノルムを量子化前のノルムで割った記述値です。clip比は各sampleのIまたはQが規定範囲を超えた割合。振幅保持率/coherence/実機較正/画像誤差ではありません。clipなしでも丸めによる差があり、decoded線形処理の一致を量子化前の平均モデルの一致へ変換できません。

全科学JSON・13数値配列が完全一致。32VDIF・32sidecar・summaryの65file/環境がbyte一致。5製品moduleの正確source/prefixとbyte一致、nativeはcheckout外/runner/PYTHONPATHなし。非上書き2で既存出力byte保持。各出力292200/292338byte、初回部分出力8724byteで上限内です。

既存452凍結+新workflow=453、原本131の76SHA、対象外tracked1484、引用9fileを保持。151wheel SHA `c54348ec4b11b89bc70956c2f0d3ad77762b79093ca128834a4bebe053f2b2ec` と製品103file+4assetのsource/wheel/installed全byteが不変。公開監査指摘0、文書リンク2077件で欠落0。

**失敗と訂正。** 初回source target成功後、最初のVDIF復号比較で187/4096箇所が不一致でした。参照は符号化中間値をfloat64で計算し、実フレーム代入経路のfloat32演算を欠いていました。微小な負値の符号化境界で差が現れました。全worker終了後に新workflowの参照だけを訂正。入力/scale/反復/許容は変えず、初回log/VDIF/凍結manifestを保持して両環境の全選択を再実行しました。初回target成功を最終件数へ足していません。

再実行の両target/両study成功後、Git外runnerの非上書きprobeに旧`--raw-reference`引数が残り、argparse拒否を期待のFileExistsErrorと比較したassertで止まりました。科学workflowは変更せず、後処理だけ正しい引数で実行。科学計算の成功を重複計上していません。

## 5. 制約・未解決事項

有限8probeの電圧と供給scaleに限る結果です。float32精度も導入codecの実経路に対応させた参照であり、外部codec/実ADC・I/Q配線・受信機の線形性や未知scaleを独立較正していません。`vis_jy`は既存key名ですが、今回の値の単位はADC²です。共分散は相関値のReImの有限集合共分散で、SEFDや画像尤度の共分散ではありません。

FIR/補間/整列/幾何/RF-rate位相/未知推定/観測SNR選別/Closure/RMLは今回の主比較外です。152とは入力・経路が異なり、二つの限定成功を全主経路の統計較正へ合成しません。[145の八条件](../../interfaces/image-noise-applicability.md)は未成立です。実Cas A、未知実LO/gain/SEFD、beam/RFI、実FFT独立性、低SNR画像尤度、全夜GPUは未検証。

最新全回帰/wheel/両実GUIは[151](151-sequence-capacity-guard.md)の引用です。両2328成功552.61/551.31秒、各30220警告を今回の新試験件数へ足しません。通常GUI151は変更せず、更新のための停止・再起動もしていません。

## 6. 次段階

次154は、147で混在した同pilot推定と採用gateの影響を、既存solver/graph/051の意味を先にreviewして限定する候補です。143/147と同じ比較を増やさず、成立しない識別を補正係数で埋めません。実入力の新回答があれば優先します。残量が10%に近づくため、今回完成後は通常reset後の実回復を待って選択します。追加resetの購入・使用はありません。150根本レビューは完了済み、次160文書整理/予定200根本レビューです。
