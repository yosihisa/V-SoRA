# 段階155：画像依存の局共分散の勾配と有限観測の非一意性

- 作成日：2026-10-29
- 状態：完了（供給受信機の条件付き計算参照。新しいproduction尤度の採用は保留）
- 比較元コミット：81a19ce8d818b95a62869d769ff0fbd028597cb6（154）

## 読者向け概要

画像を変えると、局の電圧が共有する成分も変わります。局共分散Cを使うGaussian尤度では、画像に応じたCの変化と正規化項の両方を微分する必要があります。今回は既存APIを呼ぶ検証専用の小モデルで、この連鎖微分を独立計算へ照合しました。

さらに、異なる二つの正の単位和画像から同じ4cellの3局共分散を作る対照を構成しました。尤度を正しく計算できることと、画像を一意に求められることは別です。実Cas Aの画像を復元・較正した段階ではありません。

## 1. 目的・対象範囲と既存検証

134/145/150の契約、現在のsynthesis/RML/Fourier、042/044/046/047/049/051/100、125〜133、152〜154をreviewしました。100には供給CのGaussian電圧尤度、既存phase-profileには供給振幅/SEFDの局位相勾配があります。125とRML試験には現在の固定高SNR共分散objective/勾配があり、これらを重複実装しません。

未接続だった**画像qに依存するC(q)の連鎖微分**を検証専用workflowへ限定しました。未知局量を解いたモデルや実観測用の新尤度は採用していません。現RMLにはw項があり、固定した同種・同cellの観測Closure共分散を使います。その式へ100の値や044のjoint行列を加算・差し替えしていません。

変更は `workflows/image_covariance_gradient_validation.py`、本レポート・索引・roadmap、[小容量記録](../../validation/runs/stage155/README.md)だけ。製品API/RML/weight/GUIは不変です。

## 2. 実行前に定めた条件付きモデル

各cellで全局共通のIID・平均0・proper complex Gaussian電圧を**密度モデルの仮定**とし、

```text
C_t(q) = G [ A_t diag(F q) A_t^H + diag(D) ] G^H
q = softmax(z), sum(q)=1
F = 1000 Jy
D = [2000,3000,4000] Jy
G = diag([1.2 exp(.2i), .8 exp(-.4i), 1.1 exp(.7i)])
```

とします。3局・4cell・8×8画素・45arcsec/pixel。全cellで同じscalar beam、既知静的uvw、独立cell、供給flux/receiver/gain、観測SNR選別なし。未知のgain/LO/SEFDを推定していません。供給wavelength座標`[[0,0,0],[1100,450,700],[-650,1400,-1100]]`をuv面で角度0/.07/−.05/.12radだけ回し、wを保持します。実局位置・Astropy/EOP・実収録の検証ではありません。

八条件は、この小モデル内で「平均・単位・共通標本・時間周波数・局量・採否・使う統計・正規化」を定めるために使いました。**実主経路で八条件が成立したという判定ではありません。** Closure変換を使わず全局電圧密度を評価する参照です。

参照画像は `softmax(.3 sin(.37 k)+.2 cos(.19 k))`。各C_refのCholesky列へsqrt(3)×[1,−1,i,−i]を掛けた12個の決定論的電圧を作り、有限平均0・second moment S=C_ref・擬moment0を確認しました。これはGaussian乱数ではありません。Gaussianは評価する密度のモデルであり、この12個を独立Gaussian実験やMCとして数えません。MC0・seed/MCSE対象外です。

## 3. 独立objective・勾配・拒否の照合

既存 `sky_station_covariance`、`direct_visibility`、100の`sample_second_moment`/`gaussian_nll`を使用。独立な点画素の直接和でCと基線visibilityを照合します。

複素電圧の負の対数密度は、100の値へモデル非依存定数を戻した

```text
M [ logdet C + tr(C^-1 S) + 3 log(pi) ]
```

です。Sの正規化密度ではありません。独立参照は6次元の実ベクトル[Re x, Im x]と実共分散 `Sigma=.5[[Re C,-Im C],[Im C,Re C]]` から、全raw電圧の二次形式と実密度の正規化を直接加算します。CはRTOL1e-12/ATOL1e-10、密度値は1e-11/1e-9で照合しました。

画像微分は各cellの `M tr[(C^-1−C^-1 S C^-1) dC/dq]` とsoftmaxの連鎖を使います。uniform・固定非対称・参照momentの3点について、独立な実raw密度の**全64成分の中心差分**をstep1e-4/3e-5、RTOL2e-5/ATOL2e-7へ照合。optimizerを呼ばず、画像復元や候補の性能比較をしていません。

| 固定点 | objectiveの独立最大差 | 勾配の全step最大差 |
|---|---:|---:|
| uniform | 2.28e-13以下 | 7.94e-9以下 |
| asymmetric | 4.55e-13以下 | 9.00e-9以下 |
| reference moment | 0 | 7.58e-9以下 |

参照momentで完全な勾配最大値は2.25e-18以下、logdet微分を省略した負対照は約.004770。事前固定した1e-6超の条件を満たします。正規化項を捨ててよいという主張ではなく、現RMLに新しい不具合を再現した意味でもありません。

既存APIの特異C・負receiver・bool標本数・不定なSの4拒否も各環境で確認。新しい拒否APIは作っていません。

## 4. 異なる画像が同じ共分散を作る対照

4cell×3基線×Re/Imの24測定に総和1を加え、geometryだけから25×64の実forward行列を作ります。SVDでそのnull方向を作り、正を保つ小さい振幅で参照画像へ正負に加えました。方向は評価データや参照形状誤差を使って選んでいません。全配列を[30配列](../../validation/runs/stage155/arrays.npz)へ保持しています。

相対singular閾値1e-10で数値rank25、行数からnull次元は少なくとも39。正・総和1の二画像のL2差は約.00914932ですが、4cellそれぞれの3局Cの最大差は3.25e-12以下、正規化したraw密度の負対数値の差は計算上0でした。固定許容内の一致と、線形forwardのnull構成を区別して記録しています。

**受信機を供給しても、この有限な観測設定では画像の一意性が足りません。** この反例は特定の小geometry/画素数のもので、131/133の失敗原因、実観測の誤差率、全arrayのrank不足を断定しません。画像を真値へ合わせるweight/実効M/正則化係数の調整にも使いません。

## 5. 正式検証・保持と制約

初回正式手順で完了。既存targetはsource**157成功/1.49秒**、installed**157成功/1.04秒**、両警告0・除外0。新unitなし。主比較のMC0/optimizer0と、既存target内部のGaussian/phase-fit試験は分けて扱います。

全科学JSON・30配列完全一致、9製品moduleの正確source/prefix/byte、native checkout外/runner/PYTHONPATHなし。非上書き2。既存454+new workflowの凍結455、原本131の76SHA、対象外tracked1494、引用37fileを保持。151wheel SHA `c54348ec4b11b89bc70956c2f0d3ad77762b79093ca128834a4bebe053f2b2ec` と製品103file+4assetのsource/wheel/installed全byte不変です。

study本体wall約.519/.465秒、生涯peakRSS87228416/87687168byte（import等を含む）、出力22320/22562byte。各worker120秒/追加64MiB/公開512KiB/段階1200秒以内。これらはCPU単発値で全夜/GPU/必要RAMを保証しません。公開監査指摘0、文書リンク2101件で欠落0。

[全条件・一次コードSHA・結果](../../validation/runs/stage155/reference.json)、[正式検証](../../validation/runs/stage155/verification.json)。新full/collect/wheel/install/browser/VDIF/相関/画像fitは未実施。最新全回帰/wheel/両実GUIは[151](151-sequence-capacity-guard.md)の両2328成功552.61/551.31秒・各30220警告の引用で、今回の件数へ加えません。通常GUI151も更新・停止していません。

この小モデルは未知実局gain/LO/SEFD、beam/RFI、filter/補間/量子化、観測選別、低SNR Closure分布、実FFT独立性を較正しません。152のdecoded reader参照、153の別の量子化集合、154のGaussian保存rate集計と合わせても、実主経路の平均・分布・画像復元の成立へ合成できません。実Cas A、実画像confidence、全夜GPUは未検証です。

## 6. 次段階・保留の更新

155は条件付きの画像依存Cの計算参照として完了し、**新production尤度の採用と156の固定原本画像再fitは保留**します。未知局量・実入力モデルの条件は自動的に解けていません。

次の有用な候補は、既存固定原本のuvw・観測採用supportと現在のClosure前方写像で、どの画像方向が局所的に観測できるかを点検することです。125〜129や既存objective/gradient試験に同等のrank/near-null参照があれば重複せず改訂します。新尤度・係数・画像fitを増やす前に、対象とする情報量の意味を限定します。実入力の新情報を優先し、148の照会を繰り返しません。150の両レビューは完了、次160文書整理/予定200根本レビューです。
