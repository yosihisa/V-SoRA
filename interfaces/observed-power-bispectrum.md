# 同じ標本の観測powerで正規化した三次統計

段階085の実験APIである。弱い電圧から形状を調べる前に、gain相殺と有限標本の平均の違いを確認する。RMLへ渡す誤差モデルや実機の較正ではない。

## 計算API

`vsora_simulator.bispectrum_observed_power.observed_power_normalized_bispectrum(voltages, triangles=None)`

- 入力は有限complex電圧 `[...,M,N]`。Mは3〜1,000,000、Nは3〜8、全要素は8,000,000以下。先頭の軸は別ensemble/windowとして保持する。
- 一つのwindowは既に全局で共通の標本集合を使う。masked array、非有限値、powerが0の局/windowは拒否し、無効値を測定値0として使わない。
- 三角形は一意な整数 `i<j<k`。省略時は全組合せを使う。入力は変更しない。
- 各局の観測powerは `P_i = mean(abs(x_i)**2)`。同じ標本のRMSで電圧を割り、既存の異標本U₃を計算する。各三角形の結果は `R = U3 / (P_i P_j P_k)` と同じ量になる。
- `observed_power_normalized_u3` と `observed_power_normalized_ordinary_product` は無次元の複素量。角度への変換・切捨て・SNR選別は行わない。
- 実装は実部・虚部の最大成分で一度scaleを整え、極端に大きい/小さい電圧のpowerを直接二乗してoverflow/underflowさせない。数値用の `voltage_conditioning_scale` と `mean_conditioned_power` を返す。前者の二乗と後者の積が元のpowerに対応するが、極端なscaleではその積をfloat64へ再構成できない場合がある。

## gain相殺の意味

区間中一定の非零複素gainを各局へ掛けると、U₃は `abs(g_i g_j g_k)**2` 倍、三局powerの積も同じ倍率になる。そのためRは有限実現ごとに不変である。この恒等式にはGaussianや独立標本という仮定は要らない。

ただし、同じ標本で推定したPには誤差がある。`E[U3/Pprod]` は一般に `E[U3]/population_Pprod` と同じではない。既知母powerのU₃の不偏性や共分散を、この比へそのまま移さない。局gainの相殺は、未知LO・時間変化・方向依存beamを取り除いた証拠にもならない。

## 完全共有Gaussian電圧の限定式

`gaussian_rank_one_observed_power_moments(M)` は `x_i(a)=g_i z(a)`、独立なproper Gaussian z、区間内一定の非零gというrank-one極限だけを扱う。受信機ごとの独立雑音はこの極限に含まれない。

`w_a=abs(z_a)**2`、`r_a=w_a/sum(w)` と置くと、rはDirichlet(1,...,1)となる。U₃の比は、異なる順序付きa,b,cに対して

```text
R = M^3 / (M)_3 * sum_distinct(r_a r_b r_c)
E[R] = M^2 / ((M+1)(M+2))
```

となる。`(M)_q` は下降階乗。通常の観測power正規化三基線積は、この極限では有限実現ごとに1である。U₃の比の平均はM=3で0.45となり、母powerで正規化したU₃の平均1と異なる。

二つの三つ組がk個の標本番号を共有すると、Dirichletの6次積分の分子へ `2^k` が入る。二次モーメントは

```text
A = sum(k=0..3) C(3,k) (3)_k (M)_(6-k) 2^k
E[R^2] = M^6 A / ((M)_3^2 * M(M+1)...(M+5))
Var(R) = E[R^2] - E[R]^2
```

である。Mより大きい次数の下降階乗は0とする。分散は有理数のまま差を取り、最後にfloatへ変換する。実部の平均・分散、虚部0、二次モーメントを返す。

Dirichletの密度と正規化定数は[SciPyの公式説明](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.dirichlet.html)を確認した。上のRの式は、その積分比と標本番号の重なりを用いて本プロジェクトで導出し、独立な列挙とGaussian反復電圧で照合する。

このrank-one式で一般のSの比を補正したり、一般天体のσとして使ったりしない。複素量の平均と、位相・log・振幅の平均は異なる。未知観測の検出確率・信頼区間・形状識別・画像の保証は含まない。
