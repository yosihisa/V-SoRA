# 段階156：保存133・固定priorのClosure局所Jacobian

[レポート](../../../docs/reports/156-saved-closure-jacobian.md)、[全3条件/差分・rank/失敗診断](reference.json)、[正式検証](verification.json)、[小容量42配列](evidence.npz)。元入力3NPZ、全50配列（dense J/差分を含む）、初回/第二log・凍結manifest・診断はGit外 `outputs/stage156-preparation` / `outputs/stage156-*-study`。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/run.py workflows.saved_closure_jacobian_validation --archive outputs/stage133-source-study --output outputs/new-saved-closure-jacobian
```

32x32 constructor prior、min_snr10、現在の観測選択basis/同種同cell共分散を固定。正則化なしのデータ項をintensity unit-sum接空間で線形化する。真のFisher/画像confidenceではない。元二stepの中心差分は一部で許容未達、正式比較は同じ二stepのRichardson外挿へ改訂し、元誤差とh²収束も保存。許容を緩めた結果ではない。weak入力はno-high-SNR/nullを保持しrank0という測定結果へ変換しない。

nativeはcheckout外cwd、runner/PYTHONPATHなし、製品moduleは導入prefix。新image fit/MC/raw/相関なし。比較の110arcsec平滑化や生成truthをこのworkflowへ渡していない。151full/wheel/GUIは引用のみ。
