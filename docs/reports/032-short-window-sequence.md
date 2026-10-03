# 段階032：同一VDIFの短window列とLO再推定

- 作成日：2026-10-03
- 状態：参照実装・有限検証完了
- 比較元コミット：1d1c03d

## 読者向け概要

一つの記録を短いwindowに分け、各windowのLO差を推定し直します。補正した相関を時刻ごとに保存し、最後にClosure＋RMLでまとめます。3windowの模擬VDIFで周波数差の変化を回復できました。windowの内部では一定LOと正確なsample時計を仮定し、実機の不規則な位相変化を回復した結果ではありません。

## 1. 目的・対象範囲

同じ原本から2〜64windowのpilot・rate・相関・合成を処理。LOはwindow内一定、window間変化を検証。原本変更・途中の短い入力では完成扱いにしない。未知時計、連続LO曲率、弱信号統計、実機、GUI入口は次段階。

## 2. 完了条件

- 原本VDIFの3windowで局LO差の変化を回復し、各profileの有効範囲内で相関。
- 使用露光とwindow spanを分離し、相関を時刻別のまま合成へ接続。
- 非重複、不正格子、入力不足/変更、no overwrite、失敗位置を確認。
- source/wheel/checkout外CLI、レポート・匿名監査・コミット。

## 3. 実際に行った作業

`sequence.py`を追加。step省略時はpilotspan、2〜64window、3秒/100万cell以内のpilot、画像積分のcoverage・整数VDIF/FFT格子、非重複を前検査。各windowで独立のrate profileを推定してIQを補正し、最後に合成する。全window・最終RMLが終わるまで親output.partialを保持する。

`closure_pipeline.py`にcorrelation_onlyを追加。3工程のspectral出力を作り、個々のwindowでの画像化を省いて最終合成へ渡す。通常の5工程の入口は維持。pyprojectに配布CLI`vsora-sequence`を追加。

原本・manifest/clock/観測設定のSHAを各windowで計算して一致を確認。device/inode・size・mtime/ctimeを開始時とwindow後/合成後で比較し、入力変更を検出すれば完成にしない。SHA読取の再利用は後続。

`vdif_closure_validation.py`の生成器へ連続phaseのrate変化を追加。`sequence_validation.py`でLO推定と画像の図を保存。`test_sequence.py`、`verify_sequence_installed.py`、観測入門・入出力規約を追加/更新。

## 4. 検証条件・結果

4局、1.42GHz、Fs2.048MHz、FFT32、800frame=1.6秒。連続band-limited Gaussian点源1000Jy・SEFD10000Jy、未知の一定gain、正確な公称sample時計・zero offsetを供給。入力source.model=unknownでfluxを渡さず、生成条件は評価側だけに保持。

pilot一cell2ms・256cell=0.512秒、start0.002/0.514/1.026秒。phaseを連続にしたまま、LO差をpilot境界0.514/1.026秒で切り替える。基準局との差は次の生成条件。実OCXO値ではない。

| window | 生成した局差[ST01,ST02,ST03,ST04]Hz | 最大station rate推定誤差 |
| --- | --- | --- |
| 0 | [0,17.3,-11.7,26.1] | 0.015869Hz |
| 1 | [0,31.2,-6.3,14.4] | 0.018341Hz |
| 2 | [0,-20.5,13.7,4.3] | 0.007687Hz |

各rate profileの時刻・有効範囲を保持し、別windowへ外挿しない。各画像積分0.3秒、使用露光は一局0.9秒。pilotのstart-to-end span1.536秒と区別。有効baseline露光も0.9秒、3時刻の複素値・channel・UVW・重みを保持し、先に複素平均しない。後方windowでは開始global sample1048576/2097152からguard付き部分読取を使用。

| 確認 | 結果 |
| --- | --- |
| 相関window／工程 | 3/3、各3工程＋最終合成＝10工程完了 |
| Closure | phase156、log amplitude78、独立phase117/amplitude78 |
| 保存単位 | ADC²、最終画像は相対flux総量1、絶対位置/fluxを測定せず |
| 最終RML | χ²/測定数0.7341。3探索のうち2つは293/307回で停止条件到達 |
| 選択したRML | 最小目的関数の探索は800反復上限、停止条件未到達。処理完了と収束を区別 |
| source / installed wheel回帰 | 各162成功、8968既知deprecation warning |
| checkout外CLI | 新入口help・実3window解析成功、全数値相関配列はsource参照と一致 |

点源の処理接続とLO変化の確認で、Cas Aの良好な形状復元ではない。

- 短い入力で2window目のpilotが不足：completed_windows=[0]、current_window_index=1、親incomplete。1window目の相関を保持し、最終画像を作らない。
- 1window後に同じbytesのclock fileのmtimeだけを変更：input stat変更を検出してincomplete。閉じた原本の条件を守る。
- 最終合成のunit模擬例外：completed_windowsを保持し、phase=synthesis/current_window_index=null。実相関の検証とは区別する。
- 間隔の重複、pilot coverage、時刻数、非有限pilot、不正画像格子を前検査。既存output/partialを上書きしない。

```bash
python tools/run.py workflows.sequence_validation --output outputs/stage032-sequence-final
python tools/run.py vsora_correlator.sequence --manifest manifest.json --clock-model clock.json --window-count 3 --integration-s 0.3 --output outputs/sequence
python tools/run.py pytest -q
```

[生成条件・原本SHA・全結果](../../validation/runs/stage032/summary.json)、[局所LOと相対画像](../../validation/runs/stage032/rates-and-image.png)、[checkout外CLI](../../validation/runs/stage032/installed.json)、[回帰とwheel識別](../../validation/runs/stage032/verification.json)。原本・wheel・ログ・各windowの大容量成果物はGit外outputs/stage032-*。図は同じ保存結果から再生成する関数をworkflowに含める。

## 5. 制約・未解決事項

境界を知って並べた模擬windowの内部ではLO/gainが安定している。自動で位相安定時間を検出したり、非線形位相雑音を回復したりする処理ではない。実sample時計を供給、高SNR Gaussian Closure、filtered noise/self-noiseの独立近似、局所解と反復上限がある。全原本SHAを毎window読むため長記録の費用が残る。自動resume/弱いwindowのskip、64window超、実機・GUIは未実施。

## 6. 次段階

重要な実運用入口として短window列を日本語GUIへ接続する。区間ごとの進捗・局LO差・露光・途中失敗・最終RMLの停止状態を分かりやすく示し、配布ブラウザで確認する。その後、原本識別の安全な再利用と低SNR/位相安定時間を検討する。
