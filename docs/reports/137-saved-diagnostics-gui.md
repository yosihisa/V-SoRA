# 段階137：現在の保存診断を既存日本語GUIで照合する

- 作成日：2026-10-27
- 状態：完了（GUI操作と保存値の照合。新しい画像復元性能の証拠ではない）
- 比較元コミット：6a6dea70b735b6d6840cc952647d1c01d869c1a0（136）

## 読者向け概要

相関器の計算結果が正しくても、画面が未判定を0と表示したり、保存するJSONが古かったりすると、観測者の判断を誤らせる。今回は135/136で計算した保存データを、日本語GUIから実際に読み込み、表示された数値と保存JSONが元の計算に一致することを確かめた。

診断画面は既にあったため、そのまま利用した。ソース版と導入済み版の両方を実Chromiumで操作し、各28条件・56回のJSON downloadを照合した。これは操作とデータ受け渡しの確認で、実受信機の信頼区間やCas A画像化を確認した意味ではない。

## 1. 目的・対象範囲

主目標は、精密な局gain較正が難しいRTL-SDR/OCXO観測から画像を復元することである。その途中では、短い積分に有効な情報があるか、保存量が足りているか、雑音の仮定に依存した数値かを判断する必要がある。

今回は、保存相関の一セルの雑音・Closure誤差と、3秒pilotの時間散乱を扱う既存GUIを検証した。新しい画面・統計API・画像solverは作らず、production packageを変更していない。

## 2. 完了条件と固定行列

| 対象 | 件数/環境 | 比較元 |
| --- | ---: | --- |
| 4原本×3RF×回転なし/同pilot推定rate回転 | 24 | 136全診断JSON |
| 高感度の有効/非活動セル、弱い条件の有効セル | 3 | 135全診断JSON |
| 最終相関の1時間cellを時間診断へ入力 | 1 | 136の時間数不足probe |

原本を再生成・再相関せず、132の保存NPZと推定profileを直接選択した。各診断JSONとsummary.jsonを実downloadし、全fieldを照合する。公開されたSHAを使い、同じ原本の科学値を期待値として登録した。135のjoint/production比較に使ったSNR10と、GUIが既定のAPIで使うSNR5は別である。

## 3. 実際に行った作業

追加した `tools/verify_saved_diagnostics_browser.py` は、既存フォームを操作する検証toolである。入力の読み込み、RF・時刻選択、実worker起動、処理完了、表示表、詳細JSON、downloadを確認する。保存済みの完了記録を画面に見せるだけのfixtureではなく、28件とも実workerを実行した。

変更は上記tool、本レポート、段階索引、validation/runs/stage137/の5記録に限る。既存の科学コード・GUI・試験は変更していない。

ソースと導入版はcheckout外の別workspace・所有する別portで起動し、通常GUI8765は止めていない。完了した検証出力の再使用は両方とも拒否され、全ファイルのSHAが不変だった。ソースは正確なmodule位置、導入版はprefixを10moduleで確認した。導入側にはrunnerやPYTHONPATHを置かない。検証tool自体はcheckoutにあり、toolまでwheelへ同梱された製品機能ではない。

## 4. 検証条件・結果

両実Chromium 153.0.8010.12で、全28診断と28summaryのJSONが各期待値へ一致し、両環境の全case記録も一致した。時間系列の672基線行について、局名・state・差引time/mean power・差・ratioの丸め表示を全件照合した。50未判定はダッシュ、174負・148の1超は元の数値のまま表示した。

一セル雑音は全表示SNR、冗長な全Closure行のstateと一次近似σを照合した。無効行の保存値0を、誤差0の測定と表示しない。時間cell数が1だけのprobeは処理自体は完了しても診断は未判定になり、32〜8192個が必要という説明を表示した。

初回の導入側試験は、checkout外の試験parentがworkflowsのfixture補助コードを探索できず、7失敗・194成功・警告1、347.40秒で終了した。全7件はModuleNotFoundErrorだった。終了したログを保持し、製品本体の変更ではなく試験parentのsys.pathへcheckout rootだけを追加した。apps/*/srcやPYTHONPATHは追加せず、製品moduleが導入prefixのままであることを再確認して全201件を再実行した。初回の194成功を正式成功件数へ合算しない。ソース版の正式実行と検証toolは不変だった。

390pxで日本語fontを読み込み、ページ全体に横はみ出しがないことを確認した。既存の時間表は固定幅とセル内折り返しを使う。横scroll領域を新設せず、表のcontent幅・親幅とoverflow-wrap:anywhereを測って確認した。存在しない横scroll操作を合格に数えていない。JavaScriptエラー・外部通信は両方0。

[導入済みGUIの390px表示・縦長の全行記録](../../validation/runs/stage137/mobile-result.png)

既存対象試験はソース201件/422.39秒・導入201件/412.70秒で成功、警告は各10921件、除外0。新unit test・全collectは追加していない。試験の小規模模擬workerと、本段階の保存原本への28診断は区別する。

凍結441file、core215file、既存121wheel103file＋4asset、pip環境は不変。原本76、相関12、pilot12、推定profile4のSHAを保持した。production不変のため新wheel導入・全回帰を再実行せず、121の両2116成功（609.28/607.50秒、各27396既存警告・除外0）を引用する。2277は135での収集であり全実行ではない。

[全caseとdownload識別](../../validation/runs/stage137/reference.json)、[正式検証](../../validation/runs/stage137/verification.json)、[有限の実行記録](../../validation/runs/stage137/measurements.json)を参照する。公開監査指摘0、文書リンク1783件で欠落0。

## 5. 制約・未解決事項

power比は雑音差引後の平均power/時間powerで、振幅保持率や物理的coherenceとは異なる。負・1超・nullを含む。同pilotを使うrate推定の依存、FFT/時間cell独立性、FIR/量子化、実SEFD/beam、confidenceは未校正のまま。表示が正しくても、実機の位相安定性や低SNR画像尤度の正しさを保証しない。

WSL上のheadless Chromiumを実行した証拠であり、Windows収録やWSLgの目視操作を検証していない。実Cas A観測、弱い実信号の未知LO・gain、全夜/GPU性能も未検証。

## 6. 次段階

138以降は現在の雑音モデルの適用限界と、実際の短積分の画像主経路へ戻す。画面や反復の追加だけを画像化の進捗としない。140の全体文書整理、150の専用根本レビューを維持し、既知の天空や真のLOを使う対照と未知観測を分ける。
