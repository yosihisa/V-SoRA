# 段階025：短積分の感度計画とClosure情報不足

- 作成日：2026-10-02
- 状態：期待値計算・GUI・有限比較の検証完了
- 比較元コミット：8c5d672

## 読者向け概要

Closureは未知の局gainを消せますが、弱い電波を強くするものではありません。短い積分で三角形・四角形の各辺を測れる感度が必要です。直径・雑音温度・積分時間を変えて、現在の高SNR処理に使える情報数を概算するGUIを追加しました。

## 1. 目的・対象範囲

SEFDと一基線の雑音の単位確認、Cas Aの相関flux、短露光のClosure期待数、LO残差coherence、日本語計画GUI。実機の感度測定、画像復元、rate探索成功率、低SNR likelihoodは対象外。

## 2. 完了条件

- 面積・雑音温度からSEFDを計算し、一次資料の定義と単位を記録。
- 雑音の帯域/時間/異なる局の依存を確認し、有限Gaussian試験でquadrature平均分散を確認。
- SEFD4条件×時間4条件×帯域2条件で、phase/amplitude独立数を比較。
- GUIで仮定・期待値を表示し、source全試験と実ブラウザ操作を確認。

## 3. 実際に行った作業

- `apps/simulator/src/vsora_simulator/sensitivity.py`：SEFD、円形有効面積、baseline雑音、天空のFourier相関、SNR10の独立Closure数、90%coherence、JSON/図/CLI。
- `workflows/sensitivity_validation.py`：32条件、仮定直径1/3/6m・Tsys50/100/300Kの9条件、SEFD換算直径。
- GUI models/worker/jobs/static：円形開口・有効面積の指定、短積分とchannel帯域、配置、期待数・rate表示、履歴保存。
- simulator/UI tests、browser harness。[学部生向け解説と一次資料](../guide/08-sensitivity.md)、GUI説明と索引。

## 4. 検証条件・結果

Python3.12.3/NumPy2.5.1/SciPy1.18.0/Astropy7.2.2。8局spread600m、1.42GHz、仮定総flux1000JyのCas A参照形状、4時間に16露光。各露光0.1/0.3/1/3秒。SEFD1000/10000/10万/100万Jy。帯域256kHz、2.048MHzの一coherent channel比較。雑音は独立Gaussianのquadrature平均で、天体総powerを加算。画像化も雑音の乱数抽選も行わず、真の相関fluxから期待SNRを計算。

| 仮定 | 計算結果（16露光・一channel合計） |
| --- | --- |
| SEFD1000Jy・1秒・256kHz | phase282、amplitude266 |
| SEFD10000Jy・1秒・256kHz | phase16、amplitude0。SNR10のgraph連結時刻0 |
| SEFD10000Jy・3秒・256kHz | phase64、amplitude48。連結6/16時刻 |
| SEFD10万Jy | 全時間/帯域条件でphase/amplitude0。強い単基線だけではClosureを作れない |
| SEFD100万Jy | 全条件でphase/amplitude0 |
| 直径1m・効率0.6・100K | SEFD585966Jy（仮定の計算） |
| SEFD1000Jy相当の直径 | 同じ100K/0.6では24.2m。装置仕様の断定ではない |
| 90%coherence残差rate | 0.3秒で約0.835Hz、3秒で約0.0835Hz以下 |
| 分散試験 | Gaussian電圧4000trial×64sample、SEFD1万Jy＋点源1000Jy。実部/虚部分散平均が理論から6%以内 |
| 全試験 | source125成功、3034既知warning |
| 実ブラウザ | 感度計画→期待情報0の結果表示、日本語font/JS error0/外部通信0/390px overflow0、中止成功 |

2.048MHzは一channelにcoherently集められる理想比較で、現VDIFの256kHz profileがこの帯域で動いた結果ではありません。LO/clockは補正済み。雑音に天体powerを含めても、自己雑音の基線間相関と高SNR選別の厳密な確率分布は扱いません。

初回の個別試験で18成功/1失敗。直径2m・100K・効率0.6の手計算期待値に係数2の誤りがあったため、独立数値146491.40868Jyへ訂正し、全125件を再実行しました。実装のSEFD式は変更していません。この段階ではwheelを再buildしていません。後続checkpointで配布版を更新します。

```bash
python tools/run.py workflows.sensitivity_validation --output outputs/stage025-grid
python tools/run.py pytest -q
PLAYWRIGHT_BROWSERS_PATH=/tmp/vsora-browser python tools/verify_ui_browser.py --output outputs/stage025-browser
```

[32条件とアンテナ例](../../validation/runs/stage025/summary.json)、[比較図](../../validation/runs/stage025/sensitivity-grid.png)、[ブラウザ結果](../../validation/runs/stage025/browser-summary.json)、[感度画面](../../validation/runs/stage025/sensitivity-screen.png)、[検証記録](../../validation/runs/stage025/verification.json)。大きいGUI履歴はGit外outputs/gui。生成条件はsummaryに保持。

## 5. 制約・未解決事項

実アンテナの種類/有効面積、Tsys、OCXOの位相揺れは未測定。最大SNRとClosure数は実測ではなく期待値。現在の高SNR10 Gaussian条件から外れても、全ての低SNR手法で観測不可能と断定するものではない。rate探索と画像化の成功率は別に検証が必要。主ビーム・空/地面・給電損失・RFIも必要。

## 6. 次段階

1秒の整列再相関が大きいsample配列をまとめて作るため、FFT統計を小さいブロックから集計し、メモリを制限する。3秒積分とrate更新・低SNR手法の実装へ備える。感度の仮定はハードウェアの情報が得られた時点で置き換える。
