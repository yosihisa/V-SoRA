# 段階057：短積分の三基線積の雑音と条件付き感度

- 作成日：2026-10-04
- 状態：完了（ゼロ源分散と条件付き計算の範囲）
- 比較元コミット：cef187e

## 読者向け概要

三基線の積の平均の偏りを除いても、一回の値には雑音が残ります。天体がない既知Gaussianモデルで、その散らばりを検証し、短積分や標本の間引きで感度の尺度がどう変わるかを計算しました。必要反復数は同じ天体bispectrumと正規化を保つ仮定の計算で、実際のCas Aの観測時間ではありません。

## 1. 目的・対象範囲

局間・標本間独立、単位power、proper Gaussian、天体なしのU₃の複素分散と擬共分散を検証。三辺の既知相関係数の絶対値に対し、ゼロ源分散を基準とする条件付き尺度と必要反復数を計算します。

## 2. 完了条件

小Mの独立Wick添字列挙、Gaussian5条件の実虚平均・二次モーメントを事前の6 MC SE基準で確認。入力拒否、√Q則とρ³則、標本数と時間の仮定を確認。source/wheel全回帰、checkout外API、図の目視、公開情報確認、レポートと匿名コミット。

## 3. 実際に行った作業

- `apps/simulator/src/vsora_simulator/bispectrum_sensitivity.py`：ゼロ源の正確な複素分散、擬共分散、実虚分散、条件付き既知相関係数の尺度・必要窓数。M3〜100万、三辺の実数絶対値、数値範囲とPSDになり得ない組を拒否。
- `apps/simulator/tests/test_bispectrum_sensitivity.py`：27件のWick添字列挙、√Q/ρ³、ゼロの辺・数値範囲・拒否、固定Gaussian、workflow。
- `workflows/bispectrum_sensitivity_validation.py`：5条件の零平均・実虚二次モーメント/MC SE、ゼロ源分散比、4SEFD×4積分×2保持間隔の32条件付き点源計算、図。
- `tools/verify_bispectrum_sensitivity_installed.py`：checkout外APIを正確な式と尺度の変化と照合。
- [式・入力・制約](../../interfaces/bispectrum-sensitivity.md)、[感度ガイド](../guide/08-sensitivity.md)、索引、小容量記録。

局ごとのGaussian添字の組合せから、E[U₃]=0、複素分散1/[M(M−1)(M−2)]、擬共分散0をローカルに導出しました。実虚分散は複素分散の半分です。Mは独立電圧標本数の仮定入力で、実機の帯域×積分時間から自動確認する機能ではありません。

## 4. 検証条件・結果

対象27件成功、2.14秒。M3/4/6で、二つの順序付き異添字三つ組の全組合せについてGaussianの二次モーメントの縮約を独立列挙し、分散・擬共分散を照合。Q16で尺度4倍、各辺のρ2倍で三基線積8倍、ゼロの辺の必要窓数未到達、masked/complex/非有限/不正範囲/物理的に不可能な絶対値を拒否しました。

既知独立Gaussian電圧のM3/8/32/128は各8192試行、M4096は2048試行。全条件の実虚平均・実虚二次モーメント・交差二次モーメントが事前の6 MC SE+絶対丸め許容基準内でした。複素powerの反復平均と理論分散の比は約1.0053、1.0219、0.9873、0.9493、0.9884。図はこの比に6 MC SEの棒を付け、有限試行のずれを示します。棒は未知観測の信頼区間ではありません。初回図へ有限試行誤差の表示を追加し、同じseed/条件で最終対象試験と反復を再実行しました。科学的な判定基準やseedの選び直しはしていません。最終図を目視確認しました。

反復計算1.60秒、最大RSS143952KiB、BLAS/OMP1 thread。物理的ADC・VDIF・FIR・未知rate補正は処理していません。

### 条件付き点源計算

総flux・全ての辺の相関fluxが1000Jy、局ごとに同じSEFD、64kHz、一定gainを仮定。ρ=1000/(SEFD+1000)を既知モデルから与えます。天体ありの分散は計算しておらず、ゼロ源σを基準とする尺度です。目標尺度5は検出確率の定義ではありません。

直径1m・開口効率0.6・Tsys100Kという円形開口の仮定でSEFD約585966Jy。この値は既存SEFD APIで計算した仮定値です。

| 一回の積分 | 仮定M（間引きなし） | 一窓の尺度SNR_null | 条件付き窓数 | 条件付き記録秒 |
|---|---:|---:|---:|---:|
| 0.1秒 | 6400 | 0.003580 | 1950967 | 195096.7 |
| 0.3秒 | 19200 | 0.018604 | 72236 | 21670.8 |
| 1秒 | 64000 | 0.113224 | 1951 | 1951 |
| 3秒 | 192000 | 0.588336 | 73 | 219 |

5個おきの保持例ではMが約1/5、必要反復数が大きく増加。0.3秒の条件付き記録秒は2710522.5、3秒では27087でした。実機に間引き間隔を推奨する計算ではありません。長時間のCas Aではuvやbispectrumが変わるため、この秒数を実観測の必要時間として採用できません。拡がったCas Aの長い基線の相関fluxは点源より弱くなるため、点源の表は実機成功の根拠にしません。

source539件成功、警告23952件、440.15秒。installed539件成功、警告23952件、431.85秒。試験除外なし、source→installed全回帰の順、既存deprecation警告を含み、pip check成功。Python3.12.3、NumPy2.5.1、SciPy1.18.0、Matplotlib3.11.1、Pytest8.4.2、WSL Ubuntu。checkout外APIの正確な式・√Q/ρ³・未評価flagを確認。

wheel5484102bytes、SHA256 `6bdf40cc946b70439392fd68dd75ecdd559b15b4846471a7ac71da8beff9eb3b`。

[反復・点源計算](../../validation/runs/stage057/gaussian-and-plans.json)、[図](../../validation/runs/stage057/bispectrum-sensitivity.png)、[installed API](../../validation/runs/stage057/installed-api.json)、[回帰・wheel](../../validation/runs/stage057/verification.json)。完全ログ・wheelはGit外`outputs/stage057-*/`。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/run.py workflows.bispectrum_sensitivity_validation --output outputs/new-bispectrum-sensitivity
python tools/verify_bispectrum_sensitivity_installed.py --output outputs/new-bispectrum-sensitivity-installed
```

## 5. 制約・未解決事項

天体ありの分散・擬共分散・非Gaussianな三次統計の尤度・検出確率・角度の信頼区間は未計算。実機のM・SEFD・gain・局間雑音・FFT時間相関・時計補正の推定依存は未評価。反復窓は同じ天体bispectrumと正規化、窓間独立を仮定し、地球回転・周波数依存・未知振幅gainを無条件に平均しません。現行相関器/RMLの入力・統計・重み・SNR条件は変更していません。実画像は復元していません。

## 6. 次段階

今回の条件・分散検証・短積分の尺度を日本語GUIで比較できるよう接続します。その後、天体ありの雑音や、追加統計の保存・画像復元への適用条件を段階的に検証します。
