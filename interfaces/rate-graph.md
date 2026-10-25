# pilotの検出基線graph

段階111。保存した短pilotの基線走査を既存の局rate推定と共通に使い、局解を作れない場合も採用/棄却の理由を返す。画像化や新しい周波数推定法ではない。

```python
from vsora_correlator.rate_graph import diagnose_rate_graph
result = diagnose_rate_graph(spectral_data, reference_station=0,
                            max_rate_hz=100., min_snr=8., min_peak_z=8.)
```

入力は既存rate推定と同じ `(time, channel, baseline)` のcomplex visibility、非負の実/虚部逆分散weight、uniform時刻、基線局index。8点以上・3秒以内、時間Nyquist未満の探索を使う。基準局は入力pairsに存在する整数indexとする。元のpairsを保ってweightを0にすれば、使えない局も孤立局として記録する。pairs自体から局を消した場合、その局の存在をAPIが推測することはない。

schema_version 1の主な出力：

| 項目 | 意味 |
| --- | --- |
| `state` | 採用基線で全入力局がconnectedかdisconnectedか |
| `baseline_estimates` | 既存走査と同じ基線rate、coherent SNR、peak量、採用bool、棄却理由 |
| `components` | 採用基線で行き来できる局のグループ。各groupとgroup先頭をsort |
| `reference_component` | 基準局を含むグループ |
| `stations_outside_reference_component` | 基準局から到達不能な局 |
| `isolated_stations` | 採用基線が一本もない局。非自明な別groupとは区別 |
| `graph_rank / required_graph_rank` | 局数−group数 / 局数−1。連結の必要条件 |
| `rejected_baselines` | 理由別の基線数。存在しない理由を測定した0で補わない |

診断器は局解を求めず `station_solution_attempted=false` とする。連結しても基線差の整合性・物理的な位相安定性・Nyquist aliasは別に確認する。閾値8は探索後の誤検出確率を校正した値ではなく、`false_alarm_probability_calibrated=false` のまま扱う。天空や局gainの真値は入力しない。

```bash
python -m vsora_correlator.rate_graph --input pilot.npz --output graph.json
```

入力検証・診断後に、新しい出力へ排他的に書く。旧 `estimate_station_rates` の成功JSONと失敗時ValueErrorは維持する。新CLIは失敗理由を含む診断をJSONで保存できるが、そのことを旧推定の成功へ読み替えない。

同じ保存pilotのprefix比較と、その限界は[段階111](../docs/reports/111-pilot-rate-graph.md)を参照。長い原本、補正後相関、画像化を本段階で再実行したものではない。
