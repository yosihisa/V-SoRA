# 段階010：session manifestとstream相関CLI

- 作成日：2026-10-02
- 状態：完了（共通frame時刻、単一XX、point pilot限定）
- 比較元コミット：526ee03

## 1. 目的・対象範囲

Windows収録なしでも実ファイルを渡せる入口を作る。raw ADCをJyと取り違えず、VDIFを順次相関してshard保存し、既知点源で較正・画像化するCLIを接続する。

## 2. 完了条件

manifestの局順・時刻・量子化倍率を検査。memory保持を1積分IQ＋指定個数spectralに制限。raw ADCから較正Jyへ単位を変更。実CLIを呼ぶ2pass通し検証と全回帰成功。失敗出力・上書きを明示。

## 3. 実際に行った作業

- `apps/correlator/.../session.py`, `__main__.py`：correlate/calibrate/apply。成功時だけpartial directoryをrename。
- `interfaces/session-manifest.md`：4096sample/frame、局順・unit・scale・時刻等の受渡しとpilot手順。
- spectral v2：generic `visibilities`、Jy/ADC^2明示。rawから`vis_jy`別名を提供しない。VDIF sidecarもADC/sqrt(Jy)を区別。
- `geometry.py`：明示した収録時刻でuvwと局delayを計算。低高度行を落とさずweight=0にする。
- phase/rateの原点が異なる較正の合成を修正・検証。IQで既に除去したrateを再適用しない。
- 幾何配列追加で既存simulatorのJSON出力が失敗した回帰を、数値配列とmetadataを分けて修正。

## 4. 検証条件・結果

```sh
python tools/run.py pytest -q
python tools/run.py workflows.session_cli_validation --output outputs/session-cli
```

実CLIによる4局、RF1.42 GHz、FS2.048 MHz、8ms×64、0.512秒、未知ADC振幅・delay・rate、SEFD10000 Jyの模擬点源。位相中心の既知1000 Jyで2pass較正。

- 相関前ADC、相関後ADC^2、較正後Jyを確認。
- 平均visibility相対誤差 **0.8849%**。
- dirty/restored peak **1000.000003 Jy/beam**、CLEAN model sum **991.272 Jy**、収束。両者は別の量であり同一扱いしない。
- 1shard、実時間span0.512秒。予定600秒を露光600秒として保存していない。
- frame間の局ID不一致は失敗し最終directoryなし。partialのfailure stateを確認。4shard分割、上書き拒否、較正原点合成、unit切替を含め **52件成功**。
- Baseband既知warning553件（追加のVDIF書込み回数に伴う増加）。

記録：[summary](../../validation/runs/stage010/summary.json)、[画像](../../validation/runs/stage010/images.png)。量子化ファイル・manifest・shard・較正・FITSはGit管理外`outputs/stage010-session-cli-final`。

## 5. 制約・未解決事項

- 現CLIはtimestampが同じ4096sample EDV0 frameを要求。整数sample開始差・消失frame・clock補間APIの自動組込みは未対応。
- 幾何は積分中央の周波数位相補正。有限FFT内部のdelay端損失はまだ除去しない。
- `calibrate --point-flux-jy`は既知の位相中心点源専用。Cas Aを全baselineで1000 Jy一定として扱うと誤較正になる。shapeモデル較正は次段階。
- この通し検証は同じpoint記録で2pilot。異なる天体・時刻への較正転送は未確認。
- 逆分散はtotal powerからの近似。RFI/bandpass/主ビーム/偏波補正は未実装。
- spectralを細かいまま長時間保存すると出力容量も大きい。pilot後のrate/clock補正と時間・帯域平均を設計する必要がある。

## 6. 次段階

既存環境参照に頼らないwheel導入・実行を確認し、再現可能な依存環境を保存する。Cas A shapeモデルの較正と実観測に必要な情報を拡張する。
