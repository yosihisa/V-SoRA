# 段階153：固定8電圧の量子化前後

[レポート](../../../docs/reports/153-quantized-finite-ensemble.md)、[条件・全channel平均/共分散差](reference.json)、[正式検証](verification.json)。完全な13配列・32小模擬VDIF/環境・sidecar・初回失敗はGit外 `outputs/stage153-*-study` / `outputs/stage153-preparation`。原本131とは異なる新しい有限試験入力。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/run.py workflows.quantized_ensemble_validation --output outputs/new-quantized-ensemble
```

同じ8probeを2scaleで共有。分母8の有限集合の平均/全ReIm共分散であり、不偏推定分散・Gaussian/IID・MC・実機confidenceではない。`vis_jy`という既存keyだが今回の単位はADC²。nativeはcheckout外cwd、runner/PYTHONPATHなしでworkflowを絶対指定、製品moduleは導入prefixを使用。主比較は実codec/plain FXであり152のFIR/整列/幾何経路を再実行していない。
