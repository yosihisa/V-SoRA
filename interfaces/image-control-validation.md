# 画像誤差を調べる評価専用の対照

段階114。3seed・最終3秒の相関を、既存RMLの3初期値で比較する開発用workflow。未知データの推定法を新たに完成させた段階ではない。

```bash
python tools/run.py workflows.image_control_validation \
  --reference outputs/stage113-source-study --output outputs/image-controls-new
```

| 枝 | 入力 | 真値の使い方 |
| --- | --- | --- |
| `estimated_rate` | 113の保存済み推定rate相関 | 推定に供給しない。評価だけ |
| `truth_rate_control` | 同じrawを真の局rateで再相関 | 補正に真のrateを供給する評価専用対照 |
| `ideal_model_observed_snr_control` | 同じuvの理想モデルvisibility | 理想化した対照データの生成に真の天空を使う |

RML自体の初期画像・priorへ真値を渡さず、既存Gaussian priorを使う。全枝starts3/max_iterations2000、SNR10、その他113設定を固定する。基準枝のstart0は113のstart0と全科学値を照合する。最小目的関数のrunを選ぶ従来規則を維持し、未収束のrunが選ばれた場合もその状態を示す。

理想対照は `W_model = W_obs * (abs(V_obs) / abs(V_model))**2` としてSNRを保つ。これはJy較正ではなく、観測時と同じ選別・近似誤差尺度を与える人工重みである。全有効maskと近似baseline varianceが一致することを確認する。正weightの位置でmodelが0、不正配列、数値overflow・SNRを保てない範囲は拒否する。

理想データのmetadataはevaluation-onlyと人工weight、元観測SHAを明記する。親データのclock/rate適用済み・ADC power等のmetadataをコピーして、実観測の処理結果に見せない。真のrate profileも評価専用と明示し、旧推定の共分散や誤差・基線fitを引き継がない。

導入照合は3つの真値rate相関CLIと9つのRML CLIを実行する。理想モデルは導入APIで独立に再構成し、SNRからの別の重み計算とmask/varianceを確認した後、固定した対照入力でRMLを比較する。経過秒・入力archive SHAを除く全RML科学JSON、画像と相関配列、全比較metricを照合する。[段階114](../docs/reports/114-image-controls.md)を参照。
