# 実験用：異なる標本のbispectrum

## 目的とAPI

`vsora_simulator.bispectrum_distinct`は、独立で同じ分布の電圧標本から、三つの基線の相関積を推定する実験APIです。現行相関器・RMLの統計は変更していません。

```python
from vsora_simulator.bispectrum_distinct import distinct_sample_bispectrum
q = distinct_sample_bispectrum(voltages)
# voltages: complex128 [..., M, N]
# q['triangles']: canonical i<j<k
# q['ordinary_visibility_product'], q['distinct_sample_bispectrum']
```

3〜8局、3〜1,000,000標本、全体800万複素値まで。先行軸は別windowや反復試行で、まとめて同じ標本として平均しません。complex64はcomplex128へ昇格します。masked array・非有限値・不正三角形を拒否し、計算が有限範囲を超えた場合も失敗します。数値0だけから欠損標本を識別することはできず、共通の有効標本集合の確認は呼出側の責任です。

## 三つの相関を掛ける意味

Vij = E[xi conj(xj)]、B = Vij Vjk Vki とします。Bの角度がClosure phaseです。局gainが一定ならgiの位相とconj(gi)が一度ずつ現れて消え、Bは正の|gi gj gk|²倍になります。未知の振幅は残ります。

標本sごとにz₁s=xi,s conj(xj,s)、z₂s=xj,s conj(xk,s)、z₃s=xk,s conj(xi,s)を作ります。通常の推定は各zを平均して掛けます。同じ電圧を共有する三項の雑音は独立ではないため、平均の積の期待値はBと一致しない場合があります。

平均0・proper complex Gaussian・独立M標本、局共分散Sの場合、このリポジトリで標本indexを同一/別に分けて導いた通常積の期待値は、

E[Bhat普通] = B + D/M + (P + conj(B))/M²

D = Sii |Sjk|² + Sjj |Sik|² + Skk |Sij|²、P = Sii Sjj Skk。

独立受信機雑音だけでS=IならB=0でも平均1/M²が残ります。信号なしの三次統計が平均で正になるため、弱い信号の角度・振幅をそのまま読むことに注意が必要です。この式はGaussian電圧の式で、独立Gaussian基線相関という別の近似からは得られません。

## 異なる標本だけを使う

Aᵣ=Σs zᵣs、Hᵣq=Σs zᵣs zqs、J=Σs z₁s z₂s z₃s とします。三項で異なる順序付き標本を選ぶ平均は、重複する項を包除原理で引くと、

U₃ = (A₁ A₂ A₃ − H₁₂ A₃ − H₁₃ A₂ − H₂₃ A₁ + 2J) / [M(M−1)(M−2)]

となります。別標本の三項は独立なので、同じ分布・一定の基線平均という条件ではE[U₃]=Bです。U₃自体の不偏性にGaussian性は不要ですが、必要なモーメントが存在し、標本が独立であることが必要です。角度arg(U₃)、振幅|U₃|、比、信頼区間の不偏性は保証しません。

この演算には同じ標本内の二項・三項積も必要です。保存した平均visibility・局power・Mだけでは再構成できません。第二次統計が同じでもU₃が異なる電圧配列の例を試験しています。既存NPZに必要な統計が保存された扱いにはしません。

## 条件と未確認事項

実FFTのFIR・補間による時刻間相関、時間変化するgain/LO、ADC、RFI・欠損は含みません。異なるindexでも電圧が相関していれば不偏性の条件は崩れます。局gainの打消しは積分内で一定である場合です。短い積分と周波数差補正は引き続き必要です。

単位は相関の単位の3乗です。例としてADC²の相関ならADC⁶、JyならJy³ですが、今回の検証は任意の電圧単位です。実機のflux換算を確認した意味ではありません。

[検証・数値](../docs/reports/053-distinct-sample-bispectrum.md)を参照してください。

## 背景文献と式の出所

- Wassily Hoeffding (1948), [A Class of Statistics with Asymptotically Normal Distribution](https://doi.org/10.1214/aoms/1177730196)：U統計量の背景文献。
- N. R. Goodman (1963), [Statistical Analysis Based on a Certain Multivariate Complex Gaussian Distribution (An Introduction)](https://doi.org/10.1214/aoms/1177704250)：複素Gaussianの背景文献。

今回確認したのは出版社検索の書誌情報・抄録で、本文の取得はできませんでした。上の具体式は文献本文から引用した式ではなく、このリポジトリで導出し、全組合せ・index分割・Gaussian乱数で検証したものです。背景文献を実機への適用保証の根拠としません。
