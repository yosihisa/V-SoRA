# 段階020：Closureと短積分の周波数差

- 作成日：2026-10-02
- 状態：完了
- 比較元コミット：0fb1504

## 読者向け概要

局の振幅・位相を正確に測れなくても、複数の相関値を組み合わせれば局の誤差を打ち消せます。この組み合わせがClosureです。しかし積分中の位相回転で信号が消える問題は残ります。実観測をClosure＋RML中心に進めるため、両者の違いを実装と数値で確認しました。

## 1. 目的・対象範囲

高精度較正なし、局間LO差あり、一回の積分は数百ms〜数秒という条件を採用する。Closure phase、log closure amplitude、独立集合と共分散、有限積分損失を対象とする。RML画像化と未知LO推定は次段階。

## 2. 完了条件

1. 任意の局の複素利得を掛けてもClosureが1e-12以内で一致する。
2. 完全4/8局の独立Closure数が3/2、21/20となり、共有baselineの共分散を保持する。
3. 高SNR Gaussian40,000標本の共分散が理論と3%以内で一致する。
4. 0.3秒のIQ→FXで有限積分損失を確認し、与えた真のrate補正後にClosureを回復する。
5. ADC²入力をJyと偽らずClosureへ保存する。GUIから検証を実行できる。

## 3. 実際に行った作業

- `apps/imaging/src/vsora_imaging/closure.py`：三角形・四角形、valid mask、SNR5以上、QR独立集合、全共分散、抽出CLI。16局までのCPU参照実装。
- `apps/imaging/tests/test_closure.py`：独立二点源式、利得・flux・平面近似の移動不変性、rank、flag、共分散、ADC、周波数差。
- `workflows/closure_validation.py`：40,000標本と4種類の積分計算、実IQ→FX、図・summary。
- GUIのmodel/jobs/worker/HTMLとserver試験：日本語「Closureの局誤差不変性・短積分の周波数差」を追加。理想CLEANの長積分を実OCXO性能と混同しない説明。
- `pyproject.toml`：`vsora-closure`。設計・入門・roadmap・READMEを更新。
- [Closure＋RML計画](../design/closure-rml-plan.md)：理論の出典と今後の順序。過去の既知モデル較正は比較用として維持。

## 4. 検証条件・結果

Python3.12.3、NumPy2.5.1、SciPy1.18.0、既存の独立verification環境。実受信機の測定は行っていない。

```bash
python tools/run.py pytest -q
python tools/run.py workflows.closure_validation --output outputs/stage020-closure
```

| 確認 | 結果 | 判定・意味 |
| --- | --- | --- |
| 局利得不変性 | phase最大1.33e-15rad、log amplitude最大8.88e-16 | 数値精度で一致 |
| 独立Closure | 4局phase3/amplitude2、8局21/20 | 解析rankと一致 |
| Gaussian共分散 | phase相対誤差0.924%、log amplitude0.603% | 3%条件内、非対角成分も保持 |
| 0.3秒の一定LO差計算 | 最弱baseline残存率14.53%、log amplitude偏り最大2.0013 | Closureで積分損失は消えない |
| 実IQ→FX | 計算の係数との差8.54e-4、補正前log amplitude偏り2.0063 | Gaussian波形の有限標本を含む |
| 真のrateをIQで補正 | log amplitude3.33e-16、phase4.44e-16rad | 与えたrateで回復。未知rate推定の成功ではない |

IQは4局、Fs2.048MHz、614,400sample/局、0.3秒、FFT128。局rate `[0,1.31,-0.67,2.23]`Hz、振幅 `[0.4,3,1.5,0.75]`。強い共通Gaussian信号、独立受信機雑音なし、一定bandpass。channel平均はこの限定条件でParseval比較のために使用。実天体の平均手順として一般化しない。Closure検査の重みは仮値で、実SNR測定ではない。

全試験98件成功。従来と同じ874件の依存ソフトdeprecation warning。GUIのClosure検証は実subprocessを起動し、summaryまで確認。段階019のChromium操作試験は本段階で再実行していない。

詳細：[数値](../../validation/runs/stage020/summary.json)、[図](../../validation/runs/stage020/closure.png)。生成IQはメモリ内のみ、大容量原本は保存していない。

## 5. 制約・未解決事項

- 一定局利得が掛かる条件で成立。時間・帯域内変化、主ビーム差、baseline固有誤差は別途評価。
- 高SNR・独立baseline Gaussian近似。SNR5のcutは厳密な低SNR統計を保証しない。self-noiseや補間後のchannel相関は未対応。
- 三角形/四角形から独立集合を選ぶ。欠損網の長い閉路を全部拾う処理ではない。
- 絶対fluxと位置原点はClosureから測れない。平行移動試験はw=0の平面近似。
- 未補正LO差で信号が消え得る。OCXOの温度変化・位相雑音は未測定。
- RML復元、実VDIFからのClosure画像、外部RMLソフトは未実施。

## 6. 次段階

Closureと共分散を使う小規模RMLを実装する。非負・相対flux・表示中心・滑らかさを明示し、勾配を数値微分と比較する。生成形状を事前画像に使わない復元と、未知局利得への不変性を確認し、その後モデル不要のLO差推定へ進む。
