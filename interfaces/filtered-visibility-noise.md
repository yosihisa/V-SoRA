# 既知の線形係数からFFT間の雑音を計算する

`vsora_simulator.filtered_noise.filtered_visibility_moments(S, kernels, stride, samples, pairs=None)`

既知のGaussian入力を使うforwardモデルです。未知の実機雑音を推定する[標本の推定器](sample-visibility-noise.md)と役割が違います。

## 入力・出力

- raw電圧x[n]は時刻間で独立・平均0・proper complex Gaussian、局共分散Sは既知で一定。`S[i,j]=E[x_i conj(x_j)]`。
- `kernels[N,K]`は各局の固定した複素線形係数、2〜8局。`stride`は次の出力へ進むraw sample数H、`samples`は平均する出力数M。
- 出力電圧は`y_i[a]=Σ_r h_i[r] x_i[aH+r]`、visibilityは`V_ij=mean_a(y_i[a] conj(y_j[a]))`。
- 平均visibility、局の出力共分散、時刻差ごとの局共分散、複素共分散・擬共分散・全実共分散を返す。実ベクトル順は全基線Re、その後全基線Im。
- `iid_counterfactual_real_covariance`は同じ平均相関・局powerを持つ出力が時刻間で独立だった場合の比較値。実際の独立性を確認した値ではない。

## 時刻差を残した式

時刻差dに対する局共分散をR(d)とすると、

```text
R_ik(d) = S_ik Σ_r h_i[r] conj(h_k[r+dH])
E[V_ij] = R_ij(0)
Γ_(ij),(kl) = Σ_d (M−|d|)/M² × R_ik(d) R_lj(−d)
Π_(ij),(kl) = Σ_d (M−|d|)/M² × R_il(d) R_kj(−d)
```

です。和は`|d|<M`かつ係数の支持が重なる範囲だけ。Γは複素共分散、Πは擬共分散で、実部虚部の分散が同じとは限らない情報も保持します。時刻間のGaussian電圧の4次モーメントを各時刻の組に適用し、平均のM²で割った式です。visibility自体の分布をGaussianとは仮定していません。

## 共通係数の場合の換算

全局の係数が同一なら、r(d)=Σ h[r]conj(h[r+dH])、ρ(d)=r(d)/r(0)として、

```text
η = 1 + 2 Σ_(d>0) (1−d/M) |ρ(d)|²
C_exact = η C_iid
M_effective = M/η
```

です。この場合だけ`common_kernel_variance_factor`と`common_kernel_effective_count`を返します。モデルから計算した実数で、実測した独立FFT数ではありません。局別係数では、単一の換算を仮定せずnullを返します。特定の係数で換算可能かどうかを一般に判定するAPIでもありません。

## 現在の整列処理との関係

`aligned_fft_kernel(fft_length, channel_index, fractional_sample_offset=0)`は、等しいsample rateで、65tap Kaiser FIR・固定した小数offsetの65tap sinc補間・矩形のunitary FFTを一組の係数へまとめます。FFTは8〜1024の2の冪、shift後のchannel番号、offsetは[0,1)。時刻や周波数に応じて変わる係数のモデルではありません。

この係数と既存FIR→`interpolate_samples`→FFTの直接計算は丸め誤差内で一致しました。実際の色付き入力、時間変化するsample時計・幾何/rate補正、ADC量子化、RFI/mask、gain変動、channel間相関、実機の信頼区間や画像品質は確認していません。現行の相関重み・RMLへ自動適用しません。

[段階049の検証](../docs/reports/049-filtered-fft-noise.md)を参照してください。
