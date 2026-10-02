# 段階027：3秒pilot・分割幾何と短積分画像

- 作成日：2026-10-02
- 状態：一定rate/gainの有限模擬条件で検証完了
- 比較元コミット：5a8adc0

## 読者向け概要

3秒間に天体方向と局の周波数差を揃え、信号を足す処理に対応しました。幾何を3秒全体で一本の直線にするのではなく、1秒以下の区間で補間します。未知rateは3秒を覆うpilotから推定します。実OCXOの位相が3秒安定するかは、この模擬試験からは分かりません。

## 1. 目的・対象範囲

0.1〜3秒の整列画像積分、最大1024個・3秒pilot、時間Nyquist・rate有効期間、1秒以下のsample幾何、GUI入力・配布版。非線形LOを追う処理、拡がったCas Aの3秒形状、実OCXO測定は対象外。

## 2. 完了条件

- rate/gain一定の3秒連続VDIFで、モデル不要rate→再相関→Closure→相対RML。
- 各幾何区間≤1秒、中点を参照modelで再計算し基線RF位相差≤0.001radを検査。
- 積分全体をpilot有効期間に収める。期間外の自動外挿を行わない。
- GUIで3秒と750pilotを実操作し、source/wheel全試験を確認。

## 3. 実際に行った作業

- aligned：3秒・1024積分上限、1秒以下のgeometry knots、Astropy中点検査とmetadata、既存8192sample FX分割。
- rate：一様cadenceの参照spanを3秒へ拡張。未知baseline/channel定数の条件は維持。
- closure_pipeline：0.1〜3秒、pilot8〜1024。coverage検査は維持。
- GUI models/static、browser harness：3秒選択、pilot数1024上限、検証時のcadence/積分引数。
- VDIF点源fixture：frame数とpilot blocks、RF幾何を1秒以下に分割する生成条件。
- `workflows/three_second_validation.py`、rate単体試験。利用文書と規約を更新。

## 4. 検証条件・結果

Python3.12.3/NumPy2.5.1/SciPy1.18.0/Astropy7.2.2/Baseband4.3.0。4局・600m以内・1.42GHz・Fs2.048MHz。1520frame＝6,225,920sample/局＝3.04秒VDIF。FFT32・pilot256blocks＝4ms、750時刻＝3秒。開始0.002秒、再相関3秒＝6,144,000sample。

点源1000Jy、独立雑音SEFD10000Jyの連続帯域制限Gaussian。正確な公称sample時計、gain振幅0.4/3/1.5/0.75、未知rate0/17.3/-11.7/26.1Hzが期間中一定。broadband delayは中点固定、RF delayはpiecewise linear。真値は処理へ渡さず、source=unknown/総fluxなし。

| 確認 | 観測結果 |
| --- | --- |
| 最大station rate誤差 | 0.0014804Hz |
| 再相関 | 3秒・FX最大8192sample・局buffer最大12291sample |
| 幾何区間 | 各1秒以下 |
| GUI再実行の中点検査 | 基線RF位相差最大3.71e-6rad、0.001rad基準内 |
| 全Closure | phase52、log amplitude26、ADC² |
| GUI RML独立集合 | phase39、log amplitude26 |
| 相対画像 | 有限・非負・総量1。絶対Jy/位置を測定せず |
| 最初の一点RML | χ²/測定数0.644、選択探索の停止条件到達 |
| source/wheel全試験 | 各130成功、3034既知warning、pip check成功 |
| Chromium実操作 | 3秒＋750pilot指定→5工程→相対画像。日本語font/JS error0/外部通信0/390px overflow0、中止成功 |

最初のworkflow実行後に中点検査を追加し、GUIで同じ3秒原本を再処理して検査値を確認しています。時間Nyquistを満たす750時刻の3秒未知sky/rate単体試験も追加。従来の0.512秒pilotから1秒積分を要求する試験は引き続き拒否を確認します。

```bash
python tools/run.py workflows.three_second_validation --output outputs/stage027-three-second
python tools/run.py pytest -q
python -m pytest -q
PLAYWRIGHT_BROWSERS_PATH=/tmp/vsora-browser python tools/verify_ui_browser.py --output outputs/stage027-browser --analysis-manifest outputs/stage027-three-second/input/manifest.json --clock-model outputs/stage027-three-second/input/clock.json --analysis-integration-s 3 --analysis-pilot-integrations 750
```

[生成条件と最初の結果](../../validation/runs/stage027/summary.json)、[中点検査を含むGUI科学結果](../../validation/runs/stage027/gui-scientific-summary.json)、[ブラウザ](../../validation/runs/stage027/browser-summary.json)、[解析画面](../../validation/runs/stage027/analysis-screen.png)。[配布版の検証とSHA](../../validation/runs/stage027/verification.json)。wheel5,428,696byte。原本と内部manifestはGit外outputs/stage027-*、SHAをsummaryに記録。

## 5. 制約・未解決事項

3秒一定rate/gainの4局点源に限る検証です。数百msしか位相が保てない実機で3秒を積分できるという主張ではありません。拡がったCas Aと実アンテナ低感度、LOの非線形揺れ、未知sample時計・大気・RFIは後続検証。中点の補間確認は真のEOP/局位置の精度保証ではありません。pilotの一時刻が2msなら1024個でも3秒を覆えないため、4ms等のcadenceが必要です。

## 6. 次段階

段階024の低感度Cas A条件を3秒pilot/積分で試し、実装上限と情報不足を分ける。一定gain/rateの仮定を超える追跡・低SNR処理とハードウェアの測定は別に進める。
