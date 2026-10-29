# 段階161：同時混合した3線スペクトルの有限平均

[レポート](../../../docs/reports/161-finite-band-forward-mean.md)、[全結果・入力/一次コードSHA](reference.json)、[正式検証](verification.json)、[21数値配列](arrays.npz)。詳細log/runtimeはGit外 `outputs/stage161-preparation` / `outputs/stage161-*-study`。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python tools/run.py workflows.finite_band_mean_validation --raw-reference outputs/stage131-source-study --output outputs/new-finite-band-mean
```

3局/512sample/FFT8×16block。各入力内で3modeを混ぜ、4固定符号probeの有限平均を周波数別の電力和と実整列APIへ照合する。線電力質量の2配分で連続PSD/Hzではない。符号係数の二次moment/pseudo-momentは両方Iで、proper complex/Gaussian/IID/MCではない。

固定合成geometry/decoded reader、供給clock/gain/rate、ADC²/normalized pointの限定参照。実Astropy/codec/量子化/header、noise共分散、coverage、実観測/画像尤度を校正していない。159の検証helperだけをimport再利用し、159 runは呼ばない。helperはcheckoutが必要で製品moduleの導入prefixと区別する。

source/native科学JSON/21配列/各8NPZ80フィールド(metadata含む)一致。両11対象/警告0/除外0、24製品moduleの正確source/prefix/byte、native checkout外runner/PYTHONPATHなし。151full/wheel/GUIは引用、新fit/MCなし。
