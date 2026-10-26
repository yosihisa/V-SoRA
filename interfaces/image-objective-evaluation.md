# 候補画像の目的関数を評価する

段階115。復元済み画像や比較用画像に対して、現行Closure＋RMLと同じ損失を計算するAPI/CLI。画像を最適化したり、真の形状を認定したりする処理ではない。

```python
from vsora_imaging.objective_evaluation import evaluate_closure_image
result = evaluate_closure_image(uvw_lambda, visibilities, weights, pairs, image,
                                pixel_arcsec=16., min_snr=10., prior_fwhm_arcsec=240.)
```

入力は既存RMLのvisibility・逆分散重み・基線・uvwと、有限非負の正方形画像（8〜64画素）。正の有限sumを必要とし、unit fluxへ正規化する。pixel_arcsecは明示必須。実数の設定値を受け、bool・NaN等を拒否する。高SNR独立Closureがない場合も評価不能として例外を返す。

主な出力schema_version 1：

| 項目 | 意味 |
| --- | --- |
| `candidate_sum_before_normalization` | 供給画像のsum。観測fluxの測定値ではない |
| `settings` | 実際の格子・SNR閾値・prior幅・正則化係数 |
| `metrics.data_loss` | 共有基線の共分散を含む現行近似の二次損失 |
| `metrics.entropy_loss / tsv_loss / centroid_loss` | prior・隣接画素差・表示中心へのpenalty |
| `metrics.objective` | 上記四項の和。unit-flux画像の損失 |
| `metrics.independent_closure_counts` | 実際に使うphase/logampの独立制約数 |
| `optimizer_executed` | 常にfalse。このAPIは最適化しない |
| `optimizer_parameter_sum_penalty_included` | 常にfalse。内部パラメータの総和を固定する補助penaltyは含めない |

現行RML summaryの `objective` と比較するときは、`parameter_sum_penalty` を除いて比較する。画像のスケールを変えてもunit-flux画像として同じ損失となるが、絶対fluxやastrometryを測ったとは扱わない。

同じdata・格子・重み・係数の中で候補を比較する。異なる入力の総objectiveを、そのまま科学的な優劣の順位へ使わない。現在の高SNR・wrapped local Gaussian近似を再利用しており、低SNR尤度や画像の信頼確率を検証するAPIではない。

```bash
python -m vsora_imaging.objective_evaluation --input visibility.npz \
  --image relative-model.npy --pixel-arcsec 16 --output objective.json
```

既存visibility loader（開発NPZ/限定FITS-IDI）とnpy画像を読み、入力・候補ファイルのSHAを追加する。検証後に新規JSONへ排他的に保存し、既存出力は上書きしない。詳細と固定27候補の照合は[段階115](../docs/reports/115-image-objective-evaluation.md)を参照。
