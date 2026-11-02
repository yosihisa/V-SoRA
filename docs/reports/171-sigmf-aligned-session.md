# 段階171：SigMF sessionと時計整列相関の接続

- 作成日：2026-11-02
- 状態：完了
- 比較元コミット：`58210144724706586b2f9b8015e7593560bb939a`（文書170、製品169）

## 読者向け概要

168のreaderは一局の16bit I/Qを読み、169の検査CLIは原本と説明JSONの組を識別する入口だった。今回は局ごとの記録をmanifestへ列挙し、供給時計でsample位置と電波の位相を合わせる相関処理へ接続する。8bit変換を挟まず、I/Q整数の値を保って読める。相関後は未較正ADC²で、実電波の画像復元を達成したものではない。

## 1. 目的・対象範囲

明示 `input_format=sigmf_ci16_le` をdirect `correlate-aligned` API/CLIで受ける。全局が限定ci16_le・ADC/scale1、局ID/順序、供給Fs/RF、UTC-Z capture日時と供給clock sample zeroの対応を要求する。供給日時と観測origin＋clock offsetを1ns内で照合するが、実時計精度を測定した意味ではない。名目Fsを未知実clockへ置き換えない。

既定VDIFの数値・契約を保つ。通常correlate/Closure pipeline/sequence/GUIへのSigMF形式接続、新RML/画像尤度・画像fitは対象外。

## 2. 完了条件

実装前に管理外purpose/input SHAへ目的・固定許容・正式予算を記録した。異なる保存模擬4局からの明示SigMFを独立有限作用へRTOL 1e-10/ATOL 1e-7 ADC²で照合する。旧169 installedのVDIF対照へ全保存配列・metadata/summaryを厳密一致させ、新source/installedも全配列を一致させる。局/形式/単位/Fs/RF/epoch/typed clock/原本重複/途中変更/非上書きを確認する。

両新target/collect/full、新wheel/pipcheck/製品全byte/checkout外API・実CLI/両実Chromiumまで正式選択を凍結する。公開はコード・方法/合否の文章だけ。原本・提供metadata・派生数値JSON/NPZ/画像は公開しない。

## 3. 実際に行った作業

| ファイル | 変更 |
| --- | --- |
| `session.py` | 明示SigMF専用station要素、Fs/RF/ADC/局順/実file重複を検査。4096frame制約をSigMFに流用しない |
| `input_identity.py` | InputIdentityを局ごとのmetadata/data pairへ分岐。同一data SHAの局複製も拒否。既存VDIF identity形を保持 |
| `aligned.py` | 供給epoch/clock照合、既存16bit SampleBuffer、積分境界identity、形式別read scope/処理注記を接続 |
| `test_sigmf_session.py` | 20MHz/小数秒epoch/明示rate、契約違反、複製、metadata rehash、途中変更partial等 |
| `sigmf_session_validation.py` | 保存091模擬局からの限定派生と独立畳込み/補間/FFT平均、旧VDIF対照 |
| 契約・案内・索引・計画 | 新入口と実観測の限界、配置/非公開方針を同期 |

詳しい利用契約は[SigMF session](../../interfaces/sigmf-session.md)、[reader/検査CLI](../../interfaces/sigmf-input.md)。data full SHAは各run1回、制御JSON/metadataは境界rehash。全statを保つdata変更は同runで見逃し得る。閉じた入力・信頼されたPython呼出側が前提で、file lock/敵対的filesystemの証明ではない。VDIF direct APIへidentityを追加した結果ではない。

## 4. 検証条件・結果

入力は保存091の相互に異なる模擬4局。元VDIF/sidecar/設定を編集・再生成せず、全SHAを固定した。先頭7有効frameのpayloadから固定式 `2*byte-255` でci16へ写し、別の派生原本として固定した。これは固定71のcode-unit尺度に対応し、元の供給scaleや実ADC/SEFDの較正値ではない。VDIF decoderのfloat32丸めと厳密整数の差を量子化前真値へ読み替えない。

FFT32、blocks128、2積分、開始0.002秒、保存geometry/qualityと明示nominal clockを固定。独立参照はKaiser65tapの直接畳込み、65tap sinc/Hann補間、供給geometryによるRF位相、unitary FFTと平均cross積。Astropy/EOPのgeometry値は共有で、幾何自体の独立検証ではない。新MC試験/MCSEなし。131模擬原本76SHAは保持し、再生成/再相関しない。CAMRAS16MB単局原本3SHAも保持、再取得・変換・相関なし。単局を実基線へ複製しない。

最終attempt3の全正式選択が成功。初回/第二回の成功は合算しない。

| 環境 | 対象成功 | full成功 / collect | full pytest時間 | 既存種別warning |
| --- | --- | --- | --- | --- |
| source | 182 | 2434 / 2434 | 561.65秒 | 30300 |
| installed | 182 | 2434 / 2434 | 569.76秒 | 30300 |

除外/skip0。両studyの独立visibility最大差は約1.1691e-9 ADC²で固定許容内。SigMF/VDIFそれぞれ27保存field（metadataを含む）をsource/installedで厳密一致させ、旧169 VDIFの27fieldと全metadata/summaryにも一致。20製品moduleのorigin/byteを確認した。

新wheel SHA256は `6abe07b794dd4fe5bbfecee21c87b381fbda5154c543b3d4026f8dccc36c1ff1`。105製品file+4assetsのsource/wheel/installed全byte、pipcheck、checkout外helperなしAPIと実CLIが成功。意図した非上書きworker4件は非zero終了で拒否し、既存成果物SHAを保持。両実Chromiumは各28条件/56JSON/672行、JSエラー0/外部通信0、日本語390pxを確認。旧151/168/169 prefixはそれぞれ旧wheel全byteを保持した。

凍結1267file/442Pythonを保持。131原本76SHA、091固定入力とCAMRAS3SHAを保持。製品study追加peakはsource 104824832byte / installed 94797824byteで128MiB内。正式後の管理外保存集計625160283byte、実空き44981309440byteで2GiB追加上限/10GiB reserve内。ダウンロード0byte、公開データ0byte。


### 停止と訂正

- 初回fixture準備は局1の第8frameのinvalid印を検出して停止。全worker終了後、全局の有効先頭7frameへ固定し直した。固定相関範囲は第8frameより前。invalidを有効へ変換していない。初回補助/部分出力を保持。
- 対象試験初回はkeyword-onlyのseek引数を位置渡しして2失敗/28成功（6.86秒）。全終了後に修正し30成功（7.11秒）、追加のmetadata内容検査も含む正式前全対象165成功（9.00秒）。正式成功へ合算しない。
- 製品studyの事前追加peakは104562688byteで当初64MiB超。既存Astropy/EOP/相関と独立作用を含むため、正式前に追加peakだけ128MiBへ改訂した。worker120秒/保存64MiB/全追加2GiB/空き10GiBは保持。system PythonでNumPyを読めない補助停止も残し、依存venvで旧27配列一致を確認。

- 正式attempt1は実行中reviewで、従来VDIFと共通の出力Timeが既定ミリ秒精度となる差を確認して調整役へSIGINTを通知。実行中workerを待ち、全終了後だけSigMF出力を9桁へ設定し、pair内同一実fileの拒否も明示する。初回log/出力/freezeを残し、正式全選択をやり直す。初回の成功を合算しない。初回source全回帰は4失敗/2429成功/30296警告（566.94秒）：既存のraw容量拒否試験stubが新loader keywordを受けないTypeError。全終了後、stubだけ新signatureへ合わせ、同じ4拒否条件を維持して正式対象へ追加した。

- 正式attempt2は両full各2434成功/30300警告の後、階層studyのdirectoryをfileとしてhashする補助不備で停止。全worker終了後に再帰file hashへ修正し、原本/製品は変更せず正式全選択をattempt3で再実行。独立tail補助のprefix記録/変数不足による停止も保存し、正式合格へ合算しない。全体wall予算を7200秒へ改訂し、各attempt3600秒/全追加保存2GiB/空き10GiBを保持。

詳細な方法・実行先は[text validation](../../validation/runs/stage171/README.md)。失敗log/部分出力/freeze/科学配列は全て管理外へ保存する。

公開監査指摘0、文書リンク2307件で欠落0。15fileのstrict allowlistで公開し、対象外tracked1567fileのSHAを保持。原本・提供metadata・派生データの公開0byte。

## 5. 制約・未解決事項

新しい複数局検証は模擬入力であり、実複数受信局の観測ではない。公開CAMRASは410MHz/単局/公称0.2秒で基線0。受信機チームのOCXO/構成/保存形式は未決定のまま。実Cas A・1.42GHz・未知局LO/gain/SEFD・beam/RFI・実FFT独立性・低SNR画像尤度・全夜GPUは未検証。

FIR/補間は波形を変える。構造上のvalidを天体検出やRFI品質としない。雑音差引power比のnull/負/1超の意味も変更しない。既存RMLのw項・固定同種同cell共分散・047JSON/044jointを読まない条件を維持し、相対画像へ精密gain/絶対fluxを一律必須にしない。

通常GUI151の既存prefixは更新・再起動しない。新しい両実GUI検証は保存模擬診断への回帰で、新SigMF入力画面の検証ではない。helperの固定ラベルstage137/production_changed:falseを、171の製品変更なしという意味には使わない。

## 6. 次段階

次は上位Closure pipeline/sequenceが要求する局/単位/clock/原本identityと、今回のdirect入力契約の具体差をreviewする。実接続を選ぶ場合は目的/受入/正式予算を再固定し、実複数局原本待ちだけで監視へ戻らない。観測ID・最小byte・利用条件の新根拠があるときは実アンテナ別電圧の少量取得を別途選ぶ。生成MWA fixtureの再採用や単局複製はしない。同じcodec条件変更を番号のために反復しない。次文書整理180、予定専用根本レビュー200。

172で記録訂正：warning集計補助が先頭file別2816件を拾っていたため、両full footerの30300件へ修正。成功2434/条件/科学配列は変更なし。元logと訂正前管理外記録を保持。
