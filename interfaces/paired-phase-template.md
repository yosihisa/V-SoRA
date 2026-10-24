# 同じ電圧で既知位相と未知位相を比較する参照実験

`vsora_simulator.gaussian_phase_template` は、固定した点源・Cas A・零天空モデルの模擬電圧で、二つの比較方法を対にして調べる。1.42 GHz、最大600 m、8局、天体flux 1000 Jy（零天空は0）を仮定する。振幅・SEFDと二候補の天空形状は既知である。

## API・CLI

```python
from vsora_simulator.gaussian_phase_template import case_plan, experiment, run
plan = case_plan('full')
result = experiment(plan[0])
summary = run('outputs/paired-phase', profile='full')
```

```bash
# source
python tools/run.py vsora_simulator.gaussian_phase_template --output outputs/paired-phase
# wheel導入後はcheckout外でもnative moduleから実行できる
python -m vsora_simulator.gaussian_phase_template --output paired-phase
```

`full` はM=512/19200×SEFD=1000/10000/約585966 Jyの6条件と、等Cの零天空1条件。各label64window、計896window。`smoke` は3条件・計12windowの動作確認専用。case辞書の書換えや不明profileは拒否する。既存出力を上書きしない。

## 同じ入力と異なる情報

各windowで全局共通の独立proper Gaussian電圧を直接生成し、区間内一定の局位相Gを掛ける。同じ電圧の二次モーメントSから次を計算する。

- `oracle_score`：真のGを候補共分散にも与えた段階100の二候補対数尤度比。
- `phase_profile_score`：真のGを与えず、段階103で各候補の局位相を局所探索した後の尤度差。

真位相の乱数系列は電圧系列と分ける。両方法で別の電圧を生成しない。各windowは独立、局位相もwindow間で独立に引く仮定であり、実OCXOの時間変化を再現したものではない。

## 結果と未解決の扱い

`cases/*.json` と `summary.json` に各windowの対のscore、予測、探索状態・勾配、既知位相変換の差を保存する。各labelの先頭windowでは、Sを使わない直接電圧二次形式と、profileへの追加データ位相変換も照合する。

閾値は0で事前固定し、正ならCas A、同点なら点源。`metrics.oracle` と `metrics.phase_profile` にbalanced accuracy、AUC点推定、各labelの誤り率と個別95% Clopper–Pearson区間を保存する。区間は固定した生成条件と判定手順のMonte Carlo誤差を表す。AUCの比較対数を独立標本数にしない。balanced accuracyの信頼区間や実画像の信頼度を付けていない。

profileが未収束ならそのscore・予測は `null`、件数を残す。一つでも未解決windowがあれば条件全体のprofile指標も `null` にし、成功例だけの性能を全体性能として出さない。`oracle_by_profile_prediction_counts_on_resolved_only` は受理済みwindowだけの2×2表で、行がoracle、列がprofile、各軸の順序は点源・Cas A。分母の未解決件数も併記する。予期しない数値例外は未収束として隠さず停止する。

## 保証しないこと

phase profileは3局以上で大域解を保証しない。各候補の位相を合わせた差へ、既知単純二仮説の最適性・閾値0の最適性・χ²検定・画像確率を付与しない。低感度で判定が一方へ偏っても、すべての観測手法や画像化が不可能とは結論しない。

未知振幅・SEFD・LO、実FFT標本の独立性、実機Cas A画像化は未検証。全局共通Sを、別々の三角形標本から組み立ててはいけない。現行Closure＋RML、GUI、収録形式は変更しない。[段階104の正式結果](../docs/reports/104-paired-phase-template.md)を参照する。
