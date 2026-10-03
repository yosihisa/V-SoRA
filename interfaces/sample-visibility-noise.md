# 局の標本共分散からvisibilityの雑音を推定する

条件付きの診断APIです。真の局共分散を入力する[forwardモデル](../docs/reports/042-rate-covariance-validation.md)と区別します。

`vsora_simulator.visibility_noise_estimate.estimate_visibility_noise(station_sample_covariance, samples, pairs=None)`

## 入力と仮定

局の複素電圧をxとし、**同じM個の標本**から`S_hat = Σ x xᴴ / M`を作ります。入力はその実測／模擬標本のHermitian半正定値行列です。対角は局power、非対角は複素相関。真の天体・受信機共分散や局gainを要求しません。

- 2〜32局、整数の独立標本数Mは局数以上、2⁵³以下。一般の半正定値入力について推定共分散の半正定値性を確保する参照実装の範囲。
- 電圧は平均0、proper complex Gaussian、標本間は独立、全標本で局共分散は一定という仮定。
- 経験的な標本平均は引かない。局ごと・基線ごとに異なるmaskや標本数の相関を同じ行列へ混ぜない。
- `pairs`は重複のない整数局番号で`i<j`。省略すると全基線。
- 相関・powerは同じ電圧の単位、同じ正規化で渡す。相関がADC²なら共分散はADC⁴。

FFT block数をMとして使う場合、FFT blockが実際に独立かは別の確認が必要です。FIR、補間、量子化、非Gaussian妨害、時間変化、欠損maskをこの式が自動で扱うわけではありません。

## 返す量と式

実パラメータ順は、全基線のRe、その後に全基線のImです。`mean`は測定したvisibility、`real_covariance`は推定した雑音共分散、`plug_in_real_covariance`は補正前の式です。複素共分散と擬共分散も返します。

真の共分散の式へS_hatをそのまま代入した値をC_plug、測定visibilityの実ベクトルをm_hatとすると、

```text
C_hat = (M² C_plug − m_hat m_hatᵀ) / (M² − 1)
```

です。仮定の下では`E[C_plug] = C_true + m_true m_trueᵀ/M²`、`E[m_hat m_hatᵀ] = C_true + m_true m_trueᵀ`なので、補正式の平均はC_trueになります。これは**多数の試行で平均したときに偏りがない**という意味です。一回の推定が真の共分散と等しいこと、誤差領域の包含確率が正しいことを保証しません。

逆行列や信頼区間は計算しません。Gaussian電圧から作った少数標本のvisibility分布をGaussianと仮定するAPIでもありません。[有限標本の検証](../docs/reports/046-sample-noise-estimator.md)を参照してください。

Closureへの一次伝播では、共通の**半径方向**のvisibility変化がphaseにもlog closure amplitudeにも寄与しないため、補正後の伝播共分散は補正前の`1/(1−1/M²)`倍になります。大きいMではこの補正自体は小さい効果です。基線間の共有雑音や実部虚部の分散の違いを計算することと、有限標本の偏りを補正することを区別します。
