# 段階170：技術基準169への文書整理

- 作成日：2026-11-02
- 状態：完了（文書整理・静的監査のみ）
- 比較元コミット：`8317129d4fe015b58c9a63e1b0828e7228485dd5`（169）

## 読者向け概要

公開単局IQを読めることと、複数の受信機からCas A画像を復元できることは違う。今回、全体の説明を169までの結果へそろえた。受信機チームの実記録はなく構成検討中という回答、実際に取得したCAMRAS単局IQ、製品reader/検査CLI、残る複数局の主経路を分ける。

AGENTSの10段階ごとの文書整理である。専用根本レビューは150を継承し予定200。170を新しい専用根本レビューや科学実験には数えない。

## 1. 目的・対象範囲

README、docs入口、二全体文書（時系列/要素別進捗）、短い案内09、roadmap、governance、report索引の8文書を技術基準169へ同期する。本reportと[検証案内](../../validation/runs/stage170/README.md)を加えた10Markdownだけを公開する。全個別過去report、コード/試験/tool/workflow/config/assets、原本は変更しない。

## 2. 完了条件

実行前に `outputs/stage170-preparation/purpose-fixed.md` へ範囲・受入・予算を固定した。000〜169の初回Git/JST/公開author・committerを静的照合し、時系列170行と索引000〜170の171行を対応付ける。過去170report、non-Markdown1263file、169入力/131模擬原本76SHA、新wheel/installed105file＋4assetsを保持する。

静的worker120秒・段階1200秒・管理外追加4MiB・公開512KiB。公開監査0/文書リンク欠落0、10file strict allowlist、公開名義でdevelopment commit/push/実remote一致/cleanまで完了する。録音・提供metadata・派生波形/科学JSON/図の公開0byte。

## 3. 実際に行った整理

161/162の有限mode平均/codecと、163の局LS/χ²maskを実観測のGaussian画像尤度へ合成しない条件を残した。全推定biasとgateの因果分離は未識別のままである。

164の実Crab単局16MB、165の非可逆8bit参照、166の16bit prototype、167の生成fixture除外、168の限定SigMF API、169のfresh pair SHA/実CLIを時系列へ追加した。受信機実記録なし・OCXO/構成/保存形式未決定という回答を反映し、148の同じ照会を繰り返さない。原本/metadata/派生物をGitへ載せない取得配置方法へ入口を追加した。

最新製品/full/wheel/専用両実GUIは169、通常GUI151用prefixは別に保持したことを明記した。保存模擬診断のGUI回帰を、公開IQ検査CLIをGUIへ接続した結果へ読み替えない。

169のpreformal同stat変更の見逃しと検出条件、補助呼出の誤り、公開補助の旧report参照停止と訂正を残す。168準備環境・165初回root検査等の失敗も、個別report/管理外記録に保持する。段階数/試験数を画像復元の完成率にしない。

次の具体的software候補はSigMFのsession入口で、局/時刻/clock/単位/RF/identity対応と、既存の異なる模擬局電圧による旧VDIF不変/独立照合を選択前に固定する。公開単局を複製して実基線を作らない。実複数アンテナ原本の取得候補は個別URL/ID/最小容量/実観測出典/条件を先に確認する。新画像尤度/画像再fitは保留。

## 4. 静的照合と引用した結果

静的初回は補助scriptがGit statusの先頭空白もstripし、allowlistを誤判定して停止した。対象文書/コードは修正せず、全worker終了後に補助の改行処理だけを訂正した。失敗log/初回scriptを保持し、全静的選択を再実行して初回の成功を合算しない。

正式静的再実行は0.758秒で成功。000〜169初回Git/JST/両公開名義の170行、索引171行を照合した。過去170report、non-Markdown1263file、対象外tracked1567file、131模擬原本76SHA、169入力3SHA/GUI入力10SHA、新wheel/installed105file＋4assetsを保持。検証時の公開対象231,255byte・管理外記録407,052byteで上限内。完全ID/JST・全hashの照合記録はGit管理外へ保持し、公開validationは文章だけとした。

最新数値は[169](169-sigmf-identity-cli.md)の両全2414成功・565.04/562.00秒・各30220警告/除外0、両対象98、実CLI一致/拒否、wheel105file＋4assets全byte、保存診断の両実GUI各28条件/56JSON/672行を引用した。新wheel SHA256は `7f3ad310e137294c26c83a4629ab3ab869c1061766f2db7f0a37ab8bb8a5c9cb`。168の800万成分/17配列一致も引用で、170の新合格や独立実観測試行へ再加算しない。

170で新しい科学計算/MC/pytest/full/collect/wheel生成/install/browser/取得/復号/相関/Closure/画像fitは実行していない。Git/Markdown/既存logと全byte SHAの静的読取だけである。

公開監査指摘0、文書リンク2289件で欠落0。10Markdownのstrict allowlistで公開し、原本/提供metadata/派生データの公開0byte。

## 5. 制約・未解決事項

実RTL-SDR/OCXOのCas A画像化、実sample clock/LO/gain/SEFD/beam/RFI、実FFT独立性、低SNR画像尤度、全夜GPUは未検証。単局のbyte識別は時計・品質・天体検出の較正ではない。data全stat保持変更の同instance検出も保証しない。

## 6. 次段階

現在計画の具体的なSigMF session接続の契約をreviewし、製品変更なら両新全回帰/wheel/pipcheck/全byte/checkout外API/両実GUIを含む予算を固定して選ぶ。同じcodec参照・不足文書だけの反復は避ける。次の文書整理180/予定の専用根本レビュー200、前提が崩れれば前倒し。期限2026-11-06 15:00JSTと同じautomationを維持し、手動UIで充足したreset承認を再使用しない。
