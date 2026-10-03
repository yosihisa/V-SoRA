# 段階040：線形rateの推定誤差を相関へ伝える

- 作成日：2026-10-03
- 状態：完了（条件付き計算・模擬VDIF・CLIの範囲）
- 比較元コミット：bed8fa6

## 読者向け概要

周波数差を推定して補正しても、その推定値には誤差があります。誤差による位相のずれが積分中に大きく変化すると、信号を平均した値が小さくなります。この段階では、推定された誤差だけから計算する診断を追加しました。実際のOCXOの揺れを測った値とは区別します。

## 1. 目的・対象範囲

線形rateの全共分散を使い、各基線・画像積分の条件付き複素coherenceを計算・保存します。局間の誤差の相関と、rate・傾きの相関を保ちます。診断の追加によって補正・相関・重み・合否条件を変えません。前段階の高速位相反例に適用し、診断の対象外であることを示します。

## 2. 完了条件

解析式、基準時刻・基準局の変更、不正入力、Gaussian乱数との照合を通すこと。保存済みプロファイルのSHAと数値、production CLIと相関数値の一致、source/wheel全回帰を記録すること。レポート・索引・匿名コミットを作成すること。

## 3. 実際の作業

- `rate_uncertainty.py`：入力プロファイル・共分散の順序、対称性、半正定値、時間範囲・基線を確認し、基線へ誤差を伝播。適応積分と数値誤差を保存。CLI `vsora-rate-uncertainty`を追加。
- `closure_pipeline.py`：線形モデルの画像積分について、`integration_uncertainty`をrate JSONとsummaryへ保存。区間列の各窓も同じ処理を使用。
- correlatorの単体試験、pipeline結合試験、`workflows/rate_uncertainty_validation.py`、`tools/verify_uncertainty_installed.py`、`pyproject.toml`、guide07、公開記録。

### 計算式と量の意味

局iの補正モデルを `r_i(t-e)+a_i(t-e)²/2` cyclesとします。eは推定基準時刻です。積分中央cの一定局位相を除くと、基線ijの位相誤差は

```text
δφ(t) = 2π [ (δr_i−δr_j)(t−c)
             +(δa_i−δa_j)((t−e)²−(c−e)²)/2 ]
```

パラメータ誤差の全共分散をC、式の係数をb(t)とすると、位相誤差の分散は `v(t)=b(t) C b(t)ᵀ`です。平均0のGaussian誤差を仮定すると、その特性関数から `E[exp(iδφ(t))]=exp(−v(t)/2)`となります。これを積分時間Tで平均した値を保存します。

これは `E[複素平均]`で、`E[複素平均の絶対値]`とは異なります。乱数標本から両者を別に計算しました。共分散を実機の正しい誤差分布と確認した実験ではありません。基準時刻を動かすとrateと傾きの共分散も変換する必要があり、対角成分だけでは結果を保てません。

## 4. 検証条件・結果

### 数式・Gaussian標本

一定rate誤差だけの場合のerf積分、零共分散、局間・rate/傾きの共分散の効果、基準時刻と基準局の変換、不正値・範囲外・非対称/非半正定値行列を単体試験で確認しました。

独立のGaussianパラメータ誤差65536組、seed40、6基線、積分0.2〜2.6秒について計算式と複素平均を比較しました。最大差0.001417、全基線が実験前の`6 × 標本標準誤差 + 0.00001`以内でした。これは既知の仮定分布から乱数を引く計算検証で、推定器の共分散が実データに合うという検証ではありません。

基線1−2の例では計算0.59339、複素平均の実部0.59312、振幅の平均0.63793でした。量を取り違えると減衰の説明が変わるため、記録項目を分けています。

### 保存済みVDIF推定への適用

IQ・相関・RMLを再実行せず、段階037/038/039の保存済み線形プロファイルへ診断を適用しました。プロファイルと対照比の出典JSONのSHA256を保存しています。

| 条件 | 画像積分 | 最小の条件付き複素coherence | 保存済み模擬VDIFの最小対照振幅比 |
| --- | ---: | ---: | ---: |
| 周波数変動なし | 3秒 | 0.999852 | 0.999455 |
| 中程度の線形変動 | 3秒 | 0.999851 | 0.999325 |
| 強い線形変動 | 3秒 | 0.999845 | 0.999347 |
| 連続記録の短区間0/1/2 | 各0.3秒 | 0.999660 / 0.999649 / 0.999656 | 対照比未作成 |
| 32Hz周期位相 | 3秒 | 0.999821 | 0.845899 |

最後の行では、rate推定が精密でもモデル外の速い揺れによる損失を説明できません。両列は異なる量なので、一致を合否条件にしていません。対照比も一つの模擬noise/sky実現であり、実機の測定ではありません。

### CLI・回帰

新診断あり/なしの再相関を比較し、全数値配列が一致する結合試験を追加しました。インストール済みCLIをcheckout外から実行し、diagnosticの一致・上書き拒否・範囲外拒否を確認。強い線形変動の保存VDIFをproduction pipelineで再処理し、段階037のvisibility/weight/UVW/time/frequency/露光/power/SK、整数・bool診断を含む全配列が一致しました。

- source全回帰249件成功、警告22672件、384.44秒。
- installed全回帰249件成功、警告22672件、388.54秒。source/wheelは順番に実行しました。
- pip check成功。Baseband/NumPyとStarletteの既存deprecation警告を含み、警告ゼロではありません。
- wheel 5454223bytes、SHA256 `07d97445552883a6df13e2071560ec2a106c248436bec88cb96b67c44d308fa5`。

### 再実行・保存記録

```bash
python tools/run.py workflows.rate_uncertainty_validation --output outputs/new-gaussian-uncertainty
python tools/run.py workflows.rate_uncertainty_validation --profiles outputs/stage040-input/profiles.json --output outputs/new-archive-uncertainty
python tools/verify_uncertainty_installed.py --source-run outputs/stage037-linear --output outputs/new-installed-uncertainty
```

最初のコマンドは自己完結するGaussian計算です。二つ目は`label/profile/start_s/end_s`等のJSONリストと保存済みプロファイルが必要です。三つ目は段階035/037の大容量原本を使います。大容量原本・詳細ログはGit外`outputs/`に保持し、公開の[分布・SHA・数値](../../validation/runs/stage040/summary.json)、[計算と反例の図](../../validation/runs/stage040/rate-uncertainty.png)、[installed CLI](../../validation/runs/stage040/installed-cli.json)、[全回帰/wheel](../../validation/runs/stage040/verification.json)へ小容量の記録を置きます。

## 5. 制約・未解決事項

Gaussian誤差・保存されたFisher共分散・一様露光という仮定です。実データの欠損・除外maskを使う計算ではなく、幾何delayでずれる局ごとの微小なquery時刻もこの診断では近似しています。弱信号、探索での誤検出、sample clockの誤り、共有sky・filter雑音、gain変動、範囲外rateのalias、モデル外の位相揺れは含みません。実機の下限や信頼区間ではありません。

窓はpilot範囲内・3秒以内、数値積分の位相分散の係数上界10000rad²までです。GUI表示・実機・Cas A画像品質の検証はこの段階では行っていません。

## 6. 次段階

日本語GUIで条件付き診断と対象外を示します。その後、推定器が出す誤差共分散の妥当性を、有限の信号・雑音モデルで評価します。
