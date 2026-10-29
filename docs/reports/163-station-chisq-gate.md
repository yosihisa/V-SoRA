# 段階163：局最小二乗候補と最後のχ²棄却を区別する

- 作成日：2026-10-30
- 状態：完了（保存基線候補に条件付けた局解内部の参照）
- 比較元コミット：6cc5a0e413ac21e57034e4f54929e310fd6fce32（162）

## 読者向け概要

基線ごとの周波数差が検出できても、それらが一つの局rateの組で説明できるとは限りません。現solverは基線の検出とgraphの連結を確認し、局rateを最小二乗で計算した後、残差のχ²が大きければ棄却します。

今回は保存済みの基線候補を固定し、**最後のχ²判定前に計算された局候補**を観察しました。新たな観測や基線rate探索を増やさず、381候補のうち採用354、χ²棄却27を分け、非連結131組は候補なしとして残しました。棄却候補を製品profileへ昇格したり、同pilot推定の純粋な偏りを取り出したりした結果ではありません。

## 1. 目的・変更範囲

040/042/051/098/101/107/143/144/147/154と現constant-rate solver/graph、関連code/test/workflow/validationをreviewしました。147のpowerは局解成功群だけ、154は互いの局整合を課さない基線候補と検出maskでした。今回の差は、検出graphが連結である領域の局最小二乗候補と、その後の既定χ²棄却の分割です。

新[workflow](../../workflows/station_chisq_gate_validation.py)、本report/索引/roadmap/[小容量記録](../../validation/runs/stage163/README.md)のみ変更。製品solver/API/閾値/RML/尤度/weight/GUIは変更せず、新しい基線非線形fitや独立試行も追加しません。

## 2. 固定入力・実行範囲

元147の3局3基線/64cell×8ms/1channel、visibility雑音のquadrature σ=.5/1の各256組、計512組をそのまま使いました。元 `SeedSequence([147,condition,trial,role])` のrole0学習/role1評価で再構成し、全512学習fingerprintを保存記録へ一致させました。独立roleは旧Gaussian visibilityモデルの仮定であり、電圧/VDIF/FIRや実観測の独立性を実測した意味ではありません。

情報の流れは次のとおりです。

```text
元学習pilot → 旧147保存の基線候補・検出maskを固定
             → 現solverの局LS候補 → 既定χ²≤3で採用/棄却
                  ↓ 同じ候補を固定
             学習power / 独立role評価power
真値 → 生成と候補観察後の期待値検証だけ
```

今回 `_baseline_rate_records` の戻り値を保存recordsで差し替えます。基線探索/検出を再実行したとはしません。実 `validate_pilot_arrays`、既定min_snr8/min_peak_z8/maxrate50、graph-rank検査、局最小二乗、χ²棄却の部分を通しました。実 `np.linalg.lstsq` を返り値を変えないobserverで観察し、棄却前候補を取得。χ²閾値を緩めず、新solverや別の推定器を製品の効果として代用しません。

学習のvisibility/weight/time/pairsだけがsolverへ入り、評価dataや真値は渡しません。graph非連結では局候補/power/期待値をnullで保持。χ²棄却時も製品profileはNoneのままで、観察した数値候補と区別します。時刻・周波数・閾値・支持を真値に合わせ直していません。

## 3. 独立照合・受入条件

3局の基線incidenceの符号と保存rate_sigmaから2未知局rateの正規方程式を作り、手書き2×2逆式で独立に計算しました。現solverの最小二乗解、独立残差和によるreducedχ²、元147の採用/失敗理由/成功rateをRTOL1e−11/ATOL1e−12で照合。自由度0ではχ²=Noneを維持し、0の測定値にしません。

同じ局候補で学習/評価それぞれの既存051 `time_power_moments` を呼び、次の直接式と一致させました。

```text
P = |mean_t [V_t exp(−2πi candidate_baseline_rate (t−center))]|² − 2σ²/64
```

候補観察後の既知評価期待値は、候補rateと生成rateの差による直接位相和の絶対値二乗で、Dirichlet/sinc式とも照合しました。元147で成功した354組×両roleの708power行が旧配列へ一致しています。

群はconnected、その中のaccepted、χ²rejected。connected平均が後二群のcount重み平均へ一致することを必須とし、maskで候補値を変えません。非連結を0埋めして全試行平均には加えません。評価power−既知期待値だけをN≥2で固定6 MCSE＋1e−11以内としました。MCSEは**元147モデル試行**の標本SD/√Nで、新しい独立試行ではありません。学習残差/群差は記述のみ、N0/1は未判定とする規則です。

## 4. 結果・正式検証

| σ | 元trial | 連結候補 | 既定採用 | χ²棄却候補のみ | 非連結/null |
|---|---:|---:|---:|---:|---:|
| .5 | 256 | 256 | 233 | 23 | 0 |
| 1 | 256 | 125 | 121 | 4 | 131 |

基線候補は旧147から固定し、新baseline非線形fit0。現局solverの部分replayは各環境512回です。新しく観察した棄却27候補も、元の失敗判定を維持しています。非連結131組は条件付き集計の外にあることを明示し、黙って成功群へ含めていません。

下表はσ=1での「学習power−独立評価専用の既知期待値」の平均です。単位は任意visibility単位の二乗です。

| 支持 | N | 基線01 | 基線02 | 基線12 |
|---|---:|---:|---:|---:|
| connected | 125 | .164554 | .117445 | .094831 |
| accepted | 121 | .154010 | .115025 | .086747 |
| χ²rejected | 4 | .483521 | .190632 | .339376 |

同じ候補を使った集計がχ²maskで分かれます。棄却4組の小さい群を母集団全体の偏りや因果効果へ外挿しません。connected側にも探索・基線検出・graph選択が残るため、「無選別の推定器」を得た対照ではありません。

評価残差は両σ/3群/3基線の18成分が固定6 MCSE内、最大絶対平均残差/MCSEは1.750未満。学習側へこの合格を流用しません。全連結候補のtrain/eval合計2286powerで負0、1超1202を保持。0〜1の保持率やcoherenceとして切り詰めていません。群・基線・source/nativeを追加独立試行として数えません。

初回正式手順で成功。新unitなし。両86既存対象、source6.83秒/installed6.27秒、各1720既存Baseband警告、除外0。対象はrate/graph/variation/time_scatterで、対象内の新しいfitや一時模擬VDIFと、主比較のbaseline fit0を区別します。全科学JSON/[22配列](../../validation/runs/stage163/arrays.npz)が完全一致し、16製品moduleの正確source/prefix/byte、native checkout外/runner/PYTHONPATHなし、非上書き2を確認。147 helperはcheckoutを要する検証依存です。

旧461+newworkflow凍結462、元147archive4/原本13176/対象外tracked1542/引用33fileのSHA保持。151wheel SHA `c54348ec4b11b89bc70956c2f0d3ad77762b79093ca128834a4bebe053f2b2ec` と製品103+4assetsのsource/wheel/installed全byte不変です。

study本体wall約.364/.363秒、生涯peakRSS86716416/87355392byte、保存334404/334863byte。各worker120秒/追加64MiB/公開512KiB/段階1200秒内。単発wall・生涯RSS・保存量は全夜/GPU/最低PC仕様ではありません。公開監査指摘0、文書リンク2219件で欠落0。

[全512組の候補/失敗/null・群統計・入力SHA](../../validation/runs/stage163/reference.json)、[正式検証](../../validation/runs/stage163/verification.json)。新full/collect/wheel/install/browser/VDIF/再相関/Closure/RML/画像fitなし。全回帰/wheel/両実GUIは[151](151-sequence-capacity-guard.md)の両2328成功552.61/551.31秒・各30220警告を引用し、今回へ加算しません。通常GUI151は変更していません。

## 5. 制約・次段階

今回区別したのは、保存検出基線に条件付けた局候補と最終χ²maskです。基線検索からの全取得経路、検索availability、基線検出、graph選択と同pilot推定全体の因果的分離は未識別です。棄却候補を実データへ適用する提案ではなく、productionprofileを増やしていません。051file診断や上位InputIdentityも主比較外です。

八条件、実Cas A、未知実LO/gain/SEFD、beam/RFI、実FFT独立性、低SNR画像尤度、全夜GPUは未校正。162のcodec参照と今回のGaussian visibility再構成を、同じ実入力の一貫した確率モデルへ合成しません。

164/165の新画像尤度と固定原本画像再fitは、前提未成立のため引き続き保留。次回は実入力の新回答や具体的モデル成立条件の更新を優先します。追加の局所参照や不足条件の反復文書を段階番号のために作らず、必要なら根本レビューを前倒しして計画を改訂します。148の質問は繰り返しません。次文書整理170/予定根本レビュー200、新GUI/外部追加反復/truth係数調整/Windows収録は保留です。
