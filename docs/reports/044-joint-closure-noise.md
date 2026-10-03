# 段階044：共有信号を含むClosureの誤差伝播

- 作成日：2026-10-03
- 状態：完了（既知の模擬共分散・一次近似の検証範囲）
- 比較元コミット：45a03ed

## 読者向け概要

天体の電波は局の間で共有されるため、相関値の雑音も互いに関係します。局利得を相殺したClosureにも、どの雑音が残るかを計算します。

## 1. 目的・対象範囲

既知の模擬相関値・全実共分散から、Closure phaseとlog closure amplitudeをまとめた誤差共分散を高SNRの一次近似で計算します。実機の未知共分散を既知と扱う機能ではありません。

## 2. 完了条件

独立円対称雑音で従来式と一致し、複素局利得を付けてもClosureと伝播共分散が一致すること。共有点源の理論比を確認し、相関値へGaussian雑音を直接加える試験とGaussian電圧の標本相関を作る試験を区別すること。入力拒否・配布版・全回帰・段階レポート・匿名コミットを完成させること。

## 3. 実際に行った作業

- `vsora_imaging/closure_noise.py`：一時刻・一周波数の既知の平均visibilityと全実共分散を受け取り、phase/log amplitudeのJacobianと同時Closure共分散を返す診断API。最大8局。SNR不足・平均0のmask、冗長行、特異共分散を保持し、逆行列や信頼区間を作らない。
- `apps/imaging/tests/test_closure_noise.py`：独立円対称式、共有点源4条件、複素局gain不変性、有限差分の微分照合、低SNR/平均0/Closureなし、入力拒否、電圧試験を検証。
- `workflows/closure_noise_validation.py`：4モデル×2生成方式、それぞれ16384試行。Gaussian visibility近似と、Gaussian電圧512標本から平均相関を作る方式を別々に記録。観測値による選別をせず、既知の平均SNRで条件を固定。
- `tools/verify_closure_noise_installed.py`：checkout外からinstalled moduleを読み、共有点源の理論比を確認。
- [API規約](../../interfaces/joint-closure-noise.md)、Closure guide07、公開の小容量記録。

小さい誤差では`δphase=Im(δV/V)`、`δlog|V|=Re(δV/V)`なので、両者とClosure行列を組み合わせたJacobian Jで`C_closure=J C_visibility Jᵀ`を計算しました。既存のRML重みは変更しません。

Closure共分散とGaussian近似の基本は[Blackburn et al. (2020), §3.1](https://arxiv.org/abs/1910.02062)、Gaussian電圧のvisibilityモーメントは[段階042](042-rate-covariance-validation.md)を参照しました。この段階の全実共分散・同時伝播は微分から計算し、模擬標本で検証しています。論文を実機の達成性能の根拠にはしません。

## 4. 検証条件・結果

### 数式・電圧標本

最終の対象27件は1.22秒で成功しました。8192試行の二成分電圧試験も固定の許容差0.12以内でした。数式の試験では、独立円対称の従来式、複素gain不変性、有限差分の微分が一致しました。極端に小さいvisibilityの拒否で出た初回のRuntimeWarningは、逆数の有限性を行列積前に検査して解消しました。

4局6基線、512個の独立Gaussian電圧標本、各16384試行です。点源は局共分散の非対角を1、対角を1/ρとし、ρを0.2/0.5/0.9に設定しました。二成分は共通mode1、局位相[0,0.4,1.1,2.2]radの独立mode0.7、独立受信機雑音1.5を足した正定値モデルです。アンテナ配置や1.42GHzの実IQに変換した試験ではありません。

| 仮定モデル | 平均基線SNRの最低値 | visibility Gaussian：最大規格化差 | 電圧から相関：最大規格化差 |
| --- | ---: | ---: | ---: |
| 点源ρ=0.2 | 6.4 | 0.067709 | 0.036066 |
| 点源ρ=0.5 | 16.0 | 0.039938 | 0.023612 |
| 点源ρ=0.9 | 28.8 | 0.034124 | 0.022892 |
| 二成分 | 8.1615 | 0.052555 | 0.043931 |

規格化差は、共分散の各要素の「標本計算−一次近似」を、その行・列の一次近似分散の平方根の積で割った値です。有限試行のばらつきと非線形変換の差を含み、一次近似との完全一致とは扱いません。標本分散／一次近似分散は全例で0.9953〜1.0677でした。

共有点源では、全6Closureの一次近似分散が、独立円対称式の`(1−ρ)²`倍になりました。0.2/0.5/0.9/1なら0.64/0.25/0.01/0です。受信機雑音のない単一点源ρ=1は共分散が特異になる理想極限で、追加の独立測定を得た意味ではありません。

二成分ではphase/log amplitudeの交差共分散の最大絶対値が0.000459323radとなり、同時伝播が必要な例を確認しました。これはモデルの計算値です。

### 全回帰・配布・記録

- source全回帰297件成功、警告22672件、417.95秒。
- installed全回帰297件成功、警告22672件、423.18秒。
- source/wheelは順番に実行。pip check成功。既存のBaseband/NumPy・Starlette等のdeprecation警告を含みます。
- checkout外のinstalled API：ρ=0.5、6Closureの一次近似分散比0.25、特異共分散を逆行列化しないこと・Gaussian分布保証なしの情報を確認。

wheel 5459432bytes、SHA256 `6c94a4be8909f349397dfb1bfe0fc84bc513cfb5333bc46c399aabcfdec26bc3`。[模擬標本の結果](../../validation/runs/stage044/summary.json)、[分散比の図](../../validation/runs/stage044/closure-noise.png)、[installed API](../../validation/runs/stage044/installed-api.json)、[全回帰・識別情報](../../validation/runs/stage044/verification.json)を保存しました。

完全ログ・wheelはGit外`outputs/stage044-*/`です。標本はメモリ上で生成し、平均と共分散・全生成条件を記録します。大量の電圧標本は保存しません。

```bash
python tools/run.py workflows.closure_noise_validation --output outputs/new-closure-noise
python tools/verify_closure_noise_installed.py --output outputs/new-installed-closure-noise
```

前者はcheckout、後者はインストール済みv-soraが必要です。

## 5. 制約・未解決事項

既知のforwardモデル・独立電圧標本・高SNRの一次伝播です。ADC量子化、FIR相関、時間依存gain、実機、Cas A復元品質は含みません。production RMLの重み・採用条件は変更しません。

## 6. 次段階

この検証を日本語GUIへ接続し、実観測側で必要な雑音情報を整理します。
