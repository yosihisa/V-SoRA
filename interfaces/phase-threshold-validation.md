# 位相探索scoreの閾値を独立学習・評価する参照

`vsora_simulator.phase_threshold_validation` は、既知振幅・SEFD・固定点源/Cas Aの位相探索scoreから、学習電圧で閾値を決め、別の評価電圧へ固定適用する。未知画像・未知振幅/SEFD/LOを解く実装ではない。GUIへは未接続。

```python
from vsora_simulator.phase_threshold_validation import learn_threshold, case_plan, experiment, run
model = learn_threshold(point_training_scores, casa_training_scores)
summary = run('outputs/independent-phase-threshold', profile='full')
```

```bash
python -m vsora_simulator.phase_threshold_validation --output independent-phase-threshold
# sourceでは python tools/run.py vsora_simulator.phase_threshold_validation ...
```

## 学習規則

入力は各群1〜65536個の有限実score。bool・complex・文字列・欠損・非有限値を拒否し、float64へ変換する。`score > threshold` をCas A、同点を点源とする方向を固定する。方向を反転して最良結果を選ぶ処理はない。

候補は全unique学習score、0、有限に表現できる最小score直下。学習点源の偽Cas A数をFP、学習Cas Aの見逃し数をFNとして、`FP*n_casa + FN*n_point` が最小の候補を採る。これはbalanced errorに比例する整数値で、sort/searchsortedから計算する。同率なら閾値の絶対値が小さいもの、次に値が小さいものを採る。評価score・真の局位相・oracle scoreを学習器へ渡さない。

## 固定実験

`full` はM512/19200・SEFD約585966 Jyの弱い2条件と、M512・SEFD1000 Jyの等C零天空1条件。各labelの学習64、評価64、計768window。1.42 GHz・最大600 m・8局・天体1000 Jy（零天空は0）というモデル仮定を使う。`smoke` は2条件・計32windowの動作確認専用。

学習の乱数roleは10/11、評価は20/21と分ける。生成法と位相探索は段階104の部品を再利用する。両候補の振幅/SEFDは与え、真の局位相はoracleだけへ与える。各評価電圧にoracle、固定閾値0、学習閾値を適用し、三つの予測を保存する。

学習profile scoreに未解決があれば学習閾値はnull。評価に未解決があれば、その方法の全体指標をnullにする。成功例だけの性能を全体性能として出さない。個別95%二項区間は一回の固定学習結果に条件付けた評価誤り率で、学習変動は含めない。AUCは同じraw profile scoreの順位なので、閾値の変更では変化しない。

`cases/*.json` と `summary.json` に全学習/評価score、閾値、誤り数・区間、再現seed、入力asset SHAを保存する。既存出力は上書きしない。case辞書の書換えも拒否する。[段階107](../docs/reports/107-independent-phase-threshold.md)に正式結果・制約を記録する。

`data.*.rows` の `profile_prediction_casa` は元の固定閾値0の判定で、評価行に追加した `learned_prediction_casa` が学習閾値を適用した判定。両者を混同しない。学習行へ学習後の評価予測は追加しない。
