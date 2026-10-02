# 段階016：実データ用CASAアダプター

- 作成日：2026-10-02
- 状態：完了（V-SoRA v2/v3・1band/XXの限定profile）
- 比較元コミット：d2e3656

## この段階の読み方

実FITS内の値と重みを使い、CASAの作業形式へ渡せるようにしました。模擬試験専用の正解ファイルがなくても、変換前後の相関値と条件を照合できます。

専門用語は[用語集](../guide/glossary.md)、画像と誤差の意味は[結果の読み方](../guide/03-results.md)を参照してください。以下の数値・失敗・実行条件は当時の記録です。

## 1. 目的・対象範囲

較正後のFITS-IDIをCASA Measurement Setへ渡す。simulationの期待値ファイルなしで、元のchannel重みとflagを保存する。

## 2. 完了条件

FITS自身からbridgeを生成し、CASA実import後の値・局順・時刻・周波数を照合。元のNORMAL逆分散を復元し、偏心点源画像の位置・fluxを確認。古いprofile・checksumなしは拒否。全回帰成功。

## 3. 実際に行った作業

- `vsora_formats/casa.py`、相関CLI `casa-input`：actual FLUXとmetadataをNPZ bridgeへ保存。FITS checksum、profile、finite数値を検査。入力SHA256はstream計算。
- `tools/import_casa.py`：独立CASA環境でimport、DATA/UVW/局番号/時刻/周波数/露光を照合。WEIGHT/SIGMAとchannel列を復元。ゼロ重みからFLAGとFLAG_ROWを設定。
- scientificデータと較正期待値を混同せず、入力FITSを変換の基準とする。complete/incomplete summaryを残す。
- `interfaces/fitsidi-profile.md`に実行方法を追記。

## 4. 検証条件・結果

```sh
.verification-venv/bin/python tools/run.py pytest -q
.verification-venv/bin/python tools/run.py vsora_correlator casa-input --input validation/runs/stage013/point-8channel.fits --output outputs/stage016-bridge.npz
python3 tools/run_casa.py tools/import_casa.py --input validation/runs/stage013/point-8channel.fits --bridge outputs/stage016-bridge.npz --output outputs/stage016-casa-import --image
```

- 全回帰 **71件成功**、既知Baseband warning745件。
- 4局/60行/8channel、channelごとに異なる重み、ゼロ重み1件。入力FITSとCASAのDATA、UVW、時刻、周波数、露光の比較誤差は今回の保存精度で **0**。
- 入力float32重みとWEIGHT_SPECTRUMが完全一致。偏心点源dirty peak `[67,66]`、**1000.000793 Jy/beam**（生成真値1000Jy）。先行独立期待値確認と同じ結果。
- 旧v1、checksumなし、出力上書きを拒否。
- CASA 6.7.6.14。未知telescopeと主ビーム未提供のwarningあり。既知条件として扱い、主ビーム補正を検証したとはしない。

数値：[CASA summary](../../validation/runs/stage016/casa-summary.json)。MS/bridge/画像は`outputs/stage016-*`に保存、Git管理外。

## 5. 制約・未解決事項

限定profileとshard単位のメモリ処理。CASA依存はoptionalで、通常wheelに含めない。確認画像はdirtyのみ、Cas AのCASA CLEAN・主ビーム・実測データは未検証。MS directoryの存在だけで完了とせずsummaryを見る。

## 6. 次段階

局別channel powerとspectral kurtosisを使ったRFIの診断・flag伝播を作り、bandpassで異なる雑音重みを保存する。
