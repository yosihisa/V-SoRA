# 段階112：同じ長い原本で1・2・3秒のpilotを補正相関へ接続

- 作成日：2026-10-26
- 状態：完了（既存経路の固定対照。新しい画像化は未実施）
- 比較元コミット：0e3021f549f61f303098b193c0c96ce32f32948e（111）

## 読者向け概要

111では弱い原本の1秒pilotで1局が孤立した。長く平均すれば雑音の影響が小さくなる可能性はあるが、pilotの間に局位相が変動する場合や、別の雑音を引いた場合は結果が変わる。そこで、同じ長い原本を使い、pilotだけ1・2・3秒に変える固定実験を作った。

予備の新原本では1秒でも全局がつながった。この結果を「長くしたから改善した」とすることはできない。原本sample数の変更で乱数消費、gain、LO、雑音実現値が変わるためである。固定した三つのseedの全条件を残し、失敗を捨てずに、未知LO取得と補正相関、画像化に使うClosureの可否を分ける。

## 1. 目的・対象範囲

既存のproduction経路を使って、短い補正相関まで正式に処理する対照実験を追加する。seed109/110/111、各3.04秒の原本、pilot1/2/3秒、最終積分0.3秒を事前に固定した。新しい推定式・閾値・画像尤度・RML・GUI・Windows収録は実装しない。

## 2. 完了条件

1. 同じ原本のprefixを比較し、全9条件と失敗・入力SHAを保持する。真値は事後評価にだけ使う。
2. checkout外の導入版native相関CLIで9条件を再実行し、全数値配列・graph/率/Closure科学JSON・入力不変・上書き拒否・prefixを確認する。
3. 既存のpipeline/rate/graph対象試験を実行する。production/module/packageはbyte不変とし、111の全回帰を既存根拠として明示する。
4. レポート・規約・索引・小容量記録、個人情報秘密情報監査、匿名commit/pushを完了する。

## 3. 実際に行った作業

[固定実験workflow](../../workflows/rate_acquisition_validation.py)、[導入CLI照合tool](../../tools/verify_rate_acquisition_installed.py)、[規約](../../interfaces/rate-acquisition-validation.md)、索引、本レポート、正式記録を追加する。実装済みの `process_closure_session(correlation_only=True)`、graph診断、Closure抽出を再利用する。

1.42GHz・8局・最大600m、合成Cas Aのflux1000Jy、局SEFD10000Jy、2.048MS/s、8bit複素VDIF、1520frameを仮定した。正確なsample clockとscaleを与えるが、局gain/LOと天空形状は推定に与えない。gain/LOは3秒以内で一定。これらは実機の測定値ではない。

seed109は予備原本の全SHAを確認してコピーし、予備の合格を流用せず正式な相関を新規出力で再実行した。seed110/111も同じ仕様で生成した。各原本内のpilotは250/500/750区間×4msで、最終相関は先頭付近の0.3秒を共通に使う。相関できた条件はSNR10でClosure有効数を計算する。相関しなかった条件のClosureはnull、相関後に有効なものがない場合は0とする。

残留rateが一定で矩形積分、天空visibilityも一定と仮定すれば、相関振幅の減衰は `abs(sinc(delta_rate * T))` となる。生成真値との差をこの式へ入れた値は計算値として残す。実際に測ったcoherenceや誤差の包含率とは扱わない。

## 4. 検証条件・結果

| seed | pilot秒 | 検出基線 | 補正相関 | 局rate最大誤差Hz | 有効phase/logamp Closure |
| --- | ---: | ---: | --- | ---: | ---: |
| 109 | 1 | 17 | 保存 | 0.02829107 | 0 / 0 |
| 109 | 2 | 22 | 保存 | 0.02955222 | 0 / 0 |
| 109 | 3 | 23 | 保存 | 0.02127985 | 0 / 0 |
| 110 | 1 | 15 | rate_graph_disconnected | — | 未計算 |
| 110 | 2 | 21 | 保存 | 0.02355444 | 0 / 0 |
| 110 | 3 | 22 | 保存 | 0.01045620 | 0 / 0 |
| 111 | 1 | 17 | 保存 | 0.03824672 | 0 / 0 |
| 111 | 2 | 20 | 保存 | 0.00934489 | 0 / 0 |
| 111 | 3 | 22 | 保存 | 0.01226080 | 0 / 0 |

全9条件のうち8条件が未知LO取得・補正相関まで進み、1条件は未完了として保持した。相関できた8条件中、SNR10で位相・振幅Closureとも0だったものは8条件。画像を作る処理は今回呼んでいないので、画像復元の成功件数とはしない。新原本seed109では1秒で既につながり、seed110では1秒が切断・2/3秒でつながった。異なる原本の差と、同じ原本内のpilot長の差を混ぜない。

### 導入版と変更範囲

導入版の既存native相関CLIを全9条件で実行し、104個の保存相関配列について値・dtype・shape・SHAがsourceと完全一致した。graph/率/Closure科学JSONも全項目一致。全9出力で上書き拒否・byte保持、元原本SHA不変、checkout外・runnerなし・PYTHONPATHなし、読込project module9個のprefixを確認した。metadataの観測条件・時刻・適用rate等も比較し、絶対出力場所やそのarchive/profile来歴SHAは各処理の記録として分けた。archive全体のbyte一致を主張していない。

比較元からproduction module・試験・設定・同梱assetはbyte不変である。そのためwheel再導入と両全回帰は本段階で繰り返さず、[111正式記録](../../validation/runs/stage111/verification.json)のsource/導入済み各2021試験（602.30/601.86秒、27396既存警告、除外0）を既存根拠として引用する。代わりに、今回の同じ生VDIFに対してsource9回＋導入済みCLI9回の実相関を正式に実行して新しい検証経路を照合した。

既存pipeline/rate/graphの47対象試験は26.62秒で成功、既存警告2280件。新しい実装を模倣する試験は増やしていない。通常GUIは導入済み111のままidleを確認し、ブラウザは再実行していない。

ソース/試験/検証tool/workflow/設定375ファイルの凍結SHA不変、対象外tracked 1161ファイル不変。既存111wheel内package100ファイルと同梱assetは導入先・sourceの両方とbyte一致し、pip check成功。公開監査指摘0、文書リンク1454件で欠落0。

[全9条件](../../validation/runs/stage112/reference.json)、[導入CLI照合](../../validation/runs/stage112/installed-api.json)、[来歴・不変性・公開監査](../../validation/runs/stage112/verification.json)を参照する。大容量原本と各相関NPZはGit管理外 `outputs/stage112-source-study/`、導入済み再実行は `outputs/stage112-installed-api/`、ログは `outputs/stage112-*-log/` に保存する。

## 5. 制約・未解決事項

3seedは固定の有限実験で、一般的な採用率を校正した結果ではない。同じ原本のpilotと最終相関は重なり、独立した検出・評価データではない。一定gain/LO、正確なclock/scale、周期的な帯域制限Gaussian電圧、区間中央の天空共分散という仮定を残す。

長くしたpilotの効果は原本内で判断する。109の短原本との比較は、sample数・乱数消費・gain/LOも違う。弱い実信号、実OCXO、実SEFD、Nyquist alias、低SNR画像尤度、実機Cas A画像、全夜/GPU性能は未検証である。

## 6. 次段階

113では、取得できた同じ3秒pilotの率を使い、最終積分0.3/1/3秒の範囲で相関・Closureの利用可能性を比較する候補を優先する。3秒以内で使える情報を確かめる前に、閾値を緩めて画像を作ることはしない。高SNR Closureが不足する場合は、保存した複素統計や低SNR画像尤度へ何を渡すかを主経路の課題として見直す。

次の文書整理120、根本見直し150を維持し、主要前提が崩れれば節目を待たず優先順位を変える。
