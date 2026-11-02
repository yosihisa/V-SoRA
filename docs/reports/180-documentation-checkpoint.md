# 段階180：技術基準179への文書整理

- 作成日：2026-11-03
- 状態：完了（文書整理・静的監査のみ）
- 比較元コミット：`d07981065e6db36eb4f0178be07bac6f1ae175c0`（179）

## 読者向け概要

公開4局の録音を取得できたことと、実相関からCas A画像を復元できたことは違う。今回、全体の説明を179までへそろえた。模擬SigMFの形式接続、実LBA4局原本の限定読込、目標機材の実記録なし/実相関基線0/実Cas A未検証を分ける。177の参考画像は固定100反復で非収束だったことも残す。

AGENTSの10段階ごとの規定文書整理である。専用根本レビュー150を継承し、予定200/次文書整理190。新しい専用根本レビューや科学実験には数えない。

## 1. 目的・対象範囲

README、docs入口、二全体文書（時系列/目標別進捗）、短い案内09、roadmap、governance、report索引の8文書を技術基準179へ同期する。本reportと[静的検証案内](../../validation/runs/stage180/README.md)を加えた10Markdownだけを変更する。過去180個別report、コード/tests/tools/workflows/config/assets、原本・提供metadata・保存study・旧prefixは変更しない。

## 2. 完了条件

実行前に管理外のpurposeへ範囲・受入・予算を固定した。000〜179の初回Git/JSTとauthor/committer両公開名義の180行、索引000〜180の181行を静的照合する。non-Markdown1281file、対象外trackedと過去180report、179固定入力295SHA、131原本76SHA、CAMRAS3SHA/LBA断片を保持する。

179wheel106製品file+4assetsのsource/installed全byteと、旧151/168/169/171/172/173/174/175/176/177および179初回archiveの各wheel byteを静的照合する。新数値/pytest/full/collect/wheel生成/install/pipcheck実行/browser/取得/復号/相関/Closure/画像fit/MC0。引用を180の新合格へ加算しない。

静的worker120秒/段階1200秒/管理外追加4MiB/公開512KiB/空き10GiB reserve。strict allowlist、公開監査0/リンク欠落0、両公開名義development commit/push/実remote一致・cleanまで完了する。追加reset購入使用0、同一automation/毎時0分/期限2026-11-06 15:00JSTを維持。

## 3. 実際に行った整理

171のdirect相関、172のpilot/rate pipeline、173のlive原本識別共有、174の相関専用sequenceを、模擬4局の検証として記載した。供給公称Fs/UTCと明示actual_rate/clockの対応を、実時計測定としない。UTC9桁の算術整合や1pass hashを実clock精度・総I/O測定へ読み替えない。

175の保存主張一致mergeと176の明示fresh原本照合を区別し、snapshot一致が配列の計算履歴やproducer認証ではないことを残す。valid_fft_countは独立標本数/実効Mではない。177は既存高SNR参考画像の明示形式接続だけで、新noise/RML/八条件を追加していない。固定観測行/weightを条件にしたobjective/勾配の代数検査と、非収束/実画像精度未確認を分ける。

178の実4局断片は提供者が実天体観測として配布するLBA/V177A/1600-445、公称8MHz/0.262144秒/real2pol/2bit/RF帯域下端1719MHz USB。元header/offset/記録偏波順を保持し、目標のRTL-SDR/OCXO・1.42GHz Cas A・600mとは区別する。元tar/member全体SHA・producer checksum・実clock精度と明示data licenseは未確認。ローカル非再配布検証に限定する。

179の有界実数偏波readerは全16777216成分/48seekを保存178へ一致させた。R/LをI/Qへ見立てず、actual_rate/局ID/RF/sidebandは未知のまま、session/実相関/GUIへ自動接続しない。実4局の6組合せと、検証済み実相関基線0を分けた。CAMRASは単局のままで複製しない。131原本の再生成/再相関/再fitは保留を維持。

171のinvalid frame/出力精度/stub/補助とwarning30300への訂正、172 collection停止、173追跡metadata/byte補助、174 worker0起動停止、177 API/CLI記録差の中断と非収束、178 probe誤認/取得timeout/選択再実行、179同stat盲点/一時出力を除いた2GiB予算超過を全体文書へ接続した。179は全worker終了後に初回出力を保持し、全attemptとpytest一時出力を含む4GiBへ正式改訂して全attempt2を再実行した。worker境界計測と連続peakを区別し、初回成功を合算しない。

現在計画のヘッダと旧170未選択候補を履歴として整理した。次は既存readerを重複実装せず、実数偏波/解析信号化/sideband/時計・幾何と複素入力・600m guardの具体差をreviewし、独立受入と全正式予算を固定して選ぶ。旧164/165の新画像尤度/131再fitは保留のまま。受信機チームへの148照会は回答済みとして繰り返さない。

## 4. 静的照合と引用した結果

正式静的初回は5.715秒で成功。000〜179の初回Git/JST/両公開名義180行、索引181行を照合した。過去180report、non-Markdown1281file、対象外tracked1608file、179入力295SHA、131原本76SHA、CAMRAS3SHA/LBA14fileを保持。179新wheel/installed/sourceの106製品file+4assetsと旧10prefixと179初回archiveの各wheel byteも静的照合した。検証時の公開対象260939byte・管理外記録458519byte、空き40459284480byteで固定予算内。完全ID/JST/全hashと詳細logは管理外、公開validationは文章だけとした。180の新数値/製品検証は0。

最新数値は[179](179-lba-fragment-reader-api.md)の最終attempt2、両対象104/collect・full各2573成功、各39404既存種別warning/除外0、source611.71/installed615.31秒、106製品+4assets全byte、checkout外API/既存実CLI、保存模擬診断の両実GUI各28条件/56JSON/672行を引用する。wheel SHA256は `3e7fff5ee9e4d1c3dde07e14dbe637fd8c8a122559c2e17ad53591e52f14adb4`。新LBA/SigMF画面の検証ではない。通常GUI151prefixの更新/再起動はしない。

171〜179を足した件数や、同じ原本の再照合を独立実観測試行数としない。過去の初回失敗・中断・除外・非収束は各report/管理外logへ保持する。準備時に旧補助名run_static.pyの不在を確認し、実在verify_static.pyへ参照を訂正した。これはread-only補助探索の不成功で、数値試験や正式workerの失敗ではない。

公開監査指摘0、文書リンク2425件で欠落0。10Markdownのstrict allowlistで公開し、原本/提供metadata/派生データの公開0byte。

## 5. 制約・未解決事項

180は文書と既存byte/Gitの静的読取だけ。実時計・LO/gain/SEFD/beamRFI、実FFT独立性、未知実noise/低SNR尤度、実RTL-SDR/OCXO Cas A画像、全夜運用/GPUを新たに検証していない。全stat保持raw変更や最後のguard後の変更、file lock不在の限界も残る。原本/提供metadata/派生科学JSON・配列・画像のGit公開0byte。

## 6. 次段階

現在roadmapと実残量を先に確認し、実数2偏波と現複素入力の具体的な物理契約からsoftware作業を選ぶ。新adapterや実相関の実装をこの文書整理で済ませたとは扱わない。同じcodec/有限FFT/参考fitや不足文書を番号のために繰り返さない。次文書整理190/予定根本200、前提が崩れれば前倒し。期限以降は新開発せず同じautomationをnativeでPAUSEDにし、結果を報告する。
