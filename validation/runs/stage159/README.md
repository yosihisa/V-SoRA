# 段階159：供給点形状と有限FFT channel平均

[レポート](../../../docs/reports/159-point-channel-forward.md)、[全6条件・入力/一次コードSHA](reference.json)、[正式検証](verification.json)、[38数値配列](arrays.npz)。詳細log/初回失敗/凍結/runtime位置はGit外 `outputs/stage159-preparation` / `outputs/stage159-*-study`。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/run.py workflows.point_channel_validation --raw-reference outputs/stage131-source-study --output outputs/new-point-channel-reference
```

3局/512sample/FFT8×16block、固定合成UVW/delayと合成decoded readerで実整列APIを通す。center/off-axisのnormalized点形状×3tone。toneの空間位相・独立FIR/補間応答・有限DFT漏れを、実補正電圧/保存相関へ照合。既存direct_visibility/RML Fourierの点位相も照合し、objective/fit/MCなし。

実Astropy幾何/codec/量子化/headerを主比較で実行していない。通常VDIF scope labelを実header証拠にしない。6条件はGaussian/IID標本や独立観測ではなく、ADC²とunit点形状を絶対Jy較正へ変換しない。

両11対象/警告0/除外0、科学JSON/38配列/6NPZ60フィールド(metadata含む)完全一致。24製品moduleの正確source/prefix/byte、native checkout外runner/PYTHONPATHなし。初回の観測設定grid不備は保存し、全選択再実行・初回成功合算なし。151full/wheel/GUIは引用。
