# 172：SigMF pilot/rate/補正相関の検証方法

[report](../../../docs/reports/172-sigmf-rate-pipeline.md)と[契約](../../../interfaces/closure-pipeline.md#sigmfの相関保存専用入口)を参照。原本・提供metadata・派生波形/科学JSON/NPZ/図は公開しない。

保存済み `outputs/stage038-sequence/input/` の相互に異なる模擬4局を使い、全SHAを先に固定する。生成を再実行せず、先頭70有効frameから固定code-unit尺度を派生する。各286720 complex sample/供給Fs2.048MHz/公称.14秒。131やCAMRASの再生成・再取得・再相関は行わない。

```bash
.verification-venv/bin/python tools/run.py workflows.sigmf_pipeline_validation \
  --prepare --input outputs/stage038-sequence/input --output outputs/stage172-input
.verification-venv/bin/python tools/run.py workflows.sigmf_pipeline_validation \
  --input outputs/stage172-input --output outputs/stage172-source-study
```

両方とも新しい出力先を使う。元原本のscaleとは別の固定71に対応する `2*byte-255` を使い、旧171 installedのVDIF対照も同じ71尺度で保存する。FFT32/pilot128blocks×64/start.002秒/final.1秒/max_rate100Hz/constant/raw U3保存を固定。独立作用は保存推定rateとgeometryを条件に、直接畳込み・chunk補間・RF/rate位相・FFT平均を計算する。RTOL1e-10/ATOL1e-7 ADC²。実時計・EOP・rate推定全体の確率校正ではない。

新source/installedの全NPZ fieldと決定的summaryを一致させ、VDIFは旧171対照にも一致させる。両新target/collect/full、wheel/pipcheck/105製品+4assets全byte、checkout外API/実CLI、両実Chromium28条件を選択。旧151/168/169/171 prefixは保持する。正式中source/tests/tools/workflowsを固定し、全worker終了前に修正しない。

stage3600秒/full・GUI各900秒/reference120秒/製品study追加peak256MiB/保存64MiB/全追加2GiB/空き10GiB reserve/公開512KiB。最終attempt2で全選択成功。両116対象/collect・full各2441成功・各32260既存種別warning/除外0、各42field一致/旧171 VDIF一致、105+4全byte、checkout外API/実CLI/両実GUI28条件を確認。非上書き4件の非zeroは意図した拒否。初回収集1errorを保持し成功を合算しない。失敗や訂正は削除せず管理外 `outputs/stage172-*` へ保存する。
