# 段階138：時計JSONの数値と真偽値を区別し、実入力契約を整理する

- 作成日：2026-10-27
- 状態：完了（Linux入力の型検査と固定模擬原本での回帰。実時計の精度推定ではない）
- 比較元コミット：6433f2a2c803eb8dbe80af182e0181552ae7c362（137）

## 読者向け概要

相関器には、各局がどの時刻の電圧を記録したか、その後どの速さでsampleを取ったかを渡す。これが時計JSONである。今回は帯域に数値の代わりにtrueを渡すと、1 Hzとして処理が通ってしまう不具合を直した。

Pythonではtrue/falseが数値の1/0として計算される場合がある。帯域が1 Hzへ化けると、有効とする周波数が変わる。画面に画像が出るより前の段階で、間違った入力から別のデータを作る問題である。数値欄の真偽値や不正な構造を、correlate_alignedの電圧bufferと相関出力/partialを作る前に拒否するようにした。上位pipeline/jobは失敗記録用のpartialや状態ファイルを先に作る場合がある。正しい設定の相関計算は変えていない。

## 1. 目的・対象範囲

将来の実RTL-SDR/OCXO入力をLinux解析側へ渡す際、形式として検査できることと、実機で確認すべきことを区別する。今回は既存correlate_alignedのclock検査だけをprivate helperへ整理し、新しいpublic preflight APIやWindows収録は追加していない。

同じファイルかを調べるInputIdentity、VDIF reader、LO推定、RMLは既存実装を利用する。SHAが一致することを、実I/Qの向き、時計の真値、ADC scaleやSEFDを測れたことと混同しない。

## 2. 完了条件

1. 修正前の実APIで、正しい時計と版数true/帯域true/局0 offset falseの4条件を固定131high_a原本へ通す。全結果と数値配列を保存する。
2. 修正後は不正な3条件を出力・partial・buffer作成前に拒否する。最後の局だけ不正な場合も、先の局のbufferを作らない。
3. 正しい4原本を4ms×1積分だけsource/導入APIと導入CLIで処理し、全数値・metadata・科学JSONを照合する。high_aは修正前数値とも完全一致する。
4. 対象試験・両全回帰、新wheel/導入prefix/全byte/pipcheck、両実ブラウザ、原本保持、文書・監査・匿名commit/pushを完了する。

4msは入力と数値の回帰確認に使う有限区間で、Cas A画像化の積分時間を推奨したものではない。

## 3. 実際に行った作業

主な変更はaligned.pyのprivate `_validated_clock_stations` と、その公開相関APIを通す44試験である。JSON object/array、整数版数1、有限な数値Hz/秒、局数/順序/keys、既存の帯域guardと1000ppm制限を全局分確認してからbufferを構築する。bool、文字列、非有限値、floatへ収まらない巨大整数等を数値として受け付けない。通常の整数/小数の数値は引き続き受け付ける。

検証用workflowと導入版検証tool、[実入力の確認表](../../interfaces/linux-input-readiness.md)を追加し、[clock規約](../../interfaces/clock-model.md)と[interface索引](../../interfaces/README.md)を更新した。本レポート・段階索引・validation記録も同じcommitへ含める。FFT、幾何、LO/rate補正、weight式、画像solverは変更していない。

## 4. 検証条件・結果

### 修正前の反例と修正後の拒否

| 時計条件 | 修正前API | 数値への影響 | 修正後API/CLI |
| --- | --- | --- | --- |
| 正しいcanonical | 完了 | 基準 | 完了・全数値保持 |
| schema_version=true | 完了 | 基準と同じ配列 | ValueError・出力なし |
| max_abs_baseband_hz=true | 完了 | weightsだけ変更 | ValueError・出力なし |
| 局0 input_start_offset_s=false | 完了 | 基準と同じ配列 | ValueError・出力なし |

帯域trueの反例では、正しい設定で正weightが84セルあったのに対し、28セルへ減り、56セルのweightが変わった。真偽値を1 Hzへ暗黙変換した結果であり、天体が変わった結果ではない。

反例の初回記録スクリプトは、全4条件の数値配列が同じになると誤って期待し、4相関の終了後にassertで停止した。帯域でweightsが変わることを確認し、完了済み4出力を再読込して記録した。相関を再実行した件数へ足していない。失敗した期待を隠さず、変更したfieldも残した。

### 正しい固定原本と原本追跡

APIはPythonから関数を呼ぶ入口、CLIは端末のコマンドから使う入口である。両方で同じ入力・出力になることを確認する。

131のhigh_a/high_b/weak_a/weak_bを各4ms処理した。全4のAPI/CLI科学JSON、52数値配列、全metadataが一致し、high_aの数値は修正前の正しい条件とも完全一致した。非上書きをAPIとCLIで各4件確認し、bool3条件はAPI/CLIで各3件拒否した。不正条件のcorrelate_aligned相関出力とpartialは作られていない。上位pipeline全体の全ファイルを作成前に拒否するという意味ではない。

InputIdentityで毎run新たに原本を識別し、公開131の全76入力SHAを保持した。四つの固定seedはnoise/gain/LOが同時に違う仮定付き模擬原本であり、雑音だけを変えた独立な実観測試行ではない。真の天空値を今回の判定へ読み込んでいない。sample clockとscaleは供給済みの参照である。

### 正式試験・導入・GUI

| 検証 | source | 導入済み |
| --- | ---: | ---: |
| 対象試験 | 75成功 / 10.17秒 | 75成功 / 9.76秒 |
| 全回帰 | 2321成功 / 542.82秒 | 2321成功 / 541.45秒 |
| 全回帰の警告 | 30220 | 30220 |
| 除外 | 0 | 0 |

今回は収集2321だけでなく、両2321を実行した。対象の警告は両5793件で、既存Baseband/NumPy等の警告を含む。44の新試験は型・構造・境界での実API拒否を確認し、最後の局の不正値でもbuffer数0・出力なしとなることを検査した。予備44/75と予備4原本は正式件数へ合算しない。

新wheel103 package file＋4assetをsource/導入先とbyte照合した。旧121wheelとのpackage差はaligned.pyの1ファイルだけである。依存ライブラリの版は変更せず、pipcheckは成功。初回のno-build-isolation方式は実行環境にsetuptoolsが無く失敗したため、専用の一時構築環境（setuptools84.2.1）で作り直した。初回stdoutと原因を保存し、full stderrは保存していないことも記録した。

導入側の試験parentはfixtureのためcheckout rootだけを探索場所へ追加し、製品moduleは導入prefixから読んだ。科学CLIはcheckout外・runner/PYTHONPATHなしで実行した。wrapper自体はcheckoutにあり、wheel-onlyの新しい検証製品ではない。

両実Chromium153.0.8010.12では137と同じ28worker/56実JSON保存を回帰し、672行・50null・174負・148の1超と全科学JSONが一致した。日本語390px、表の折り返し、ページはみ出しなし、JS/外部通信0を確認した。通常GUI8765は実所有・activejob0を確認して所有プロセスだけを停止し、更新後に再開した。

[全科学記録と修正前反例](../../validation/runs/stage138/reference.json)、[正式検証](../../validation/runs/stage138/verification.json)、[有限実行記録](../../validation/runs/stage138/measurements.json)を参照する。公開監査指摘0、文書リンク1800件で欠落0。

公開手順の最初の実行は、自動承認レビューのbuilder errorで実行前に停止した。安全性を理由とする拒否ではなく、レビュー処理を完了できなかったもの。HEADが137のままであること、対象13ファイルだけの変更、読み取り専用監査0件・文書1800リンク欠落0を再確認し、承認を迂回せず同じ経路へ再提出し、本commitの公開手順を実行した。

## 5. 制約・未解決事項

型が正しいことと、実機で正しい値を測ったことは別である。実I/Q向き、UTC/sample番号の対応、実sample rate、ADC scale、アンテナ応答/SEFD、弱い実信号のLO、実Cas A画像化、低SNR画像尤度、全夜/GPU性能は未検証のまま。今回のclock検査で解決したとしない。

原本SHAはbyteの識別で、全headerや物理量の正しさを証明しない。seekで飛ばした区間のheader検査や、全statを保つような改変の検出には既存の限界がある。有限の不正入力での拒否を、あらゆる破損や無限の値域の完全検査へ一般化しない。Windows収録は対象外である。

## 6. 次段階

139では所有する有限処理の失敗・非上書き・別出力先への再実行と、容量・時間の記録を点検する。完了/partial/失敗の区別と原本保持を確認し、一晩の性能へ無条件に外挿しない。140で全体文書を整理し、150で最終目標への寄与と残る律速を根本的に見直す。
