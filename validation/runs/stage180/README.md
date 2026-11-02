# 180：技術基準179への文書同期・静的監査

[レポート](../../../docs/reports/180-documentation-checkpoint.md)を参照。公開対象は指定10Markdownだけ。旧個別report180件とコード/tests/tools/workflows/config/assetsは変更しない。文書整理はAGENTSの規定周期で、専用根本レビュー150を継承する。

Git/Markdown/既存byteだけを読む。000〜179個別reportの初回追加commit・JST・公開author/committerを180行の時系列へ照合し、索引000〜180の181行を検査する。完全ID/日時/全SHA/詳細logは `outputs/stage180-preparation` に管理外保存する。

変更前の全tracked SHAから、対象外と全non-Markdown1281file、過去180reportを照合する。179 input-files295SHA、131原本76SHA、CAMRAS3SHAとLBA断片をSHA読取だけで確認する。179wheel106製品+4assetsとsource/installed全byte、旧151/168/169/171/172/173/174/175/176/177と179初回archiveのwheel byteを比較する。wheel生成/import/installを行う検査ではない。

新科学計算/pytest/full/collect/wheel生成/install/pipcheck実行/ブラウザ/取得/復号/相関/Closure/画像fit/MCは0。179の両全2573等は引用で、180へ加算しない。177の参考画像非収束、178の実4局取得と実相関0、179の保存予算監査不備と全選択再実行を条件付きで読む。

静的worker120秒/段階1200秒/管理外追加4MiB/公開512KiB/空き10GiB reserve。正式選択中は入力・対象・補助を固定し、修正が必要なら全worker終了後だけ、失敗log/旧補助/凍結を保持して全選択を再実行する。準備時の旧補助名不在はread-only探索で、正式試験の失敗と混同しない。

公開監査・文書リンク・strict allowlistを確認し、公開名義でdevelopment commit/push、実remote一致/cleanまで行う。原本/提供metadata/派生科学JSON/配列/図は管理外。通常GUI151更新/再起動0、追加reset購入使用0。次文書整理190/予定根本200、同一automation/期限を維持する。
