# 段階179：実数偏波を保持する有界LBA fragment reader API

- 作成日：2026-11-03
- 状態：完了
- 比較元コミット：`4cbea257e17cdf2f594019a1c8af61f4f99b70df`（178）

## 読者向け概要

178で取得した実4局の記録は、1局ごとに2つの実数偏波を保存している。今回の目的は、録音全体を復号して保持するworkflowから、指定した偏波の必要な区間だけを読む製品APIへ進めること。R/L偏波を複素数のI/Qへ置き換えず、実時計やRFをヘッダから推定しない。[API契約](../../interfaces/lba-fragment-reader.md)と[検証手順](../../validation/runs/stage179/README.md)を公開する。

## 1. 目的・対象範囲

旧16byte header、real2pol/2bit/LBASTD little-endian、公称8MHzという確認済みcaseに限定した `LBAFragmentRecording` を追加する。178のheader/decode関数を製品moduleへ移し、既存workflowはimport aliasで同じkernelを使う。別のcodec/identity/sessionを重複実装しない。既存VDIF/SigMF、clock/InputIdentity/SampleBuffer、相関・画像の目的関数や重みは変更しない。

公称時刻の算術整合、fragmentのbyte識別、偏波指定のseek/逐次読込を対象とする。実相関・Closure・画像・解析信号化・新MC trial・新取得は0。製品の実観測相関基線は依然0であり、4局録音を得たこととは区別する。

## 2. 完了条件

実行前に目的・入力SHA・整数厳密一致・時間byte・全正式選択を管理外へ固定した。178の原本4局/receiptと両完成studyを再利用し、各2偏波×2097152sample、計16777216成分をchunk4096で保存levelsへ厳密一致させる。各偏波の固定6seek（計48case）も一致し、最大read32770byteを確認する。MCSEなし。

両新環境の対象/collect/full、新wheel/pipcheck/106製品file+4assets全byte、module origin/byte/依存版、checkout外helper不要API、既存実CLI、両実Chromium28条件を受入とする。旧178全量workflowの10field/科学JSONも保存178へ一致させる。この旧32FFTの回帰を新科学試行へ加算しない。

worker120秒/追加peak256MiB/科学保存各64MiB、full/GUI900秒、attempt3600秒/全attempt7200秒、全追加2GiB/空き10GiB reserve/公開512KiBを固定。正式中source/tests/tools/workflows/helpers/入力は凍結し、全worker終了後だけ修正する。通常GUI151と旧prefixは更新しない。自然回復100%/週間35%をnativeで確認して開始し、追加reset購入使用0。

## 3. 実際に行った作業

- `packages/formats/src/vsora_formats/lba.py`：限定header/復号関数と、fresh fragment SHA・境界検査・偏波明示の有界reader。
- `packages/formats/tests/test_lba_fragment_reader.py`：模擬小fileによるseek/tail/型/範囲/偏波/時刻/期待SHA/変更拒否/全stat保持の反例。
- `workflows/public_lba_fragments.py`：178のkernelを製品moduleから参照する互換変更。
- `workflows/public_lba_reader_validation.py`：変更しない178原本と保存levelsへの全成分/48seek照合。
- 本report/索引、API契約、公開電圧案内、roadmap、validation手順を更新。

constructorで各fragment payloadを1回fresh full hashし、各読込前後に小header内容SHAとresolved path/device/inode/size/mtime/ctimeを確認する。返却codeはDiFX s16規約で物理電圧較正ではない。`actual_sample_rate_hz`、局ID、RF/sidebandは未知として保持する。名目UTC9桁は元header+供給offsetの算術値で、元headerを変更していない。

## 4. 検証条件・結果

入力は178のV177A/2005-03-11/1600-445、AT/HO/MP/PAの共通供給UTC22:08:40.002Z、各1MiB payload。各局2偏波/2097152 time sample、公称8MHz/0.262144秒。PAの記録順L,R、他R,Lを保持する。未取得元member/archiveのfull SHAはnull。新取得/原本生成/変換/実相関/新画像study/MC0（全回帰内の既存画像試験とは分ける）。

固定seekは `(0,1),(1,7),(3,4097),(1023,65536),(1,65536),(2097139,13)`。全16777216成分、8偏波のstream SHA、48seekを保存178 levelsへ厳密一致させた。source/installedの48NPZ field/summary/API JSONは全一致。旧workflowの全10NPZ field/科学JSONは各保存178へ一致し、除外は時間/RSS4fieldだけ。旧32FFT回帰を新科学試行に加算しない。整数厳密一致/MCSEなし。

各descriptorのconstructor payload hashは1回、計4file/4194304byte。summaryのfull_data_hash_*はこのconstructorの計数であり、検証workflow自身の原本再照合を含む総I/Oではない。逐次2偏波+seekは各局1036read/2232360byte、最大read32770byte。source study 0.8220秒/追加peak25583616byte、installed 0.8136秒/追加peak25952256byte。参照配列も読む検証processの計測で、実機throughputではない。

事前初回98成功後、iterator最終guard試験を加えた選択は1失敗/98成功。同tickのpayload書換えが全statを保つ例を検出しなかった。全worker終了後、通常変更testへmtime変化を明示し、別の全stat保持反例は維持して99成功。製品・許容は不変で、失敗log/変更前testを保持し成功を合算しない。管理用usage JSONの初回保存もnullをPython literalと誤用したNameErrorで書込前に停止し、json.loadsへ訂正した。凍結製品/正式helperの変更ではない。

正式attempt1の数値・互換全選択は成功したが、完了後の資源監査で段階directory保存632391917byte+所有pytest一時出力1607033476byte=2239425393byteを確認し、2GiBを少なくとも91941745byte超過した。検査helperがpytest一時出力を除外していた不備。全21worker終了後、成功一時出力だけを削除し、初回全log/科学出力/freeze/wheel/prefix/helpersを `outputs/stage179-formal-attempt1` へ保持した。製品・入力・数値許容は不変。両attempt保存+新pytest一時出力を含む4GiBへ正式前に改訂し、全選択をattempt2で再凍結・再実行した。初回の成功は合算しない。

最終attempt2は両対象104成功/各41既存種別warning、両collect/full各2573成功/各39404既存種別warning/除外0。source 611.71/installed 615.31秒。21worker全終了、非上書き2のreturn1は意図した拒否。checkout外helper不要APIと既存CAMRAS inspect-sigmf実CLIのJSONも一致した。新LBA相関CLIの実装ではない。

新wheel SHA256 `3e7fff5ee9e4d1c3dde07e14dbe637fd8c8a122559c2e17ad53591e52f14adb4`。106製品file+4assetsのsource/wheel/installed全byte、2study module origin/byte、44依存版/pipcheckを確認。両実Chromium各28条件/56JSON/672行、JS0/外部0/日本語390px。保存模擬診断のGUI回帰で新LBA画面ではない。helper固定stage137/production_changed:falseを179製品未変更と解釈しない。旧151/168/169/171/172/173/174/175/176/177 prefixは各旧wheel全byte保持、通常GUI151更新/再起動0。

凍結1285file/459Python/固定入力295、131原本76SHA/CAMRAS3SHA/過去原本を保持。worker境界の保存量最大2871406811byte。top-level CLI JSON/管理journal/公開textも最終監査へ加えた保守上限2872964491byteで4GiB内。連続filesystem peakの測定ではない。全worker終了後、所有を確認した成功pytest一時出力だけを削除し、段階保存1264407309byte/空き40460414976byte（集計時点）。両正式経過2511.27秒で全7200秒内。

公開監査指摘0、文書リンク2391件で欠落0。10fileのstrict allowlistで公開し、対象外tracked1606fileのSHAを保持。原本・提供metadata・派生データの公開0byte。

## 5. 制約・未解決事項

供給公称Fs・元header/offsetを未知実clockへ代用していない。全statを保つraw書換え、最後のguard後の変更、file lock不在/trusted Pythonの限界がある。fresh fragment SHAは未取得元member/archiveのfull SHAやproducer checksum認証でない。最大readはpayload呼出単位の上限で、実機速度や全夜性能の測定ではない。

この限定readerを複素SampleBuffer/session/GUIへ接続していない。R/L偏波をI/Qとせず、LBA長基線・RF・clockを主目標の600m/1.42GHzへ加工しない。天体検出、fringe、実FFT独立性、未知LO/gain/SEFD/beamRFI、低SNR画像尤度、実RTL-SDR/OCXO Cas A画像は未検証。178の配布用途を根拠とするローカル非再配布検証に限り、別個の明示データライセンス未確認を継承する。原本・提供metadata・派生配列/科学JSONのGit公開0。

## 6. 次段階

180は規定の文書整理で技術基準179へ同期する。新数値試験を文書整理に足さない。次の製品作業は実残量を確認し、実数偏波の解析信号化/sideband/実clock/geometryと現相関入力の具体差をreviewして独立受入を固定する。既存readerの小変更や同じFFT/参考画像fitを番号のために繰り返さず、未知実noiseの成立を形式接続で正当化しない。専用根本レビュー150を継承し、予定200を維持する。
