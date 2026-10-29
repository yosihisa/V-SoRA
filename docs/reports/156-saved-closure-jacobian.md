# 段階156：保存入力のClosure局所Jacobianと画像方向のrank

- 作成日：2026-10-29
- 状態：完了（固定priorでの局所参照。画像再fitは保留）
- 比較元コミット：87a984b28f8d8e7ed2b6312847add293254a22c0（155）

## 読者向け概要

Closureを何本使えたかと、画像のどの変化を区別できるかは別です。**Jacobian**は、画像の各画素を少し変えたときに予測Closureがどれだけ変わるかを並べた表です。今回は保存133の入力と固定priorを使い、その表を独立差分へ照合しました。画像の再fit、truthとの形状評価、尤度や重みの変更は行っていません。

## 1. 目的・対象範囲

021、125〜129、131〜133、145/150/151/155と現rml/closure/objective_evaluation、関連試験をreviewしました。既存のrank試験は基線からClosureへのdesignの独立性、既存の勾配試験はobjectiveの微分が中心です。**画像画素から観測採用Closureへの局所Jacobian**が今回の未接続差です。155の小Gaussianモデルの非一意性を、そのまま全原本へ外挿しません。

新規 `workflows/saved_closure_jacobian_validation.py`、本レポート/索引/roadmap/[小容量記録](../../validation/runs/stage156/README.md)だけを変更。製品RML・採否・weight・GUIは不変。元156の固定原本画像再fitは条件未成立のため引き続き保留します。

## 2. 入力と実行前の条件

保存133の`high_a_t0.3`、`high_a_t3`、`weak_a_t0.3`の3つの`fitter.npz`を、元133のSHAへ照合して固定しました。各1時刻×8channel×28基線、7科学配列とmetadata、ADC²、`source.model=unknown`。32×32・16arcsec/pixel・prior FWHM240・min_snr10は133のままです。生成sky・保存fit画像・原本VDIF payloadは読みません。highの2条件は同じraw/取得pilotを共有する入れ子積分で、独立試行や積分時間だけの介入ではありません。

実`ClosureObjective`が観測値から選ぶbasis、同種同cell共分散、Fourier行列、priorを固定します。entropy/TSV/centroidは0とし、priorを基準画像として使うことと、正則化を測定情報へ足すことを区別します。parameter-sum penaltyも加えません。

## 3. 微分・whiteningと独立照合

`V=Fq`に対し、Closure designをMとすると、画素微分はphaseで`M Im(F/V)`、logampで`M Re(F/V)`です。総和1の接空間を `P=I−11^T/1024` としてrow平均を引き、観測共分散のCholesky `L` で

```text
J = L^-1 J_q P / sqrt(採用Closure行数)
```

を作ります。これはintensityのEuclidean接空間で、softmaxパラメータの尺度ではありません。`J^T J`は現固定近似の局所Gauss-Newton行列であり、完全なHessianや真のFisher情報ではありません。

独立に全点画素のFourier和を作り、全係数を照合。予測phaseは複素三角形積のangle、logampは絶対値積比のlogから計算し、固定した同じ観測basis/共分散を使います。全1024接方向 `e_k−1/1024` の差分を取りました。基準model zero・位相残差の分岐境界・正support不足は黙って行を除外せずblockedとして残す条件です。今回のactive2条件はこの事前条件を満たしました。

### 失敗と参照手順の改訂

初回source対象成功後、新workflowの`factor[1] is True`が停止しました。導入SciPyのフラグは0次元`array(True)`であり、全worker終了後にbool値確認へ1箇所だけ訂正。初回log/部分出力/凍結manifestを保持しました。

第二実行では、step1e−7の中心差分が84992成分中58成分で固定許容を超えました。最小model |V|約1.61e−5に対し、最大相対摂動が約.00626あり、有限差分の打切り誤差を確認する必要がありました。元の各step直接一致条件は未達成です。

全worker終了後の診断で、step1e−7/3e−8/1e−8/3e−9の誤差normがh²に従って減ることを確認。その診断を正式合格に数えず、元の二stepを使う**Richardson外挿**を正式比較値へ改訂しました。

```text
R = (D_3e-8 − .09 D_1e-7) / .91
```

許容RTOL3e−4/ATOL3e−4・norm相対1e−5、入力・画素・prior・二step・rank閾値を緩めず保持し、誤差norm比.04〜.16（h²なら.09）も正式条件へ追加。元stepの成否・全誤差も保存しました。第二log/部分出力/凍結・診断を保持し両環境の全選択を再実行、初回/第二の対象成功は最終件数へ足していません。診断の初回起動もmodule名とファイルpathの取り違えで数値前に停止し、standaloneへ訂正した記録を残しています。

## 4. 局所的な結果

| 条件 | 採用phase/logamp行 | Jの形 | rank（相対1e−6 / 1e−8 / 1e−10） |
|---|---:|---|---|
| high_a 0.3秒 | 43 / 40 | 83×1024 | 57 / 69 / 82 |
| high_a 3秒 | 61 / 58 | 119×1024 | 76 / 92 / 114 |
| weak_a 0.3秒 | 0 | null | null（既存no-high-SNR拒否） |

採用Closure行の独立性と画像写像の数値rankを区別します。総和1の接空間は1023次元。相対1e−10を主定義とした数値null/near-null次元は941/909で、閾値依存を含みます。行数だけから導ける代数的なnull次元下限940/904とは同じ数字ではありません。これらを位置・gain等の特定の物理ゲージと推測しません。

二条件とも元の二stepの成分許容は一部未達でしたが、誤差norm比は約.090000001。Richardsonとの相対norm差は約2.34e−11、最大絶対差は約1.84e−6/4.79e−6で固定条件内でした。データ項と接勾配も実RMLへ一致し、勾配norm相対差は3.39e−16以下でした。

総和0・局所`Jd`ほぼ0の方向をgeometryと固定局所Jから構成しました。相対`Jd`は2.30e−17/3.40e−17以下。正を保つ事前規則の小摂動対は画像L2差約2.09e−6/2.96e−6、whitened予測差norm約1.28e−11/1.87e−12でした。**局所nullの確認であり、有限幅の厳密な非線形対称性や、実形状誤差の上限を証明したものではありません。**

rankやdata lossを二積分の品質順位、感度改善や因果的露光効果へ変換しません。support・重み・uvwも異なり、同raw/取得pilotを共有しています。弱い条件をrank0の有効測定として数えず、値/微分/rankは未判定nullです。

## 5. 正式検証・保持

最終関連targetはsource**36成功/1.23秒**、installed**36成功/1.07秒**、両警告0・除外0。既存のgradient/guard/Closure/evaluationのnodeを明示選択し、画像fit試験は選んでいません。新unitなし。全科学JSON・全50数値配列完全一致、公開は[42小容量配列](../../validation/runs/stage156/evidence.npz)（dense Jと差分表はGit外）です。

8製品moduleの正確source/prefix/byte、native checkout外/runner/PYTHONPATHなし、非上書き2。旧455+new workflowの凍結456、元133入力3SHA/metadata、原本131の76SHA、対象外tracked1500、引用25fileを保持。151wheel SHA `c54348ec4b11b89bc70956c2f0d3ad77762b79093ca128834a4bebe053f2b2ec`、製品103file+4assetのsource/wheel/installed全byte不変です。

study本体wall約.880/.855秒、生涯peakRSS155942912/156663808byte（import/線形代数等を含む）、各出力約6.45MBで追加保存上限64MiB内。各worker120秒/公開512KiB/段階1200秒以内。保存量とpeakRSSを区別し、全夜/GPU/必要RAMを保証しません。公開監査指摘0、文書リンク2113件で欠落0。

[全条件・rank・参照手順改訂・入力SHA](../../validation/runs/stage156/reference.json)、[正式検証](../../validation/runs/stage156/verification.json)。MC0/画像optimizer0。新full/collect/wheel/install/browser/VDIF/再相関/画像fitは未実施。最新全回帰/wheel/両実GUIは[151](151-sequence-capacity-guard.md)の両2328成功552.61/551.31秒・各30220警告の引用で、今回へ合算しません。通常GUI151は変更していません。

## 6. 制約と次段階

固定priorの局所微分であり、画像全域・別の推定点・別supportの識別性を保証しません。観測に固定した高SNR・基線独立近似、同種同cell共分散を使うため、真のFisher・posterior・実機confidenceや低SNR画像尤度ではありません。155や他の限定参照と合成して、実Cas A/未知実LO gain SEFD/beam/RFI/実FFT独立性/全夜GPUの成立とはしません。新尤度/RML/画像再fit/GUI・外部追加反復/truth調整/Windows収録は保留です。

次157は、既存比較で使う110arcsecの共通平滑化kernelと、この局所null/near-null方向の対応を点検する候補です。これは実アンテナの一次beamではありません。既存のfull-support比較/平滑化/格子参照を先にreviewし、同等なら重複しません。truthでkernelや係数を選ばず、新fitや画像改善の主張を増やさない範囲で正式目的を定めます。実入力新回答を優先し、148の照会は繰り返しません。150の両レビュー完了、次160文書整理/予定200根本レビューです。
