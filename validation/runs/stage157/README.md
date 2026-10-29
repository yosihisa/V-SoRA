# 段階157：110arcsec比較平滑化と局所near-null部分空間

[レポート](../../../docs/reports/157-smoothed-null-subspace.md)、[作用素対照・全6部分空間](reference.json)、[正式検証](verification.json)、[16数値配列](arrays.npz)。完全log/runtime prefixはGit外 `outputs/stage157-preparation` / `outputs/stage157-*-study`。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/run.py workflows.smoothed_null_validation --archive outputs/stage156-source-study --output outputs/new-smoothed-null-reference
```

156の固定prior/保存J/観測支持を再利用。110arcsecは比較用Gaussian kernelで実アンテナ一次beamではない。全支持の線形作用素と、unit-sum接空間の数値null/near-nullに対するFrobenius二乗norm比・spectral norm比を計算する。物理power保持率・情報損失割合・posteriorではない。signed方向は復元した非負画像ではなく、APIへ渡すのは非負点対/translation limit0のcontrolだけ。

nativeはcheckout外cwd、runner/PYTHONPATHなし、製品moduleは導入prefix。新fit/MC/再相関なし。main translation optimization0と既存registration試験は区別する。151full/wheel/GUIは引用のみ。
