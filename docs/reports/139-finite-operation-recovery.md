# 段階139：有限入力の失敗を保持し、別出力先で再実行する

- 作成日：2026-10-29
- 状態：完了（固定模擬原本による有限運用検証。自動checkpoint再開は未実装）
- 比較元コミット：74ed25fdc3f93f99658fd15d3b301a8ab580037a（138）

## 読者向け概要

長い原本でも、要求した時刻の電圧が足りなければ処理は完成できない。途中の結果を完成結果として使わず、失敗記録を残して別の出力先へ正しい区間を処理し直せることが必要になる。

今回は3.04秒の模擬原本に3.038〜3.042秒を要求し、末尾不足の失敗を確認した。同じ出力先は拒否され、失敗記録を残したまま別の出力先の0.002〜0.006秒は成功した。既存機能を実行した検証で、製品の新機能は追加していない。

## 1. 目的・対象範囲

131のhigh_a原本・8局をreadonlyで再利用し、correlate_alignedのAPIとCLIをsource/導入済みで使う。APIは関数呼出し、CLIはコマンドの引数解析からの呼出しである。既存InputIdentityを検証workerで使い、毎回SHAとstat境界を確認した。これは直接のcorrelate_aligned自身へ新たなSHA機能を追加した意味ではない。

4ms×1の失敗・非上書き・別出力への再処理、時間/メモリ/容量の有限測定を対象とする。原本再生成、画像fit、製品修正、GPU、自動checkpoint再開、実機確認は対象外。

## 2. 完了条件

1. 両環境のAPI/CLIで末尾不足ValueError、incomplete failure.json、完成先不存在を確認する。
2. 同じpartial先への正しい区間もFileExistsErrorで拒否し、失敗記録を全byte保持する。
3. 別出力先で正しい4msを処理し、138 high_aの全配列・metadata・summaryを直接照合する。完成出力への再実行も拒否し全byte保持する。
4. 原本76SHA、実module所属、checkout外native、対象試験、package byte不変、公開監査と文書・匿名commit/pushを確認する。

## 3. 実際の作業

[finite_recovery_validation.py](../../workflows/finite_recovery_validation.py)を追加した。各環境で2入口×4操作の8個の単独workerを順番に起動し、成功と例外の両方について終了コード、SHA、module所属、LinuxのpeakRSSとwall timeを保存する。CLIは既存__main__をrunpyで実行し、通常のargparseと処理を通す。新しい解析APIや製品の再開機構ではない。検証wrapperはcheckoutを必要とする。

既存input_identity・sequence・aligned_sessionの対象試験を両環境で実行した。新unit testは追加していない。正式実行中はcode/試験/tool/workflow445件を凍結した。変更はこのworkflow、レポート/索引、小容量validationの7ファイルだけである。

## 4. 検証条件・結果

### 失敗と再実行

| 操作（各環境のAPIとCLI） | 実際の結果 |
| --- | --- |
| 3.038〜3.042秒を要求 | ValueError、完成先なし、partial/failure.jsonのみ |
| 同じ出力先へ0.002〜0.006秒を要求 | FileExistsError、partial全byte保持 |
| 別出力先へ0.002〜0.006秒を要求 | complete、138の全数値/metadata/summaryと一致 |
| 完成先へ同じ処理を再要求 | FileExistsError、完成先と旧partial全byte保持 |

source/導入各8、計16workerで、予備実行は行っていない。失敗記録は`state=incomplete, error_type=ValueError`で、成功summaryや配列は保存されなかった。失敗先は52byte、成功先は各16658byteだった。圧縮された4ms出力の大きさを、全夜の容量見積りに使わない。

正常出力は各環境2件×13配列＝26配列を138へ直接一致確認し、両環境の全科学JSONも一致した。成功時の読取は各局4frame、8局合計32frame、guarded_seekの開始sampleは全局0だった。これは短い冒頭の正常処理である。末尾失敗の実読取frame数はsummaryが残らず測っていないためnullとした。飛ばしたprefixの全header検証とも別である。

### 容量・時間・メモリ

| 環境・各8worker | workerの起動から終了まで | 各workerの生涯peakRSS |
| --- | --- | --- |
| source | 0.589〜1.003秒 | 122.4〜222.6MiB |
| installed | 0.597〜0.997秒 | 122.9〜223.0MiB |

wall timeはPython起動・依存import・毎回8 VDIFのfresh SHA（100,003,840byte）・metadata照合・API/CLI・記録を含む。peakRSSはLinux RUSAGE_SELFのru_maxrss×1024で、相関処理だけの増分メモリではない。単発・cache制御なしで、コールド/ウォームの速度比較、throughput、最低PCや全夜/GPUの測定ではない。各環境の全検証出力は16MiB上限内だった。

### 試験と再利用した正式基準

| 対象試験 | source | 導入済み |
| --- | ---: | ---: |
| input_identity・sequence・aligned_session | 19成功 / 48.92秒 | 19成功 / 48.07秒 |
| 既存警告 | 7272 | 7272 |
| 除外 | 0 | 0 |

製品103 file＋参照4assetは138 wheel/source/導入先と全byte一致。新full/collect/wheel/導入/ブラウザは実施していない。[138正式記録](../../validation/runs/stage138/verification.json)の両全2321成功（542.82/541.45秒、各30220警告、除外0）と両実GUI28worker/56downloadを引用し、139の新成功へ加算しない。

[全科学値](../../validation/runs/stage139/reference.json)、[正式検証](../../validation/runs/stage139/verification.json)、[実測一覧](../../validation/runs/stage139/measurements.json)、[再実行条件](../../validation/runs/stage139/README.md)を保存した。公開監査指摘0、文書リンク1811件で欠落0。

## 5. 制約・未解決事項

ここでの再実行は、観測者が別の出力先を指定して最初から処理すること。partialから任意checkpointへ復帰する機能ではない。確認した失敗は入力末尾不足であり、電源断・容量枯渇・プロセス強制終了の全回復を確認していない。

131の仮定SEFD/供給clock/decoder scaleを使い、実RTL-SDR/OCXOのI/Q・UTC・時計精度・SEFD・beam・弱い実信号LO・実Cas A・低SNR画像尤度・実FFT独立性は未検証のまま。製品コードや画像性能を改善した段階ではない。

## 6. 次段階

140で二つの全体文書、計画、短い現状案内、入口、索引を技術基準139へ更新する。131〜139の失敗・未実施を維持する。150では専用の根本見直しを行う。継続期限2026-11-06 15:00JSTを維持する。
