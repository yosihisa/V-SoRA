# 段階160：技術基準159への文書整理

- 作成日：2026-10-29
- 状態：完了（文書整理・静的監査のみ）
- 比較元コミット：ed067c8390b72f70a685f441c06a125ff5da1df7（159）

## 読者向け概要

個別の小さい検証が増えても、実観測から正しい画像を得られたことにはなりません。今回は全体の説明を159までの記録へそろえ、何が製品として変わり、何が条件付き参照で、何が未検証かを読み直せるようにしました。

AGENTSの10段階ごとの文書整理です。専用根本レビューは150で実施済み、予定200であり、160を新しい根本レビューや数値実験とは数えません。新しい結果は、文書・履歴・引用・SHAの静的照合です。

## 1. 目的・対象範囲

README、docs入口、二全体文書（時系列/要素別進捗）、roadmap、短い案内09、report索引、運用governanceの8文書を技術基準159へ同期しました。本reportと[小容量記録](../../validation/runs/stage160/README.md)を加えた14対象だけを公開します。過去個別report、コード/試験/tool/workflow/config/assets、原本を変更しません。

## 2. 完了条件

000〜159の初回Git/JST/公開authorとcommitterを照合し、時系列160行/索引000〜160の161行を対応させます。過去160個別report、凍結459、原本131の76SHA、対象外trackedを保持。現在の製品/full/wheel/GUI基準151と、最新の限定参照/対象159を区別します。公開監査0・文書リンク欠落0・指定公開名義のdevelopment commit/push・実remote一致/cleanまでを完了条件としました。

文書だけのため、製品関数/科学数値/MC/unit/pytest/full/collect/wheel/install/browser/取得/decode/raw/相関/Closure/画像fitを実行しません。Git/AST/行範囲/全byte SHAと既存JSONの読取りは静的照合です。

## 3. 実際に整理した判断

151で既存容量式を共用し37/64窓を高コスト処理前に拒否したため、旧全体文書の「151は未選択」「最新全回帰は138」を更新しました。36窓126MiBがguardを通ることと、全系列完走/自動resume/全夜性能は分けます。151初回fullの優先順不備と訂正、初回成功非加算を保持します。

152の共有幾何/decoded reader平均と153の別集合codecは統合した主経路成功ではありません。154の保存rate/gate集計は局推定全体の因果的分離を未識別のまま残しました。155は供給receiverの画像依存C、156は固定prior局所J、157は比較blur作用素、158は有限非負候補、159は固定合成幾何/単一toneの有限channel参照です。

156の元二step直接FDは一部未達であり、Richardsonへ正式手順を改訂した履歴を残します。157のscan誤検出とAST同じ空白訂正、158のpostprocessor、159の観測grid8/schema最小16拒否と一行訂正も消しません。局所null・blur norm・非負半径を、真Fisher/posterior/一次beam/許容振幅confidenceや復元改善へ変換しません。159のtone周波数と漏れ先channel中心の差はRML不具合や131画像差の単一原因ではありません。

実入力の根拠、広帯域前方平均/依存、未知局量と採否、低SNR画像モデルの八条件を主律速として維持。実入力新回答を優先し148の質問を繰り返しません。物理装置の不存在やWindows側不可を推定せず、供給時計/仮定SEFDを実測へ読み替えません。

## 4. 静的照合と引用した検証

[初回Git/JST記録](../../validation/runs/stage160/chronology.json)の000〜159をGitへ照合し、author/committer両方の公開名義を確認しました。過去160個別report/凍結459/原本76SHAと対象外tracked1518SHAを保持。正式静的照合は2.84秒で完了し、[正式記録](../../validation/runs/stage160/verification.json)へ保存しました。[引用根拠](../../validation/runs/stage160/evidence.json)は39file SHAと現在4codefile/5関数のAST行範囲SHAで、関数を実行した検証ではありません。

最新全回帰は151の両2328成功552.61/551.31秒・各30220警告/除外0、wheel103+4assets/全byte/pipcheck、両実GUI各28worker/56download/672行の引用です。表は折り返しで横scroll検証ではありません。最新対象/APIは159の両11成功1.13/.71秒・警告0/除外0、各6条件/38配列/6NPZ60フィールドの引用。158のfit試験1除外も過去記録へ残し、160の新合格へ足しません。

静的worker120秒/段階1200秒/公開validation512KiB/新ignored記録4MiB以下を予算としました。通常GUI151は変更せず、過去のwheel/full/browserも再実行していません。公開監査指摘0、文書リンク2182件で欠落0。

## 5. 制約と次段階

160は画像/機器の性能改善ではありません。実Cas A、実I/Q/時計/SEFD/beam/RFI、弱い実信号の未知LO/gain、実FFT独立性、低SNR画像尤度、全夜GPUは未検証です。新production尤度/RML/画像再fit/GUI、外部追加反復、truth係数調整、Windows収録は保留します。

[161〜165の候補](../../validation/runs/stage160/next-candidates.json)を現計画へ同期。有限帯域平均→必要な場合だけcodec後平均→推定/採否の識別可能な差とし、モデル条件が成立して初めてobjective/固定入力画像比較へ進みます。全候補は未選択で、後段164/165は現時点で保留。既存API/同等参照を先にreviewし、番号のため反復文書/小参照を追加しません。

次の文書整理170、予定の専用根本レビュー200、前提が崩れれば前倒しします。期限2026-11-06 15:00（Asia/Tokyo）、追加reset禁止、同じchat/scheduleを維持。段階数/試験数は完成率ではありません。
