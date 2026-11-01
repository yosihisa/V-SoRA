# 段階169：SigMF原本pairの同一性と実検査CLI

- 作成日：2026-11-02
- 状態：実装・正式検証完了
- 比較元コミット：`6648b980db611049ac2d356b14fc1afc731e153e`

## 読者向け概要

168では実IQを16bitのまま製品APIで読めるようにした。次に必要なのは、実行した原本本体と説明metadataを組で識別し、再実行時に別のbyteを混ぜないための入口である。SHA256はfile全byteから計算する識別値で、時計精度や天体信号の品質を測る値ではない。この段階では新しい検査CLIと明示的な原本pair identityを追加し、期待する両SHAへの照合と上書き拒否を接続する。

## 1. 目的・対象範囲

`SigMFInputIdentity` と `vsora-correlate inspect-sigmf` を追加する。168の限定SigMF profileを使い、metadata/dataを各runでfresh hashし、供給Fs・capture日時・RF中心・ADC単位を表示する。station IDは作らない。既存VDIF用InputIdentityとpipelineを変更せず、session/相関処理のSigMF入力形式追加とは区別する。

契約と実行例は[限定SigMF入力](../../interfaces/sigmf-input.md)と[取得配置案内](../guide/public-voltage-data.md)へ記載した。

## 2. 完了条件

実装前に `outputs/stage169-preparation/purpose-fixed.md` へ、原本3SHA・受入・予算・全失敗の扱いを固定した。fresh pair SHA/byteと供給項目を独立hashlib/JSON読取へ照合し、API/CLI/source/新installedの決定的JSONを一致させる。期待SHAは両指定のみ、不正/片方/不一致を失敗にする。既存出力・原本を上書きしない。

新source/installed collect+全回帰、wheel/pipcheck、全製品file＋4assets、checkout外helper不要API/実CLI、両実Chromium28条件/56JSONを選択した。正式中1265file/Python440（管理外runner2を含む）を凍結。全worker終了後だけ修正し、正式失敗は全選択再実行とする。

段階3600秒、各full/GUI900秒、原本study/CLI120秒、copy/build/install180秒、追加保存2GiB、study追加peak64MiB、空き10GiB以上。公開文章/コード512KiB以内、原本・提供metadata・派生波形/配列/JSON/図は0byte。MC/MCSE・新相関/Closure/画像fitは対象外。

## 3. 実際に行った作業

- `apps/correlator/src/vsora_correlator/input_identity.py`：閉じたSigMF pair用の別classを追加。既存snapshot/digest関数を再利用し、構築前後と境界でresolve/device/inode/size/mtime/ctimeを照合する。小metadataは境界ごとに再hash、raw全hashは各instanceの構築時1回。同じ実fileへaliasするpairは拒否する。返却dictはcopy。
- `sigmf_inspect.py` と既存 `__main__.py`：期待する両SHAへのfresh照合、限定profile/byte/供給項目のJSON、既存出力拒否。期待値なしは照合未評価null、実clock・生産者checksum照合はfalse。ローカルpathや提供metadata全文は出力しない。
- `apps/correlator/tests/test_sigmf_input.py`：新22件。fresh hash、変更/削除/置換/symlink、metadata内容検査、返却copy、期待値エラー、既存出力/原本の保護、CLIを確認。
- `workflows/public_sigmf_identity_validation.py`：CAMRAS実原本のpairを独立hash/供給JSONへ照合し、境界ごとのraw再hashなしと別instanceでの新hashを確認する。実波形の再復号や科学統計を追加しない。
- interface、取得配置案内、本report/検証案内、索引、計画を更新。

新installedは168 prefixから独立copyした `outputs/stage169-installed-venv/`。旧168と通常GUI151用prefixを更新しない。依存追加/版変更は行わない。

## 4. 検証条件・結果

入力は164で取得済みのCAMRAS単局Crab原本16,000,000byte、ci16_le・400万complex sample・供給Fs20MHz/中心410MHz。raw SHA256 `e12a408af4d963802623a95ee732c20b0b6b0cbf787454f5b10753d6d04f992e`、metadata SHA256 `42878700f4cc91c4cda249ec1d958cea6c7e78fc1b13f3af714f654956f4f188`。receiptを含む3SHAを固定し、再取得/変更なし。期待値は初回取得byteの識別で、生産者の公表checksumや認証ではない。

### preformalの失敗と検出限界

最初の対象試験は1失敗/97成功・1720警告・7.82秒。同sizeのrawを書換えてmtimeを戻したが、ctimeも同じfilesystem tick内に保たれ、検出を要求した試験が失敗した。8合成例の確認でも7例は全statが同じだった。この事実を保存し、rawを毎境界再hashする仕様へ密かに変えず、同instanceでのstat検出の限界として明記した。検出試験は20ms後のctime変化を確認してから判定する条件へ修正し、対象98件が7.17秒で成功した。metadataは全statが同じでも内容SHAで検出する試験を含む。

補助診断の初回 `tools/run.py -c` は非対応で開始前に失敗し、正しいPython/source-path指定でやり直した。初回preformalはstdout fileを指定しておらず、捕捉した工具出力の失敗traceを転記して保存した。両失敗の要約・trace・後続の属性確認を管理外に保持する。いずれも正式結果や独立科学試行へ合算しない。

### 正式結果

| 正式項目 | source | 新installed |
| --- | --- | --- |
| 対象試験 | 98成功、8.31秒、1720警告 | 98成功、6.58秒、1720警告 |
| 全回帰（実collectも同数） | 2414成功、565.04秒、30220警告 | 2414成功、562.00秒、30220警告 |
| 原本study本体（import後） | 0.02261890098452568秒 | 0.02325073501560837秒 |
| import後current RSSからの保守的peak差 | 262144byte | 262144byte |
| 実Chromium | 28条件/56 JSON | 28条件/56 JSON |

除外0。全回帰の警告は既存basebandのNumPy shape設定DeprecationWarningとしてlogへ保存した。両API検査JSON/summaryとcheckout外実CLIのJSONは厳密一致。fresh期待SHA照合、既存出力拒否2、SHA不一致拒否2、workflow出力再使用拒否2を確認した。拒否の6非zeroを失敗と取り違えず、全正式選択は初回成功。preformal成功を合算していない。

新wheel SHA256 `7f3ad310e137294c26c83a4629ab3ab869c1061766f2db7f0a37ab8bb8a5c9cb`。source/wheel/新installedの105製品file＋4assetsを全byte照合し、study15moduleのorigin/byte、checkout外helper不要API、pipcheck、45 distributionの依存版同一を確認。旧168 prefix104file＋4assets、通常GUI151用prefix103file＋4assetsと131模擬原本76SHAを保持した。

両実ブラウザは各672基線行、null50/負174/1超148、全JSON、日本語font・390px・表折返し、JavaScript error/外部通信0を確認。検証helperの固定stage137ラベルは再使用toolのラベルで、169未変更を意味しない。専用serverは終了し、通常8765の既報の接続拒否を更新/再起動していない。

追加保存584,980,388byte、検証後空き45,662,162,944byteで上限内。原本の追加取得0、出力JSON/提供metadata/波形/画像の公開0byte。

詳細の再現方法と管理外logの所在は[検証案内](../../validation/runs/stage169/README.md)を参照する。168の800万成分/17配列一致は引用で、今回の新しい復号・独立実観測成功へ加算しない。

公開手順初回は補助scriptのreport参照が旧168のままで、コミット前のassertで停止した。製品/試験コードや旧168reportは変更せず、公開補助の参照だけを訂正して監査から再実行した。正式検証の失敗や再実行とは区別し記録を保持する。

公開監査指摘0、文書リンク2273件で欠落0。11fileのstrict allowlistで公開し、対象外tracked1564fileのSHAを保持。原本・提供metadata・派生データの公開0byte。

## 5. 制約・未解決事項

閉じたfileと信頼されたPython呼出側が前提。dataの全stat保持変更は、同instanceの境界では見逃し得る。敵対的なfilesystem操作の証明やfile lockではない。新runの期待SHA照合は必ずfresh full hashするが、返却後の不変を永久保証しない。

SHAはbyte同一性で、実UTC/clock精度・実RF帯域guard・天体検出・RFI品質・局gain/SEFDの確認ではない。単局の実基線0で、局複製0。実複数アンテナ相関/Closure/Cas A画像、旧134/145の八条件や新画像尤度/画像再fitは未検証・保留。新classはinspectionの明示入口で、SampleBufferやsessionへ自動適用していない。

## 6. 次段階

170で規約どおり全体文書・要素別進捗・入口/計画を技術基準169へ同期する。新しい数値試験を行わない文書整理では、今回の試験を引用と明示する。その後は実複数アンテナ原本の具体的取得根拠、または局/時刻/帯域/単位/identityを固定したsession接続を選ぶ。同じ単局参照の小変更を自動反復しない。
