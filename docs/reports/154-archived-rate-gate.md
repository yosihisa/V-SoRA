# 段階154：保存rateを固定した採用maskと同pilot power

- 作成日：2026-10-29
- 状態：完了（保存基線候補の採用後集計。局推定全体の因果的分離は未実施）
- 比較元コミット：e1ac5fae1a4762ed9e8c5f9da03fab7cd5cc1271（153）

## 読者向け概要

同じデータでrateを推定してから信号を揃える操作と、強く見えたデータだけを採用する操作は別です。[147](147-rate-fit-reuse.md)では両方が含まれていました。今回は当時保存した基線ごとのrateを固定し、同じpowerの表を全候補・検出採用・検出棄却へ分けました。採用maskだけで集計値が変わることを記録し、局rate推定全体の偏りを補正したとは扱いません。

通常reset後に5時間枠99%・週間62%の実回復を確認して選択しました。追加resetの購入・使用はありません。

## 1. 目的・対象範囲

040/042の条件付きrate誤差、051のpower、098/101/107の独立template学習、143の同raw分割、144の観測SNR選別、147の保存profile/graphと現在のrate/graphコードをreviewしました。同じsolver実験を増やさず、147の`baseline_estimates`に、検出棄却した基線でも`rate_hz`が残ることを利用します。

当初候補の「同pilot推定と採用gateの因果的分離」は、この保存記録だけでは識別できません。**同じ保存rate・同じpowerに対する検出採用maskだけの集計対照**へ正式目的を縮小しました。局解のrateではなく、互いの局整合を要求しない基線ごとの候補です。新たな局profileとして製品へ使いません。検索範囲・境界や局graph/χ²の採否を解消する変更でもありません。

製品変更なし。新規 `workflows/rate_gate_postselection_validation.py` とレポート/索引/roadmap/[小容量記録](../../validation/runs/stage154/README.md)のみ。新solver・閾値・尤度・画像weight・RML・GUIは追加しません。

## 2. 固定条件・完了条件

元147の3局3基線/64cell×8ms/1channel、σ=.5/1の各256組をそのまま使います。保存rateと検出maskを読み、元の `SeedSequence([147, condition, trial, role])` で学習/独立評価の同じGaussian visibilityを再構成。512学習fingerprintと、両roleの1024行のoracle複素平均/powerが既保存配列へ完全一致することを必須としました。新seed・新rate fit・新独立試行は0です。生成する相関値と既知の独立円対称雑音は147の仮定であり、実電圧・実SEFDではありません。

候補rateが記録された行をavailable、その中の元の`accepted`をdetected、残りをrejectedとします。候補なしはnull/未判定とし0を入れません。採用/棄却は全候補を分割し、同じrateで得た**同じ数値**だけにmaskを適用。群平均のcount重み分解をRTOL1e-11/ATOL1e-12で照合します。3基線を独立標本としてpoolしません。

051の`time_power_moments`による値を、全候補/両roleで独立直接式へ照合します。

```text
P = |mean_t [V_t exp(−2πi reported_baseline_rate (t−center))]|² − 2σ²/64
```

独立評価の条件付き期待値は、保存rateと生成真値の差による位相和の絶対値二乗。直接和とDirichlet/sinc式を固定許容で照合します。真値は生成と保存fit後の検証だけに使い、fitや採否を作り直しません。各基線・各群N≥2で、評価power−この予測の平均を事前固定6 MCSE＋1e−11内とします。MCSEは元147のモデル試行の標本SD/√N。学習側や群間の差は記述のみ、N<2は未判定です。

各worker120秒/追加64MiB/公開512KiB/段階1200秒以内。source/native全JSON・数値配列、製品prefix/byte、非上書き、既存入力保持、関連targetと公開までを受入条件にしました。正式検証中のsource/tests/tools/workflowは固定しました。

## 3. 保存候補と採否

全512組×3基線＝1536候補に保存rateがあり、候補なしは今回は0でした。検出採用1143・検出棄却393。元の局解成功233/121と失敗158の記録は残しています。局解に失敗した観測も、保存基線候補の集計から黙って除外しません。

| σ | 基線 | available | detected | rejected |
|---|---|---:|---:|---:|
| .5 | 01 / 02 / 12 | 各256 | 各256 | 各0 |
| 1 | 01 | 256 | 126 | 130 |
| 1 | 02 | 256 | 126 | 130 |
| 1 | 12 | 256 | 123 | 133 |

σ=.5でも元の局解は233成功であり、基線が全検出されたことと、局解のχ²を通ったことは異なります。σ=1の表も、station成功121という母集団へ単純に読み替えません。

## 4. 平均残差と正式検証

下表はσ=1の **学習power−独立評価専用の既知予測** の平均。全候補・採用・棄却は入れ子の支持で、独立した三実験ではありません。任意visibility単位の二乗です。

| 基線 | available | detected | rejected |
|---|---:|---:|---:|
| 01 | .056946 | .261309 | −.141129 |
| 02 | .027093 | .234251 | −.173690 |
| 12 | .016543 | .215815 | −.167746 |

同じrateとpower表でも採用maskを適用すると平均が変わります。count重みを付ければ全候補の平均へ戻ります。**この差を純粋な推定器の偏り、因果効果、補正係数とはしません。** 全候補側も探索手順を通った候補であり、完全に無選別の局推定器を作った対照ではありません。

独立評価の非空15群は全て固定6 MCSE内、最大絶対平均残差/MCSEは2.016未満。σ=.5の棄却3群はN0/null・未判定として保持しました。学習側へこの判定を流用していません。全availableの学習/評価計3072powerの負値は今回は0、1超は1476。重複する採用/棄却群を足して件数を増やしたり、1で切り詰めたりしていません。

最終関連targetはsource/installed **各76成功、各640既存警告、各3.19秒、除外0**。新unitなし。study本体wall約.357/.353秒、生涯peakRSS83816448/84230144byte（import等を含む）。CPU単発値で全夜/GPUや最低RAMを保証しません。主比較はメモリ上の既存Gaussian相関値で、関連target内の一時模擬VDIF試験とは区別します。

[全512組の元局state・基線rate・採否・群集計](../../validation/runs/stage154/reference.json)、[正式条件/結果](../../validation/runs/stage154/verification.json)。全科学JSON・16配列が両環境で完全一致。16製品moduleの正確source/prefix・byte、native checkout外/runner/PYTHONPATHなし、非上書き2を確認。旧147 helperはcheckoutを要します。各出力約407kbyteで予算内です。

初回source76対象成功後、新workflowの結果組立で`original_station_state`を`state`として読みKeyErrorで停止しました。全worker終了後に新workflowの1箇所だけ訂正。条件/入力/seed/反復/許容/閾値は変えず、初回log/部分出力/凍結manifestを保持し両環境の全選択を再実行しました。初回成功を正式件数へ合算していません。

既存453凍結+新workflow=454、元147 archive4file/原本131の76SHA、対象外tracked1489、引用18fileを保持。151wheel SHA `c54348ec4b11b89bc70956c2f0d3ad77762b79093ca128834a4bebe053f2b2ec` と製品103file+4assetのsource/wheel/installed全byte不変。公開監査指摘0、文書リンク2089件で欠落0。

## 5. 制約・未解決事項

新しい512組を追加した結果ではありません。元147の相関値を同じseedで再構成した派生解析で、source/native反復・基線・群を独立追加試行と数えません。基線候補の数値があることは、optimizerの成功・局整合・aliasの不存在を保証しません。今回は候補なし分岐の新しい実データ検証はありません。

検出後の支持を固定した帳簿上の分解であり、局解のgraph/χ²や探索availabilityを含む全採用gateと、同pilot推定の依存を因果的に分離した方法ではありません。147の局推定結果を改善・較正していません。独立評価は生成モデルの仮定で、同raw分割143を独立化した意味でもありません。047のPSD/局power gateや051file診断全体は通していません。

FIR/ADC/量子化/幾何/RF-rate整列/電圧・VDIF生成/新相関/Closure/RML/画像fitは主比較外。新full/collect/wheel/install/browserも未実施です。最新全回帰/wheel/両実GUIは[151](151-sequence-capacity-guard.md)の両2328成功552.61/551.31秒・各30220警告の引用で、今回の件数に足しません。通常GUI151は変更していません。

[145の八条件](../../interfaces/image-noise-applicability.md)は未成立。152/153の限定参照と合わせても、実機Cas A、未知実LO/gain/SEFD、beam/RFI、実FFT独立性、低SNR画像尤度、実coherence/coverage、全夜GPUの成功へ合成できません。

## 6. 次段階

次155は、152〜154が確認した範囲を八条件へ照らし、画像固有のモデルが定まっているかを再点検する候補です。条件が足りなければ新目的関数・画像比較を開始せず、不足を具体化します。既存known-C API/042/044/046/047/049/051/100を重複実装しません。実入力の新情報を優先し、148の照会を繰り返しません。150の文書整理/根本レビューは完了済み、次160/予定200です。
