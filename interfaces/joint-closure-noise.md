# 既知の全visibility共分散からClosureへの誤差伝播

段階044のforwardモデル用APIです。実観測の未知共分散を推定したり、production RMLへ自動適用したりする契約ではありません。

## 入出力

`vsora_imaging.closure_noise.joint_closure_noise(mean_visibilities, real_covariance, pairs, min_snr=5.)`

- 一つの時刻・周波数cellの平均複素visibilityを基線ごとに渡す。平均は模擬モデルの既知値。
- `pairs[B,2]`：重複のない整数局番号で`i<j`。完全な基線集合でなくてもよい。最大8局。
- `real_covariance[2B,2B]`：全基線の実部、その後に全基線の虚部という順番の実対称半正定値共分散。基線間・実部虚部間の共分散も含む。
- SNRは平均振幅を、実部虚部の分散の平均の平方根で割った値。閾値は5以上。雑音0の非零平均は無限大。平均0または閾値未満の基線は無効。
- 既存の三角形phase行と四角形log amplitude行を作り、すべてのphase、その後にすべてのlog amplitudeという順番で`joint_values`、`joint_valid`、`joint_jacobian`、`joint_covariance`を返す。
- 無効基線を含む行は値・Jacobian・共分散を0にして`joint_valid=False`。0を測定値や誤差0として使わず、maskで除外する。
- phaseはrad、log amplitudeは無次元。共分散のphaseブロックはrad²、交差ブロックはrad。

返す共分散には冗長なClosure行を含むので、特異になる場合があります。逆行列・χ²・信頼区間は計算しません。SNR閾値を通ってもGaussian分布を保証しません。時間・周波数間の相関、時間依存局gain、filter・量子化・欠損露光の効果は入力モデルの範囲外です。

## 計算式

小さい複素誤差をδVとすると、一次近似で

```text
δphase = Im(δV / V)
δlog|V| = Re(δV / V)
```

です。phaseとlog amplitudeの基線からClosureへの行列を組み合わせたJacobianをJとし、`C_closure = J C_visibility Jᵀ`を計算します。phaseとlog amplitudeの間の相関も残します。

独立円対称基線雑音なら従来の`A diag(1/SNR²) Aᵀ`へ戻ります。既知の局共分散から作る模擬雑音には、[段階042の電圧モーメント](../docs/reports/042-rate-covariance-validation.md)を使えます。一般の実測受信機共分散を得る方法は、今後の課題です。

Closure共分散と高SNR近似の基本は[Blackburn et al. (2020), §3.1](https://arxiv.org/abs/1910.02062)を参照しました。このAPIでの全実共分散・phase/log amplitude同時伝播は、上記微分から計算し、模擬電圧と照合しています。論文の結果を実OCXOやCas A画像品質の保証として使いません。
