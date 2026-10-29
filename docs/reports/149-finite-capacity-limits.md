# 段階149：固定VDIF容量と、系列計画・RML制限の組合せ

- 作成日：2026-10-29
- 状態：完了（条件付き容量計算・既存APIの小入力照合・文書。製品修正なし）
- 比較元コミット：728ef876da9460a6c43b6784d7cde3f7d50febb3（148）

## 読者向け概要

原本を何byte保存するかと、選んだ区間を画像化できるかは別の問題である。今回は現在の固定VDIF形式の容量を整数式で確認し、処理ごとに設けられた上限を一緒に満たす条件を点検した。

8局・8チャネル・32画素では、系列計画が許す64窓でも、最終RMLの直接Fourier行列は計算上224MiBとなり、128MiB上限を超える。37窓の既存RML呼出が行列生成前に拒否されることを両環境で確認した。36窓の126MiBは、この行列上限を満たす計算値に限り、全系列や画像化の成功ではない。

## 1. 目的・対象範囲

148で実記録/取得環境を照会済みで、新回答はない。重ねて質問せず、回答不要の有限運用点検を選んだ。138/139/131、整列相関・短区間・sequence・synthesis・RML、既存`expected_vdif_bytes`/`check_resources`と既存試験を先にreviewした。既存運用設計にも容量式があるため新preflightは作らず、制限の組合せを新しい対象とした。

対象は固定profileの整数計算、原本digest/stat、既存の純粋な計画APIとRML早期拒否、[有限容量と制限の案内](../guide/finite-capacity-and-limits.md)である。source/tests/tools/workflow・RML・GUIは変更しない。取得・raw生成・相関・Closure算出・Fourier行列生成・画像最適化は行わない。

## 2. 完了条件と予算

3.04秒/1時間/8時間/24時間の容量を既存式と独立なpayload+header整数式で一致させる。canonical4件の原本76SHAと32 VDIFのstat byteを確認する。36/37/64窓の計画と37窓RML拒否をsource/installedで照合し、輸入moduleの正確な位置とbyteを確認する。planの受理をraw長・全系列完走へ広げない。

既存容量式4回、3計画+1早期拒否/環境、MC0、seed/MCSE対象外を実行前に固定した。各子処理60秒、全照合120秒、追加出力2MiB以下、公開記録128KiB以下を予算とした。新製品APIや同等unit/全回帰は選ばない。対象外trackedと451コード・設定・asset、原本を保持し、監査・文書リンク・公開名義commit/push・実remote一致/cleanまでを完了条件とした。

## 3. 固定原本容量

EDV0/8bit I/Q、4096 complex sample、32byte header、公称Fs2048000、8局を固定した。8224byte/frame、500frame/秒/局なので、8局の名目byte流量は32,896,000byte/秒となる。実取得速度の測定ではない。

| 名目区間 | 8局VDIF bytes | 独立整数式と既存式 |
| --- | ---: | --- |
| 3.04秒 | 100,003,840 | 一致、各canonical caseのstatとも一致 |
| 1時間 | 118,425,600,000 | 一致、生成なし |
| 8時間 | 947,404,800,000 | 一致、生成なし |
| 24時間 | 2,842,214,400,000 | 一致、生成なし |

既存workflowの`expected_vdif_bytes`関数本体をASTから取り出し、固定定数を与えて4回評価した。generator moduleのimport/entrypointや`check_resources`は実行していない。独立側はsample数×局数×I/Q bytesとframe数×局数×header bytesの和で求めた。再利用した関数の行範囲/SHAを保存した。

4caseのVDIF合計400,015,360byte、32ファイルのstatと76原本SHAを確認した。新しいVDIF header/payload decodeはしない。表にmetadata・元IQ・複製・圧縮出力・partialは含まれない。131の512MiB生成予算/4GiB空きdisk/8GiB MemAvailableを、一般の必要PC仕様や実観測の性能へ変換しない。[容量記録](../../validation/runs/stage149/capacity.json)に全整数とstat/SHAを保存した。

## 4. 独立した上限を組み合わせる

一次コード6file/10関数・メソッドと引用15fileを[行範囲/SHA記録](../../validation/runs/stage149/source-audit.json)へ残した。既存試験の計画・partial・synthesis失敗検査もreviewし、同じ試験を追加・再実行していない。

整列相関は1回約3秒/100万cell等、sequenceは2〜64窓/非重複/最終100万cell等、synthesisは軸・単位・露出・時刻整合等、RMLは128MiB Fourier行列と採用Closure等を別々に検査する。`process_sequence`は各窓の相関後、時刻/チャネルを保ったまま合成し、pixels=32でRMLを呼ぶ。計画時点で全条件を一括保証してはいない。

小入力では8局/FFT8/1024block、pilot750 cell（3秒）、画像0.3秒、start0.002秒、非重複default stepを固定した。`plan_windows`は36/37/64窓とも受理した。最終pilot末尾は108.002/111.002/192.002秒となるが、計画APIはrawを読まない。3.04秒の131原本でこれらが処理できるという結果ではない。

| 窓数・画素数 | Fourier行列の計算値 | 今回の実行/判定 |
| --- | ---: | --- |
| 36窓・32画素 | 132,120,576byte＝126MiB | 計算のみ、この上限内。RML完走は未検証 |
| 37窓・32画素 | 135,790,592byte＝129.5MiB | 既存RMLが128MiB超過ValueErrorで早期拒否 |
| 64窓・32画素 | 234,881,024byte＝224MiB | 計算上超過、RMLは実行せず |
| 64窓・16画素 | 58,720,256byte＝56MiB | 計算のみ。現sequenceの指定項目ではない |

37窓の`ClosureObjective`にはshape(37,8,28)のゼロvisibility、有限ゼロuvw、重み1、28pairだけを渡した。既存constructorはgeometry検査の直後に行列上限で拒否するため、Closure/Fourier構築やfitへ到達しない。物理的な観測や天空の対照ではなく、既存の入力容量検査を通す小入力である。36窓や16画素の計算を収束・科学的妥当性・搭載RAM要件へ変換しない。行列以外の一時配列等もある。

sourceは明示したsrc探索path、installedはcheckout外の一時cwd・runner/PYTHONPATHなしで同じ小入力を実行した。両JSONは完全一致、24製品moduleは正確なsource位置/導入prefixで、輸入された24moduleのファイルbyteも一致した。package全103file+4assetの新しい全byte監査を行ったという主張ではない。[API記録](../../validation/runs/stage149/api-probes.json)に方法と拒否文を残した。全照合は2.80秒で予算内、初回成功。小入力照合を新pytestの合格件数へ加算していない。

## 5. 運用上の判断と制約

計画が受理されても、後段の上限、原本末尾、rate推定、Closure不足等で停止し得る。窓間stepは長く取れるため、長い経過時間を選ぶことと連続全夜を処理することも異なる。今回、長時間driver・早期一括preflight・任意checkpoint再開は追加していない。潜在的な高コストの後段拒否を150の優先順位検討へ渡す。

InputIdentityの適用箇所とhash/statの限界、原本/clock/設定/profileの固定は148/138、末尾不足・partial保持・同出力拒否・別出力再処理は139の引用である。139の4ms出力16,658byteや単発wall/生涯peakRSSを、長時間容量/速度へ比例外挿していない。149で系列のpartial再開を試験したとも扱わない。

新unit/target/full/collect/wheel/install/browser/科学MC/raw生成/相関/Closure/画像fitは未実施。[正式記録](../../validation/runs/stage149/verification.json)に明記した。最新全回帰は138の両2321成功542.82/541.45秒・各30220警告/除外0、wheel/両実GUIも138、最新target101件は147を引用する。通常GUI138は更新・停止していない。公開監査指摘0、文書リンク1988件で欠落0。

変更は本report、索引、有限容量の案内、[小容量記録](../../validation/runs/stage149/README.md)だけ。対象外tracked1462と凍結451、原本76SHAを保持した。実取得throughput、実時計/LO/gain/SEFD/beam/RFI、実FFT独立性、低SNR画像尤度、実Cas A、全夜/GPUは未検証。既知天空・供給時計の模擬参照を未知の実観測成功へ変換しない。

## 6. 次段階

150は必須の文書整理と専用根本レビューを併せて実施する。技術基準149で時系列/目標別進捗/計画/短い案内/入口/索引を同期し、145の八条件、141〜147の限定参照、148の実入力未確認、149の容量・後段拒否を統合する。部品や段階数で完成率を評価せず、次5〜10段階の寄与と受入条件を更新する。150自体は未実施。

実入力または取得環境の新回答があれば優先する。前提が揃わない画像/GUI接続、truth係数調整、追加反復、Windows収録は保留を維持する。継続期限2026-11-06 15:00JST、追加reset禁止を保持する。
