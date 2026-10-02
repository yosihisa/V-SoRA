# 段階008：IQから未知LO差の推定と再相関

- 作成日：2026-10-02
- 状態：完了（短時間・静止モデル）
- 比較元コミット：4a1c4cf

## 1. 目的・対象範囲

受信機の未知の周波数差をIQへ注入し、量子化・VDIF・短時間FX・較正・補正後平均まで検証する。連続観測の幾何追従やADC clock driftは別段階。

## 2. 完了条件

独立生成IQからdelay誤差20 ns以内、rate誤差0.08 Hz以内、平均visibility誤差3%以内。既知invalid frameを除外。VDIFの読み出しをフレーム単位にでき、既存結果を維持する。

## 3. 実際に行った作業

- `fx.py`：短時間series、周波数昇順、実有効FFT数、total powerから近似逆分散、IQのrate再位相補正。
- `vdif.py`：`iter_vdif_frames`でメモリを1frameに制限。便利な全読込みAPIはこのiteratorを使用。
- `fringe.py`：channel単体のSNRが低くても全帯域で検出される場合、noise分散を使ってモデル残差を判定。
- `workflows/iq_fringe.py`：未知局応答→VDIF→初回推定→**記録IQを再位相補正してFX再実行**→残留応答推定→平均。
- 新規integration tests：Parsevalによる独立相関値、LO再位相補正、低SNR、未知delay/rate、iterator一致。

## 4. 検証条件・結果

```sh
python tools/run.py pytest -q
python tools/run.py workflows.iq_fringe --output outputs/iq-fringe
```

4局、1000 Jy点源、仮定SEFD10000 Jy、FS2.048 MHz、128channel、8 ms×64積分、実露光0.512秒。未知delay最大2.3 μs、rate最大26.1 Hz、振幅0.8～1.2。8bit complex VDIFへ保存。1局の1frameをinvalidにした。

- 初回のモデル残差判定では、低いchannel別SNRをモデル不一致と誤判定。noiseを考慮して修正。
- 1pass後の平均visibility誤差 **3.605%** で完了条件未達。積分内で失われたcoherenceを事後補正では戻せないため2passに変更。
- 2pass後：平均visibility誤差 **0.5976%**、delay最大誤差 **1.88 ns**、rate最大誤差 **0.0144 Hz**、振幅最大誤差 **1.08%**。全局clipping fraction=0。
- 全回帰 **44件成功**、既知Baseband warning41件。iteratorで4096sample/frame、時刻・invalid mask・値が全読込みと一致。

記録：[summary](../../validation/runs/stage008/summary.json)、[較正結果](../../validation/runs/stage008/calibration.json)。量子化入力とspectral cubeはGit管理外`outputs/stage008-iq-fringe-v4`。

## 5. 制約・未解決事項

- 模擬信号はFFT周期的な静止snapshot。長時間連続の物理的伝搬を実装済みとは扱わない。
- total powerからの重みは独立receiver近似。既知1000 Jyモデルがfluxスケールを決める。raw ADC値を自動的にJyへ換算できるわけではない。
- 推定後の再相関にはIQの保持が必要。FFT内の周波数ずれ・band edge漏れは残る。
- frame iterator自体は bounded memoryだが、この検証workflowは短いデータを全読込み。長時間sessionのstream相関は未実装。
- ADC sample clock drift、整数sampleずれ・分数sample補間、欠落frameの自動充填は未対応。既知invalidは保持、消失frameは拒否。

## 6. 次段階

ADC clock差と分数sample時刻を、連続bandlimited波形の独立モデルで検証する。入力session manifestとstream処理を整備する。
