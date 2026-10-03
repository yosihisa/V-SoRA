# 段階035：積分中の局周波数変動とClosureの誤差

- 作成日：2026-10-03
- 状態：完了（計算・模擬VDIFの影響確認。変動の自動補正は未実装）
- 比較元コミット：3aabd73

## 読者向け概要

これまでの補正は、一回のpilot内で局の周波数差が一定と仮定していました。周波数が徐々に変わると位相の曲がりが残り、積分で信号が弱くなります。しかも、その減衰は基線ごとに異なるため、Closureにも誤差が残ります。

一例では3秒の相関処理が完了しても、最も弱くなった基線は対照の約92%でした。同じような変動を短く積分すると減衰は減りますが、雑音が増えます。実OCXOの変化率は未測定なので、ここでは仮定した変動でこの関係を確認します。

## 1. 目的・対象範囲

滑らかな線形周波数変動の影響を、解析モデルと実際の模擬VDIFで比較すること。0.1〜3秒の積分、一定rate推定の完了/停止、Closureの偏りを確認します。実機の位相安定性を推定する段階ではありません。

## 2. 完了条件

- 一定rate補正後の相関減衰とClosure phase/amplitudeの誤差を計算。
- 積分時間と周波数変化率を区別して比較。
- 実VDIFの一定rate推定が完了する条件、停止する条件を記録。
- 正解の局変動は生成・比較だけへ使い、推定処理へ渡さない。
- source/wheel検証、レポート、匿名コミットを実施。

全条件を実施しました。画像復元は今回の検証範囲に含めていません。

## 3. 実際に行った作業

- `apps/correlator/src/vsora_correlator/coherence.py`：滑らかな周波数変化に対する複素coherenceを数値積分。最適に中心を合わせた一定rateで90%信号が残る最初の変化率を計算。
- `apps/correlator/tests/test_coherence.py`：独立した20万点の中点和、一定残差のsinc、符号反転、時間の二乗則、Closureの誤差、生成入力を検証。
- `workflows/vdif_closure_validation.py`：既存生成器へ局ごとの線形周波数変化率を追加。sample時計は正確な公称値の仮定を維持。
- `workflows/rate_drift_validation.py`：同じseedの空・受信機雑音で、変動なし/中程度/強い変動の3記録を生成し、3秒/0.3秒の計5条件を比較。保存pilotの4分割推定も追加実行。
- `tools/verify_drift_installed.py`：checkout外の導入CLIで中程度の3秒条件と計算関数を確認。

### 位相と減衰の計算

局iの発振器による位相をcycle単位で `r_i*t + a_i*t²/2` としました。rはHz、aはHz/sです。補正後の基線ijの信号は、残った位相の `exp(2πi*phase)` を積分区間で平均した複素値Kで減衰します。信号の残る割合は|K|です。

積分の中央の残差rateを0に合わせた理想条件では、Kは `a_ij*T²` で決まります。一定の位相・gainなら局誤差はClosureで消えますが、積分後のKは一般に局ごとの定数gainの積へ分解できません。今回のClosure偏りは、このモデルから計算したものです。

### 参考にした一次資料

[HOPS4のfringe-fitting説明](https://mithaystack.github.io/HOPS/hops4/data_processing/algorithm_and_output/algorithm.html)は、残差delay/rateの探索と診断を説明しています。今回は、既知のsample/幾何整列の後のLO差Hzだけを扱い、HOPSの実行・互換性確認はしていません。

[BlackburnらのClosure統計論文](https://arxiv.org/abs/1910.02062)は、Closureの局gain不変性と共分散、低SNRの注意を扱います。[Cappalloのfourfit位相補正資料](https://www.haystack.mit.edu/wp-content/uploads/2020/07/docs_hops_012_fourfit_phase_by_file.pdf)には時刻ごとの外部位相を使う処理が記載されています。今回の減衰式・数値結果は、このリポジトリで計算した結果です。

## 4. 検証条件・結果

Python 3.12.3、NumPy 2.5.1、SciPy 1.18.0、Astropy 7.2.2、Baseband 4.3.0、BLAS thread1です。

| 検証 | 結果 |
| --- | --- |
| source全試験 | 192成功、129.32秒 |
| wheel導入後の全試験 | 192成功、124.68秒 |
| 既知の非推奨警告 | 各14968件。BasebandのNumPy shape変更とStarlette TestClient。未修正 |
| 依存関係 | pip check問題なし |
| 導入CLI | 中程度の3秒条件がsourceと全数値配列/整数flag/countで一致、差0 |

### 最適に中心を合わせた計算値

**滑らかな線形変動だけ**で、積分中央の残差rateを0に合わせた場合です。90%信号が残る最初の境界は、基線の変化率について `|a_ij|*T² ≈ 1.946` でした。

| 積分T | 90%coherenceの基線変化率 | 分類 |
| --- | --- | --- |
| 0.1秒 | 約194.6Hz/s | 計算値 |
| 0.3秒 | 約21.62Hz/s | 計算値 |
| 1秒 | 約1.946Hz/s | 計算値 |
| 3秒 | 約0.2162Hz/s | 計算値 |

OCXOの実測値や推奨仕様ではありません。不規則な位相雑音、補正の誤差、pilotと画像積分の中心の違いがあれば、この理想値とは異なります。

### 実際の模擬VDIF

4局、1.42GHz、2.048Msample/s、8bit complex、各局3.06秒、seed35。生成時の共通点源1000Jy、受信機SEFD10000Jyは仮定です。各局の未知gainは固定。対照は同じ空・雑音の実現値でLO差を0にした記録です。中程度・強い変動の初期局差は[0,17.3,-11.7,26.1]Hzとしました。

| 条件 | 局の変化率[基準局,局2,局3,局4] Hz/s | pilot / 画像積分 | 結果 |
| --- | --- | --- | --- |
| 対照3秒 | [0,0,0,0] | 3秒 / 3秒 | 3工程完了 |
| 対照短時間 | [0,0,0,0] | 0.512秒 / 0.3秒 | 3工程完了 |
| 中程度3秒 | [0,0.1,-0.05,0.15] | 3秒 / 3秒 | 3工程完了、最小振幅比0.9171 |
| 強い変動3秒 | [0,1,-0.5,1.5] | 3秒 / 3秒 | pilot後、局rateの基線整合性で停止 |
| 強い変動短時間 | 同じ強い変動の原本 | 0.512秒 / 0.3秒 | 3工程完了、最小振幅比0.9932 |

振幅比は、双方で有効なchannelを用いた対照との比較です。生成truthを使う検証用の値で、未知の実skyから直接測定できるcoherence値ではありません。推定された一定rateから計算した減衰との差は、中程度3秒で最大0.00310、強い変動短時間で最大0.00228でした。

中程度3秒のlog closure amplitude RMSは0.07774、対照3秒は0.03273でした。変動モデルだけから予測したRMSは0.07197で、測定とモデルの残差RMSは0.03190です。一定rateの基線整合性χ²は0.454で処理は完了しましたが、区間内の変動がないことを確認した値ではありません。

短時間のphase/log amplitude RMSは約0.073/0.077で、対照短時間の約0.072/0.083と同程度でした。短くすると変動の減衰は小さくなりますが、雑音は対照3秒より増えています。この一seedから感度条件の一般的な成功率は推定しません。

### 保存pilotの分割推定

追加実行で、各保存pilotを4分割し、それぞれ未知sky/gainの一定rateを推定しました。全5条件の各4部分で推定は完了しました。中程度3秒の局4は、0.377秒の約26.153Hzから2.627秒の約26.492Hzへ変化しました。対照にも雑音による変動があります。今回は有意性の判定や変動の自動補正は実装せず、診断の入力候補として記録しました。

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/run.py workflows.rate_drift_validation --output outputs/drift-new
# 保存済みpilotだけを分割して再確認する場合
python tools/run.py workflows.rate_drift_validation --output outputs/drift-new --diagnose-only
```

[全条件の数値](../../validation/runs/stage035/summary.json)、[分割pilotとSHA](../../validation/runs/stage035/subpilot.json)、[導入CLI](../../validation/runs/stage035/installed.json)、[検証・wheel識別](../../validation/runs/stage035/verification.json)、[比較図](../../validation/runs/stage035/coherence.png)を保存しました。大容量の原本はGit管理外の `outputs/stage035-drift/` にあります。

## 5. 制約・未解決事項

- 決定的な線形周波数変動は、実OCXOの不規則な位相雑音やAllan偏差の実測ではありません。ADC時計の非線形変動も含めていません。
- 変動を推定処理へ入力していません。一定rate補正の影響を確認した段階で、二次位相の補正や自動短区間選択は未実装。
- 点源、固定gain、一seedです。Cas A形状・多時刻画像・実機を検証した試験ではありません。
- 信号が90%残ることとClosureに系統誤差がないことは別です。強い長積分だけが問題になるわけではありません。
- pilot分割はSNRを減らします。弱い相関では各部分の局をつなぐrate推定ができない可能性があり、未判定を安定と扱えません。

## 6. 次段階

pilotの複数部分の推定値と雑音の予想を比較する診断を実装し、日本語GUIへ表示します。変動検出、情報不足、一定rateと整合した条件を区別し、判定の限界を検証します。
