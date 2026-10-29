# 段階158：固定方向の有限非負候補

[レポート](../../../docs/reports/158-positive-null-candidates.md)、[全14評価・入力/一次コードSHA](reference.json)、[正式検証](verification.json)、[48数値配列](arrays.npz)。詳細log/runtime位置はGit外 `outputs/stage158-preparation` / `outputs/stage158-*-study`。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/run.py workflows.positive_null_validation --jacobian-archive outputs/stage156-source-study --direction-archive outputs/stage157-source-study --input-archive outputs/stage133-source-study --output outputs/new-positive-null-reference
```

保存157の主cut signed方向を固定し、非負条件の対称振幅上限の.25/.5/.75倍で正負12候補と基準2点を評価。既存画像評価API/独立Fourier・Closure積・共分散solveと照合する。新SVD/fit/微分/MC/再相関なし。弱.3秒は既存no-high-SNR/nullを継承。非負候補は構成した数値参照で、復元画像・有限幅の厳密対称性・観測が許す振幅confidenceではない。比較110arcsecのfull-support blurは実アンテナ一次beamではない。

source/native科学JSON/48配列完全一致。native checkout外/runner/PYTHONPATHなし/9製品module導入prefix。両既存25対象成功・警告0、画像fit試験1nodeは実行前に除外を明示。151full/wheel/GUIは引用のみ。
