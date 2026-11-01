# 段階168：16bit公開原本を直接読む限定SigMF入力API

- 作成日：2026-11-01
- 状態：実装・正式検証完了
- 比較元コミット：`a1c6fb03c897ea480ce33a34e5ba0cb68c7907ce`

## 読者向け概要

SigMFはIQ標本の本体と、標本化周波数・記録時刻などの説明を別ファイルで保存する形式である。166のworkflow内reader置換を、限定した製品APIへ置き換えた。元の16bit整数を8bitへ変換せず読み、既存FIRフィルター・補間へ直接接続できる。単局の入口の検証であり、実複数局の相関やCas A画像の実証ではない。

## 1. 目的・対象範囲

`SigMFRecording` と `SampleBuffer.from_sigmf` を追加する。ci16_le・単一channel/capture・先頭offset0・明示UTC-Z時刻・正の有限Fsに限定し、未対応構成を拒否する。既定VDIF経路とFIR/補間式は維持する。session manifest・相関CLI・GUIへ形式を追加しない。[限定契約](../../interfaces/sigmf-input.md)と[取得配置案内](../guide/public-voltage-data.md)を用意した。[公式SigMF仕様](https://sigmf.org/)の全仕様対応や準拠認証は主張しない。

## 2. 完了条件

実行前に目的/範囲/入力3SHA/許容/時間byteを `outputs/stage168-preparation/purpose-fixed.md` へ固定した。製品変更として両新全回帰・wheel/pipcheck・全製品byte・checkout外API・両実Chromiumを選択。原本800万成分を独立byte復号へ厳密一致、供給時刻を独立計算へ1ns以内、166固定4窓×seek/順次8条件を独立有限作用へRTOL1e-11/ATOL1e-8 ADCで照合する。MC/MCSEは対象外。

正式中1262file（Python437、管理外実行補助2を含む）を凍結。段階3600秒、全回帰/GUI各900秒、原本study各120秒、追加保存2GiB、study追加peak64MiB、空き10GiB以上。公開は文章/コード512KiB以内、原本・提供metadata・派生波形/配列/図0byte。

## 3. 実際に行った作業

- `packages/formats/src/vsora_formats/sigmf.py`：最大1MiBのmetadata、重複key拒否、1〜65536sampleの有界読込、最終短chunk保持、sample index/供給時刻、dataのstat変化/短read検出。
- `apps/correlator/src/vsora_correlator/aligned.py`：明示SigMF入口。actual_rateは呼出側が供給し、正の有限値・名目Fsから±1000ppm以内（両端を含む）を要求。
- `packages/formats/tests/test_sigmf.py` と `apps/correlator/tests/test_sigmf_samplebuffer.py`：新64件。成分/時刻/seek/末尾/不正metadata/範囲/clock入力契約/初期guardを確認。
- `workflows/public_sigmf_api_validation.py`：実製品APIを通す原本照合。166 helperは独立参照の計算だけに使い、readerの置換はしない。
- interface・取得案内・report/検証案内・索引/計画を更新。AGENTS/運用にはユーザー手動resetで今回1回の承認が充足され、追加自動使用をしないことを反映。

旧通常GUI151用prefixを変更せず、独立 `outputs/stage168-installed-venv/` に新wheelを導入した。regular file inode共有なし、45 distributionの依存版は同一、新規依存追加0。

## 4. 検証条件・結果

164で取得済みのCAMRAS単局Crab原本16,000,000byte・400万complex sample・供給Fs20MHz・中心410MHz・capture `2024-07-30T09:19:20.197000Z`、未較正ADCを使用。再取得/再生成なし。raw SHA256 `e12a408af4d963802623a95ee732c20b0b6b0cbf787454f5b10753d6d04f992e`、metadata SHA256 `42878700f4cc91c4cda249ec1d958cea6c7e78fc1b13f3af714f654956f4f188`、receiptも実行前SHAを保持した。

| 正式項目 | source | 新installed |
| --- | --- | --- |
| 対象試験 | 120成功、2.74秒、2947警告 | 120成功、2.66秒、2947警告 |
| 実collect/全回帰 | 2392収集/2392成功、541.54秒 | 2392収集/2392成功、543.40秒 |
| 全回帰警告 | 30220 | 30220 |
| 全800万成分の独立復号 | 厳密一致 | 厳密一致 |
| 原本study本体時間 | 0.6994秒 | 0.6786秒 |
| import後current RSSからの保守的peak差 | 2,613,248byte | 2,359,296byte |
| 実Chromium | 28条件/56 JSON保存一致 | 28条件/56 JSON保存一致 |

除外0。警告は既存basebandのNumPy shape設定DeprecationWarningとしてlogへ保持。既定4096sampleで977chunk、末尾2304sampleを保持し、時刻差最大約2.991psは固定1ns内。独立FIR/補間との最大差約2.292e-13 ADC。source/installed/166保存結果の17配列は厳密一致。同じ原本・窓の経路比較であり、独立実観測試行を増やしたとは数えない。

新wheel SHA256 `d3046ff70ae8e39a508b5d6d61f99fa1601d268216ffcad631709a4d7913978a`。source/wheel/新installedの104製品file＋4assetsを全byte照合。studyの21moduleのorigin/byteを確認し、helper不要API probeもcheckout外/PYTHONPATHなしで成功。pipcheck成功、上書き拒否2で保存出力不変。旧151 prefix103製品file＋4assetsと131模擬原本76SHAを保持した。

両ブラウザは専用serverで新規実行し終了した。各672基線行、null50/負174/1超148、全JSON、日本語font・390px・表折返しを確認、JavaScript error/外部通信0。再使用helperの固定 `stage:137` / `production_changed:false` は保存診断helperのラベルで、本168の製品変更がないことを意味しない。通常8765は既報の接続拒否状態で更新/再起動なし。

補助準備でsystem Pythonを使い、GUI入力SHAの重複索引作成がhttpx不足で失敗した。コード/原本の凍結はその前に完了し、GUI入力は凍結済み135/136参照SHAを工具が前後照合していた。正式コードは変更せず、全worker終了後に正しい環境で28条件/10入力の補助索引を追補。準備失敗を保持する。正式選択は初回全項目成功、別実行の成功を合算していない。

追加保存585,128,366byte、検証後空き46,276,235,264byteで上限内。既存失敗出力も削除していない。詳細の再現条件と管理外logの所在は[検証案内](../../validation/runs/stage168/README.md)を参照する。

公開監査指摘0、文書リンク2264件で欠落0。13fileのstrict allowlistで公開し、対象外tracked1557fileのSHAを保持。原本・提供metadata・派生データの公開0byte。

## 5. 制約・未解決事項

actual_rateへ供給Fsを入れた名目identity mappingで、実時計の測定ではない。別欄 `dt:datetime` の意味/差、実UTC精度、物理帯域guard、天体検出は未検証。validはbyte復号成功だけでRFI/受信機品質を表さない。annotations/任意拡張は未解釈、SHA512は自動検証しない。stat検出は暗号学的原本同一性ではなく、InputIdentityは上位pipeline/sequenceの別機能である。

入口の追加量子化0でもFIR/補間は波形を変える。単局/実基線0/局複製0。実複数局LO/gain/SEFD・相関/Closure/Cas A画像・低SNR画像尤度を検証していない。134/145の八条件や162/163の限定モデルを実入力で成立済みと扱わない。

## 6. 次段階

実複数アンテナ電圧の取得可能な個別ファイル・出典・最小byte・利用条件がそろう候補を優先する。session/CLI接続を選ぶ場合も局/時刻/帯域/単位/原本同一性の具体的契約と正式予算を先に固定する。単局の小変更反復や生成fixtureの実観測扱いを避け、旧画像尤度/画像再fitは保留。次の文書整理170。
