# 段階165：公開I/Qの供給時刻を保つVDIF限定参照

- 作成日：2026-11-01
- 状態：完了（初回正式手順の停止を保持し、全選択再実行）
- 比較元コミット：`f35a4da404703f203a8cde903b5e44a572c5b2bd`

## 読者向け概要

VDIFは電圧をフレーム単位で保存する形式。164の実記録は20 MHzと小数秒開始のため、現writerの既定条件では保存できなかった。本段階ではフレームを4,000サンプルにすると供給時刻を保てることを確認した。既存の読込処理はその記録を扱える。一方、8 bit化で電圧値は変わるので、形式上の接続成功と、元電圧の保存・科学的な較正を区別する。

## 1. 目的・対象範囲

CAMRAS単局原本の供給Fs・capture epoch・全sample順を維持する検証専用変換を作る。製品write_vdifの整数秒制約とVDIF形式一般の制約を分離する。新規は[workflow](../../workflows/public_vdif_validation.py)、本report、[公開検証案内](../../validation/runs/stage165/README.md)。取得配置案内、索引、計画を更新した。製品・tests・依存・wheelは変更しない。

原本と提供metadataの取得方法・SHA・著者・利用条件は[取得配置案内](../guide/public-voltage-data.md)および[164](164-public-single-station-iq.md)。再取得せず同じ原本を読み取り専用で用いる。元データ、提供metadata、receipt、変換VDIF、科学summary、数値配列をGitへ載せない。

## 2. 完了条件

実行前に管理外の `purpose-fixed.md` と `input-files.json` を固定した。EDV0/complex/8bit成分/1channel/1thread、4,000sample/frame、5,000frame/s、1,000frame、8,032byte/frame。開始frame番号985を供給capture epochから算出する。Fs/epochを置換せず、resample/drop/pad・模擬局複製0。station=1は検証用codec識別子で実局の新しい証拠ではない。

scale=256×35.5=9,088 ADCは全int16範囲から固定し、データ依存AGCやgain調整をしない。153の独立scalar量子化式を再利用し、全400万complex sampleの復号値と800万payload byteを厳密一致。原本に対する最大成分誤差は事前上限129 ADC（半step128にfloat丸め余裕1）以内を要求する。全headerの秒/参照epoch/frame番号はdatetimeと有理数で厳密照合、製品iterator時刻は元epoch+sample/Fsから1 ns以内。既存range読込とnative writerの小数秒拒否も確認する。

source/installed各既存5 VDIF対象と新workflow、上書き拒否、科学JSON/3配列/VDIFの両環境一致、正確module由来/byte、原本SHAを正式選択。source/tests/tools/workflowの430 Pythonを凍結。各worker120秒、import後から追加peak64 MiB以内、原本+164/165保存64 MiB以内、空き10 GiB以上。公開text/code512 KiB以内、録音と派生数値データの公開0 byte。MC0、MCSE対象外。

## 3. 実際に行った作業

Basebandのwriterで元Fsと小数秒epochを受け、読み取り専用memmapから4,000sampleずつ変換する。製品writerを変更せず、`iter_vdif_frames` を使って全復号を読み戻す。EDV0はFsを内部保存しないため外部供給値を使う。

headerはstructで8個の32bit語を読み、秒/refepoch/frame/length/channel/bit数/thread/station/valid/complexを独立に分解。payloadは153のfloat32内部丸め・ties-to-even・飽和・復号の独立式へ照合する。原本と復号の有限誤差はローカルに記述統計として保存した。helperを介してcorrelator moduleもimportするがFXを実行しない。

`start_sample=4001` のrange読込がframe4000へ切り下がることを確認。現write_vdifへ元epoch・20 MHz・4000sample/frameを渡し、`initial adapter requires UTC integer-second start` と出力なしを実APIで確認した。時刻を書き換えて回避していない。

## 4. 検証条件・結果

初回は両study後、実行スクリプトのsource-root確認が `packages/` だけを許し、既存helperがimportする `apps/correlator/` を除外して停止した。初回の全workerは終了してから確認式を修正した。コード凍結、初回ログ、部分出力、実行スクリプトを保持し、選択した両対象試験・両study・両上書き拒否を全て再実行した。初回成功を最終件数へ加算しない。科学workflow/入力/許容の修正はない。

最終source/installed各5対象成功、0.21/0.22秒、各41既存警告、除外0。両study本体約6.68/6.77秒で成功。全400万complex sample（800万成分）が独立量子化式へ完全一致し、payload800万byte、全1000headerの有理数時刻が一致。sample欠落・補間・複製0、最大frame時刻差約9.6 psで固定1 ns以内。これは供給時計上の数値差で、実時計精度ではない。

原本からの最大成分誤差は約128.000022 ADC、固定上限129以内。複素誤差二乗の有限平均は約11,018.88 ADC²、原本/復号の有限平均powerは約149,574.30/159,775.52 ADC²。量子化で平均powerも変わるため、元電圧の完全保存や低SNR科学モデルの成立とはしない。これらは同一有限記録の記述値で、独立雑音分散・SEFD・coherence・confidenceではない。

両科学JSON/3配列/VDIF全8,032,000byteが厳密一致。5製品moduleのsource/installed originと全byte、checkout外native/PYTHONPATHなしを確認。helper二つはcheckoutを明示参照する。既存出力上書き拒否2も最終選択内で成立した。

最終RSSは約81.65/82.06 MB、生涯peakからimport時現在RSSを引いた増分は30,781,440/30,658,560 byteで64 MiB以内。単一プロセスの観察であり全夜メモリではない。失敗出力も含む原本+164/165全studyの実file合計48,465,679 byte、空き48,083,292,160 byte。空き差には環境変動も含む。

旧164凍結429、原本131の76file SHA、151wheelの103製品file+4assetsのsource/wheel/installed全byteを保持。新full/collect/wheel/install/GUI/MC/相関/Closure/RML/画像fitなし。全2328/両実GUIは[151](151-sequence-capacity-guard.md)の引用で今回の合格へ加算しない。

公開監査指摘0、文書リンク2239件で欠落0。原本・提供metadata・派生数値配列の公開0 byte、対象外tracked1552fileのSHAを保持。

## 5. 制約・未解決事項

これは供給Fs/epochを保つ単局codec参照であり、現製品writer・manifest・上位pipeline全体が新profileへ対応したという意味ではない。元の16bitを8bitへ落とす変換をproduction profileにしない。core:datetimeと別名dt:datetimeの意味・精度は未照合、ADC未較正、物理clock/OCXO精度・天体検出・RFI分類は未測定。

単局で基線0。自前RTL-SDR/OCXO、Cas A、未知LO/gain/SEFD、実FFT独立性、低SNR画像尤度を実証していない。受信機構成・保存形式は引き続き受信機チームとの調整対象。通常GUIは既報の接続拒否のまま、再起動・更新していない。

## 6. 次段階

本段階で形式と現writerの制約を切り分けた。次の新作業は原本16bitを保つ主経路の具体的な接続差、またはMWA複数アンテナ電圧の実観測ID・取得可能性・最小byte・利用条件を確認してから選ぶ。同じ単局codec参照の条件変更を自動反復しない。製品変更の場合は両新full/wheel/pipcheck/全byte/checkout外API/両実GUIを含む予算を先に確保する。旧画像尤度・画像再fit案は保留を維持する。
