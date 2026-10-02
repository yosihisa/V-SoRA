# 段階009：ADC時計と分数sample整列

- 作成日：2026-10-02
- 状態：完了（bandlimited参照補間・強い共通信号の時計推定）
- 比較元コミット：2c1ec2a

## 1. 目的・対象範囲

LOの位相rateとは別のADC sample時計差を扱う。分数sampleの開始時刻、一定sample rate誤差、幾何遅延を連続解析波形で確認する。実観測の弱い相関から時計を回収できるとはまだ判定しない。

## 2. 完了条件

順方向の連続多周波数波形から、既知時計の再sampleで誤差0.0006以内。未知の線形時計mappingを3条件で推定し、補正後相対誤差0.1%以内。入力端やband edgeを拒否し、invalidを伝搬。幾何遅延とRF位相の符号を独立確認。

## 3. 実際に行った作業

- `apps/correlator/.../clock.py`：有限windowed sinc（radius32、65 tap）、小chunkで補間。guard sampleを要求し外挿禁止。無効区間に掛かるsupportを無効にする。
- 実sample rateと開始時刻から共通physical timeへ変換するAPI。必要な有効bandwidthを明示し、この参照補間ではNyquist端に20%のguardを要求。
- 強いrate補正済み共通信号用の時計推定：segment相互相関の粗いlag→連続mappingの最小二乗。常定位相・利得はnuisance parameter。
- `workflows/clock_validation.py`と4tests：解析的に任意時刻の波形を生成。補間器と同じ生成法を使っていない。

## 4. 検証条件・結果

```sh
python tools/run.py pytest -q
python tools/run.py workflows.clock_validation --output outputs/clock
```

FS65536 Hz、0.5秒、32個の連続complex tone、帯域端±0.35FS、noiseなし。clock offset/sample rate誤差は（3.25sample,+80ppm）、（-2.4sample,-65ppm）、（0.3sample,0ppm）。異なるcomplex利得も注入。

- 推定ppm：80.000038、-65.000029、0.0000098。offset最大誤差0.00000245 sample。
- 補正前相対誤差0.362～1.188、補正後 **2.01e-5～2.39e-5**（約0.002%）。
- 連続幾何試験：RF1.42 GHz、delay 0,+1.4,-0.7 μs。時刻を`t-delay`でqueryしRF位相を負符号で戻すことで、各局が解析的基準波形と誤差0.0006以内で一致。
- 全テスト **48件成功**（追加4件）、Baseband既知warning41件。

詳細：[summary](../../validation/runs/stage009/summary.json)。模擬サンプルは解析式から再生成可能。

## 5. 制約・未解決事項

- 未知時計推定は強く共通なdeterministic waveformで確認。RTL-SDR/Cas Aの低SNR、RFI、LO未補正条件は未検証。
- 推定offsetは天体方向の幾何delayと時計offsetの和であり、幾何を別に与えなければ分離不能。
- 一定の線形sample driftだけ。温度変化等による非線形driftは区間分割・再推定が必要。
- finite sincは一般のdownsample用anti-alias filterではない。実際の有効帯域をguard内へ制限する前処理が必要。
- この段階は65536 Hzの正しさ確認。2.048 MHz×多局の長時間処理速度、GPU最適化、sessionへの時計自動適用は未評価。

## 6. 次段階

session manifestからVDIFをstream相関するCLIを作る。raw ADCの相関値と較正Jyを区別し、実データを受け取る入口と保存規約を整える。
