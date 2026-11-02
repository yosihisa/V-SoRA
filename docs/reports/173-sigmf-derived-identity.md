# 段階173：SigMF派生sessionの識別再利用

- 作成日：2026-11-02
- 状態：完了
- 比較元コミット：`818aa4ab0047ae398aba8276a9e4cb9b3a9a1b63`（172）

## 読者向け概要

172のSigMF pipelineは、元入力とpilot・最終相関で同じdataを計3回full SHA256で読んでいた。原本が長くなるとこの重複読込は容量に比例する。今回は最初のfreshな識別情報を、元入力との対応を検査した派生sessionへ再利用する。相関値・rate・weight/flagは変更せず、ファイルを変更不能にする仕組みや実機速度の測定を追加するものではない。

## 1. 目的・対象範囲

親InputIdentityと2つのguarded view（再利用元を検査する派生識別）で、同じ逐次runのfull data hashを3回から1回へ減らす。既定のdirect APIは毎回fresh hash。private `_source_identity` にlive親を明示したSigMFだけがviewを使う。VDIF、共有sequence、画像/RML、保存形式/時計モデルの追加は対象外。

## 2. 完了条件

実装前にpurpose/入力SHA/変更許容/予算を管理外へ固定した。子は同じresolved clock・同じ局順/ID・同じresolved metadata/data pairだけを許す。変更可はblock数とcontrolの配置/path表記だけで、その他のFFT/Fs/unit/geometry/quality等は型を保つcanonical JSON一致を要求する。親と子のsmall metadata/controlを境界で再hashし、全stat検査を維持する。

固定172の同じ入力で、digest_file実呼出のraw4file×3=12回を4回へ減らすこと、全数値/科学metadata不変、旧VDIF全field不変を確認する。新source/installed全field一致、新両target/collect/full/wheel/pipcheck/全byte/checkout外API/実CLI/両実Chromiumまで正式検証する。原本・提供metadata・派生数値はGitへ出さない。

## 3. 実際に行った作業

| ファイル | 変更 |
| --- | --- |
| `input_identity.py` | live親からの派生view、child controlのfresh SHA、親/子境界検査と対応拒否 |
| `aligned.py` | 型を検査するprivate親引数、既定freshと派生viewを分離 |
| `closure_pipeline.py` | SigMF pilot/finalへ同じ親を明示し、data hash合計1passを記録 |
| `test_sigmf_identity_reuse.py` | 実hash回数、親/子変更、型/clock/pair/config拒否、盲点、積分中の親検査 |
| `test_sigmf_pipeline.py` | 既存2rate modelのhash契約を新1passへ厳密更新 |
| `sigmf_identity_reuse_validation.py` | 固定172比較、hash実呼出、保持した独立作用を再利用 |
| 契約/案内/索引/計画 | 対応範囲、過去172の3passと新1passを区別 |

詳しくは[契約](../../interfaces/closure-pipeline.md#同じrunの派生identity173)、[SigMF入口](../../interfaces/sigmf-session.md)。子は小ファイルをhashしてからparseし、後で再hashして内容とloaded configを結びつける。子自身のmanifest/clock/観測config SHAを保存し、pair SHAは親から引く。親を各direct積分境界でも検査する。

## 4. 検証条件・結果

172の固定入力と両完成studyを全SHAで再利用した。新しい原本/変換/取得は0。保存038由来の異なる模擬4局、70有効frame、固定 `2*byte-255` code-unit尺度、Fs2.048MHz/各286720complex sample/公称.14秒。元の供給scale/物理ADC/SEFDの較正ではない。FFT32/pilot128blocks×64/start.002/final.1/max100Hz/constant/raw U3を維持する。131の76SHA、CAMRAS3SHA、038/091/171/172原本・参照を保持し再生成/再相関しない。CAMRAS単局を複製しない。

比較除外を事前固定した追跡情報はinput_identity/input_identity_diagnostics、input_sha256、rate_only_profile_sha256、visibility_sha256、raw注記のrate_profile_sha256。圧縮metadataの変化でraw_bispectrum.bytesも変わるため、この値だけは新旧それぞれ実file statへ照合してから比較対象外とする。その他のbytesや科学fieldは除外しない。

事前第三回studyではraw full hash実呼出4回/4587520byte。172の12回/13762560byteに対して9175040byte分を除いた。これはhash読込だけで、波形読込を含む全I/O量や実機速度とはしない。SigMF39非metadata field・3科学metadata・8JSON、VDIF全42field・8JSONを保存172へ照合した。保存推定rateと共有geometryを条件に172の独立有限作用を再利用し、visibility最大差は約2.3554e-12 ADC²でRTOL1e-10/ATOL1e-7内。同じ有限標本で独立実観測試行ではなく、rate推定bias/coverage/EOP/画像尤度の校正ではない。

事前対象初回24成功（7.79秒）、正式前全対象134成功（94.74秒）。型/clock/pair/FFT/unit/geometry/quality変更、子JSON変更、親metadata変更、symlink置換、ordinary raw変更、別run fresh hashと積分中の親検査を確認した。全stat保持raw変更の意図した見逃しも明示試験した。truthへ係数/格子/weight/mask/seedを合わせない。

正式attempt1の全選択が成功。事前studyの停止前の成功は合算しない。

| 環境 | 対象成功 | full成功 / collect | full pytest時間 | 既存種別warning |
| --- | --- | --- | --- | --- |
| source | 134 | 2459 / 2459 | 561.60秒 | 32332 |
| installed | 134 | 2459 / 2459 | 563.04秒 | 32332 |

除外/skip0。両studyでraw full hash実呼出4回/4587520byteと子のdata新規hash0を確認。新source/installedはSigMF/VDIF各42fieldを全て厳密一致。保存172 SigMFには39非metadata field・3科学metadata・8JSONを一致させ、VDIFは全42field・8JSONを厳密一致させた。固定した追跡値だけが変わり、独立有限作用への最大差は約2.3554e-12 ADC²で許容内。

新wheel SHA256は `a1a463fc77e9ad3f41ea17d1f47863b11d7843d2a8b4a483a532f922ba0f39b8`。105製品+4assets全byte、22study module origin/byte、pipcheck、checkout外helperなしAPI/実CLIが成功。非上書きworker4件の非zeroは意図した拒否で既存成果物SHAを保持。両実Chromiumは各28条件/56JSON/672行/JS0/外部0/日本語390pxを確認。旧151/168/169/171/172 prefixを各旧wheel全byteと照合した。

凍結1272file/447Pythonと全固定入力、131原本76SHAを保持。製品study追加peakはsource 137900032byte / installed 104669184byteで256MiB内。正式後管理外保存集計618698679byte・実空き43466022912byteで全追加2GiB/空き10GiB reserve内。新取得/原本変換0、公開原本/metadata/派生データ0byte。


### 正式前の停止と訂正

初回study補助はNPZのmetadata keyをmetadataと誤記し、metadata_jsonの追跡SHAを配列として厳密比較して停止した。全worker終了後、事前固定の追跡値だけを除くmetadata_json比較へ訂正。第二回はraw_bispectrum.bytesが16595→16599となりsummary比較で停止した。圧縮済み追跡metadataによる実byte数の変化として正式前に許容追跡範囲へ追加し、新旧とも実file statに厳密照合した。原本/製品/数値許容は変えず、初回/第二回のlog・部分出力・旧補助を保持して新出力へ全studyを再実行した。失敗前の成功を最終件数へ加算しない。

[text validation](../../validation/runs/stage173/README.md)に方法を記載し、log/freeze/科学JSON/NPZは管理外へ保持する。

公開監査指摘0、文書リンク2329件で欠落0。13fileのstrict allowlistで公開し、対象外tracked1578fileのSHAを保持。原本・提供metadata・派生データの公開0byte。

## 5. 制約・未解決事項

同じrunの閉じた入力・逐次処理・信頼されたPython呼出側が前提。永続cache、file lock、任意Python/敵対的filesystemの証明ではない。dataが全statを保持して変更されると同runで見逃す限界は残る。別runでは親を新規構築しfresh full hashする。metadata/controlはstatが同じでも内容SHAで検査する。

実Cas A/未知実LO・gain・SEFD/beamRFI/実FFT独立性/低SNR画像尤度/全夜GPUは未検証。新studyの画像fit/MC study/実基線0であり、既存全回帰の画像試験と分ける。RMLのw項・固定同種同cell共分散・047JSON/044jointを読まない条件は変更しない。相対画像へ精密gain/絶対fluxを一律必須にしない。

通常GUI151を更新/再起動しない。両実GUIは保存模擬診断への回帰で新SigMF入力画面の検証ではない。helperの固定stage137/production_changed:falseを173製品未変更とは解釈しない。

## 6. 次段階

同一runの派生識別が複数窓で使える条件と、SigMF sequenceへ残るFFT grid/窓間原本一致/容量/画像への接続をreviewする。新画像fitや新入力を選ぶなら目的/独立受入/正式予算を再固定する。形式・I/Oの接続を実観測画像成功とせず、番号のための小codec反復や不足文書を増やさない。文書整理180/予定根本200を維持する。
