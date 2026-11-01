# 段階166：16bit公開I/Qと既存整列バッファの限定接続

- 作成日：2026-11-01
- 状態：完了
- 比較元コミット：`8456f0319e440ab2e56d75ded2ef5dd80a692b45`

## 読者向け概要

165の8bit VDIF変換では元電圧に量子化損失が生じた。本段階では元のI/Q各16bitを正確に読み、既存SampleBufferへ渡す検証用リーダーを用意した。SampleBufferは有限長フィルターと分数sample補間を行う部品である。固定した4区間について、順次読込・シーク読込を別々に実行し、直接計算した有限作用と照合した。実時計の推定や二局相関を行ったものではない。

## 1. 目的・対象範囲

実原本の読込時に電圧値を8bit化せず、現在の整列部品へ接続できるかを調べる。新しい[workflow](../../workflows/public_samplebuffer_validation.py)の中だけでreaderを置換し、製品のSampleBuffer/FIR/補間/guardをそのまま用いる。供給20MHzは名目上のidentity mappingであり、実sample時計を測定した値ではない。単局のADC値を用い、複製した局・SEFD・Jy・真値較正を導入しない。

変更はworkflow、本report、[検証案内](../../validation/runs/stage166/README.md)、取得後の実行案内、索引、計画。最新ユーザー指示による既存reset自動使用1回だけの今回限定例外をAGENTSと運用へ記録した。新規購入は許可されていない。これは科学検証の件数には数えない。期限は2026-11-06 15:00JSTのまま。

## 2. 完了条件

実行前に管理外の目的・入力3SHA・許容・時間/byte予算を固定した。原本は[164のCAMRAS単局ci16_le](164-public-single-station-iq.md)と同じ400万complex sample。再取得・再生成・編集をしない。

readerは4000sample/chunk、scale1でint16をcomplex128へ正確に変換する。queryは開始128/3904/2000000/3999000sampleと小数部.25/.75/.25/.75、各256点の固定4区間。各窓で独立したseek true/false bufferを作る8条件とした。読んだ全成分をint16へ厳密一致させ、原本起点のsample indexを保持する。

期待値は146の独立I0/Kaiser tapsを再利用し、NumPyの有限畳み込みと明示sinc/cosine式で計算する。productionのfirwin/lfilter/補間を参照式では呼ばない。taps RTOL1e-11/ATOL1e-12、電圧出力RTOL1e-11/ATOL1e-8 ADC。主8条件のmaskは全True、同窓のseek/順次も一致を要求する。原本外query -1/4000000を拒否し、先頭query0のFIR支持不足はmask=False/値0を要求する。

source/installedで各既存clock4+VDIF5対象、新workflow、上書き拒否を正式選択。全Python431fileを凍結し、科学JSON/全配列・正確な製品module由来/byte・原本SHAを照合する。各worker120秒、import後peak増分64MiB、今回追加保存64MiB、空き10GiB以上、公開text/code512KiB。録音/提供metadata/派生数値データ公開0byte。MC0/MCSE対象外。

## 3. 実際に行った作業

読み取り専用memmapから原本I/Qを読む `RawFrames` をworkflow内に作り、`aligned.iter_vdif_frames` の境界だけを一時的に置換した。SampleBuffer自体のコードは変更しない。シークは4000sample境界へ切り下げ、FIRの前方guardを残す。

reader内で全読込成分の値を元int16へ照合する。参照計算は必要な有限raw範囲だけを畳み込み、フィルター遅延32sampleの補償と補間重みを明示する。全caseの値・参照・query・tapsはGit管理外の17配列に保存した。原本のcapture日時と別名日時はsummaryへ引き継ぎ、意味や精度を解決済みとはしない。

## 4. 検証条件・結果

初回正式選択で両環境とも成功。既存対象は各9成功、source1.12秒/installed0.67秒、各41既存警告、除外0。既存clock solver試験の模擬信号と、今回の公開単局主比較を区別する。主workflowは各8条件、source/installed本体約0.331/0.331秒。実出力と独立有限作用の最大絶対差は約2.3e-13 ADCで固定許容内、seek/順次の値とmaskが一致した。

末尾窓の順次読込では全400万sampleを読み、読込成分は元int16へ全て厳密一致した。同じ末尾窓のseekは4000sampleの1chunkを読む。中間窓は順次501chunkに対しseek2chunk。最大保持bufferは4096sampleで、原本全体を複素配列として保持しない。これは今回の固定窓の値であり、全夜性能ではない。

原本外query2件を指定した理由で拒否、先頭query0はFIR支持不足をmask=False/値0として保持した。両科学JSONと17配列が厳密一致。21製品moduleのsource/installed originとbyte、checkout外native/PYTHONPATHなしを確認した。既存146/周期参照/164のhelperはcheckoutを明示参照し、helperのimportで模擬計算や相関を実行しない。両出力上書き拒否2も成立した。

import時現在RSSから生涯peakまでの増分は18,235,392/18,251,776byteで64MiB以内。今回両出力は119,726byte。失敗保持分を含む原本+164/165/166全studyは48,585,405byte、確認時空き48,080,949,248byte。空き差は環境全体の変動も含む。管理外集計の旧段階から引き継いだfield名を今回追加容量の名称へ訂正し、数値・科学結果を変更していない。

旧165凍結430、原本131の76SHA、151wheelの製品103file+4assetsのsource/wheel/installed全byteを保持。新full/collect/wheel/install/GUI/MC/FX/相関/Closure/RML/画像fitなし。全回帰と両実GUIは[151](151-sequence-capacity-guard.md)の引用であり今回へ加算しない。

公開監査指摘0、文書リンク2248件で欠落0。原本・提供metadata・派生数値配列の公開0 byte、対象外tracked1553fileのSHAを保持。

## 5. 制約・未解決事項

16bit値を保持するのはreader入口であり、FIRと補間の出力は元波形を変える。今回の固定FIRを公開記録の全帯域へ科学的に適用できる条件、実受信帯域のguard、窓特性、実sample時計の精度は未検証。数値作用の一致を実時計較正や情報損失のない整列処理全体と読み替えない。

このreaderはworkflow内のprototypeで、session/CLI/manifestへ製品接続していない。上位InputIdentityの保証にもならない。単局・基線0、実Cas A/未知LO gain SEFD/実FFT独立性/低SNR画像尤度は未検証。受信機チームの構成と保存形式も未決定。通常GUIは既報の接続拒否が継続し、更新・再起動していない。

## 6. 次段階

新しい単局条件の小変更を繰り返さず、複数アンテナの公開rawについて観測ID・取得可能性・最小byte・形式・利用条件を確認する。製品readerを採用する場合は、時計/offset/単位/identity/失敗時出力を含む契約と、新両全回帰/wheel/pipcheck/全byte/checkout外API/両実GUIの正式予算を先に固定する。旧新画像尤度・画像再fit案は保留を維持する。
