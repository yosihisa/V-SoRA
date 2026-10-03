# 段階046：局の標本からvisibility雑音を推定する

- 作成日：2026-10-03
- 状態：完了（独立Gaussian電圧の有限標本モデルの範囲）
- 比較元コミット：d4f0519

## 読者向け概要

これまでの雑音検証では、模擬天体と受信機の真の共分散を与えていました。実観測で使える情報へ近づけるため、局信号の標本共分散と独立標本数から推定する式を検証します。

## 1. 目的・対象範囲

同じ独立Gaussian電圧標本から作った局共分散に基づき、visibilityの全実共分散を有限標本の偏りを補正して推定します。実機へ自動適用する処理や、filter後の有効独立標本数を測る処理は対象外です。

## 2. 完了条件

既知の真値を推定器へ渡さず、独立Gaussian電圧のMonte Carloで推定共分散の平均を理論と照合すること。未補正の偏り、補正式、複素gainの変換、Closureへの一次伝播を確認し、input拒否・source/wheel全回帰・配布API・レポート・匿名コミットを完成させること。

## 3. 実際に行った作業

- `vsora_simulator/visibility_noise_estimate.py`：局の標本共分散S_hat、同一の独立標本数M、基線番号からvisibilityの全実共分散・複素共分散・擬共分散を推定するAPI。真のsky/receiver情報を引数にしない。2〜32局、Mは局数以上。
- `apps/simulator/tests/test_visibility_noise_estimate.py`：2局の解析式、半正定値、局gain変換、Closureへの一次伝播、実Gaussian電圧の平均、入力拒否、全基線のbatch式との一致。
- `workflows/sample_noise_validation.py`：4局・M=4/8/64/512で各32768試行。2成分の局共分散と未知の複素gainを生成側でだけ使い、推定器には標本の局共分散とMだけを渡す。batch処理の最初の標本を毎回public APIと照合。条件・推定例・平均・Monte Carlo平均の標準誤差・半正定値性を保存。
- `tools/verify_sample_noise_installed.py`：[API規約](../../interfaces/sample-visibility-noise.md)、公開の小容量結果。

補正前のC_plugは、真のGaussian電圧共分散の式へS_hatを代入した値です。visibilityの実ベクトルm_hatを使い、`C_hat=(M² C_plug−m_hat m_hatᵀ)/(M²−1)`としました。仮定の下での平均の式から導いた補正で、真の共分散を実機で測ったという意味ではありません。

## 4. 検証条件・結果

### 対象試験・有限標本

対象27件成功、0.91秒。2局のGaussian電圧65536試行では、推定した複素共分散・擬共分散の平均が固定の6標準誤差＋丸め許容内でした。複素局gain変換と全基線batch式も一致しました。

本実験は4局、段階044と同じ2成分・受信機雑音1.5のモデルに、振幅[0.4,3,1.5,0.75]、位相[0.3,−1,2,1.1]radの局gainを掛けたものです。各条件32768試行、seed46〜49。真値は電圧生成と結果比較でだけ使います。標本平均は引きません。

| 独立標本数M | 補正前：推定共分散の平均の最大規格化誤差 | 補正後：推定共分散の平均の最大規格化誤差 | 半正定値の推定数 |
| --- | ---: | ---: | ---: |
| 4 | 0.105067 | 0.007885 | 32768/32768 |
| 8 | 0.046433 | 0.004441 | 32768/32768 |
| 64 | 0.006084 | 0.001301 | 32768/32768 |
| 512 | 0.001158 | 0.000386 | 32768/32768 |

規格化誤差は共分散の要素の差を、真の行・列分散の平方根の積で割った量です。**多数の試行を平均した推定値**の偏りを調べており、一回の観測の共分散がこの精度になるという結果ではありません。

全4条件で補正後の共分散の全要素の平均が6標準誤差＋丸め許容内でした。補正前も、理論から予測した偏りを含めた平均と同じ許容内でした。Gaussian visibility分布や実機の信頼区間を校正した検証ではありません。

Closureへの一次伝播では、取り除く偏りが共通の半径方向なので相殺され、補正後の共分散は補正前の`1/(1−1/M²)`倍になることを試験で確認しました。実運用の大きいMではこの補正効果自体は小さく、共有雑音を含む共分散構造を扱うことと区別します。

### 全回帰・配布・記録

- source全回帰325件成功、警告22672件、447.09秒。
- installed全回帰325件成功、警告22672件、449.15秒。source/wheelを順番に実行し、次段階の試験を作成する前に両方のcollectionを確定しました。除外した試験はありません。
- checkout外のinstalled API：2局8標本の複素共分散・擬共分散が解析式と一致し、真値不要・条件付きensemble不偏・visibility Gaussian分布保証なしの情報を確認。pip check成功。
- 既存のBaseband/NumPy・Starlette等のdeprecation警告を含みます。

wheel 5461603bytes、SHA256 `c3b26e344d766cc7bd8cccf207f207e64a1762eaca3926791564cd58fac79cec`。[Monte Carlo結果](../../validation/runs/stage046/summary.json)、[偏りの図](../../validation/runs/stage046/sample-noise.png)、[installed API](../../validation/runs/stage046/installed-api.json)、[全回帰・識別情報](../../validation/runs/stage046/verification.json)を保存しました。完全ログ・wheelはGit外`outputs/stage046-*/`です。

```bash
python tools/run.py workflows.sample_noise_validation --output outputs/new-sample-noise
python tools/verify_sample_noise_installed.py --output outputs/new-installed-sample-noise
```

電圧標本はメモリ上で作り、大量の標本自体は保存しません。モデル・seed・M・試行数、推定例と集計を保存します。文書追記の自動承認は初回timeoutしましたが、未変更を確認したうえで許可された一度の再試行が成功しました。

## 5. 制約・未解決事項

独立・平均0・proper complex Gaussian電圧、共通の標本集合、一定の局共分散という仮定です。実ADC/FIR/VDIF、RFI/mask、有効標本数、実機の信頼区間、Cas A復元品質は未検証です。

## 6. 次段階

観測側で保存する局power・複素相関・共通標本数を整理し、模擬相関器から推定共分散を出す入口を検討します。
