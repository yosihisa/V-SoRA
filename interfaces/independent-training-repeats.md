# 独立した学習・評価の反復

既知点源/Cas Aの参照分類を、学習・評価の両方を作り直して繰り返す。[段階098](../docs/reports/098-independent-training-repeats.md)のAPI/CLIであり、画像尤度・実機の信頼区間は定義しない。

## 実行

ソースから：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .verification-venv/bin/python tools/run.py vsora_simulator.independent_training_validation --profile full --output outputs/repeated-training
```

導入済み環境から：

```bash
python -m vsora_simulator.independent_training_validation --profile full --output repeated-training
```

出力先は新しいフォルダにする。既存出力へは上書きしない。`smoke`は少数のソフト確認用で、正式なMC精度の確認には使わない。いずれも同梱された既知天空・仮定SEFDを使い、実観測の入力は受け付けない。

## API

- `case_plan(profile='full')`：固定計画を返す。fullは7条件・各16反復、各ラベルの学習32/評価128、M512または19200。smokeは3条件・各3反復、学習8/評価16、M16。
- `experiment(case, progress=None)`：case_planから得た一条件を実行する。計画を任意に変更して渡す用途には使わない。
- `run(output, profile='full', progress=None)`：全固定条件とsummary、条件別JSON、図を保存する。
- `independent_replicate_summary(values)`：独立反復を単位とした平均、標本SD、平均のMC標準誤差、min/maxを返す。2〜64個の有限実数、各0〜1を受け付ける。masked・複素数・非数・不正shape、表現不能な正の統計量は拒否する。

集約APIは反復の独立性を数値だけから検証できない。呼出側の生成条件・seed/roleがその根拠になる。CLIは固定したseed_baseに反復番号を加え、role0/1を二ラベルの学習、2/3を二ラベルの評価として分離する。評価用データで方向・閾値・条件を選び直さない。

## 結果と統計単位

summaryのtypeは`known_template_independent_training_repeats`。fullでは112個の独立した学習/評価の組と35,840生成windowを保持する。各反復の学習model、全評価score、誤判定件数・率・個別二項区間、正答率とAUROC、gainの有限確認を保存する。

`metrics`は外側反復の平均・標本SD(ddof=1)・SD/sqrt(R)を持つ。学習と評価の両方の変動を含み、学習だけの変動ではない。複数学習modelの誤判定を一つの二項区間へ合算せず、AUROCの全組合せ対を独立標本と数えない。個別二項区間は、各反復の固定した学習結果に条件付く。反復のSDやMC標準誤差が0でも将来のリスク0とはしない。

## 保存容量と照合

全model/scoreはGit管理外のnative出力へ保持する。公開記録には全反復の評価値・個別区間・seed、model/scoreを`json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)`で表したcanonical JSONのSHA-256、全summaryのbyte SHA-256を保存する。再現には固定計画・同梱設定/天空のSHA・依存版を参照する。同じ環境でsource/wheelを全JSON照合する確認と、異なる環境でのbit一致の保証を区別する。

## 適用範囲

Gaussian電圧、独立mode、既知形状・仮定受信機モデル、一window内の一定局gainという参照条件である。M19200を64kHz×0.3秒とみなす解釈は実FFTの測定ではない。実SEFD・未知LO・量子化・RFI・実Cas A画像化・低SNR画像尤度・全夜/GPU性能は未検証。段階099より同梱日本語GUIの「動作検証」から同じ固定計画を実行できる。全model/scoreはnative summary downloadで取得する。

公開metricsのtypeは`known_template_independent_training_metrics`で、native summaryとは別形式である。共通の生成共分散等はcaseの`shared_generation_metadata`へまとめ、各反復のgenerationには差分を持つ。共通dictへ差分dictを重ねると元の生成metadataを復元できる。
