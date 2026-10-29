# 162：同じ有限電圧の実codec→整列平均

[レポート](../../../docs/reports/162-quantized-aligned-mean.md)の小容量記録。

- [reference.json](reference.json)：固定入力・全probe/scale/clip、8API、実行範囲、独立式/一次コードSHA、初回と第二回の失敗。
- [verification.json](verification.json)：最終両14対象/各105警告、module/byte/SHA/非上書き、予算と公開監査。151の全回帰/wheel/GUIは引用。
- [arrays.npz](arrays.npz)：全21科学配列。raw/decodedの最初512sample、固定符号/線電力/query、量子化前後の各probe visと有限平均。全4096sampleの実復号は別途全件照合。

## 再現と所在

sourceは `tools/run.py workflows.quantized_aligned_mean_validation --raw-reference outputs/stage131-source-study --output <新出力>`。installedはcheckout外のcwdから同workflowを直接起動し、runner/PYTHONPATHを使わない。146/152/153の検証helperはcheckoutを要する。BLAS1/OMP1。既存出力は拒否する。

正式目的/凍結/runner/全logは `outputs/stage162-preparation/`、科学出力は `outputs/stage162-source-study/` と `outputs/stage162-installed-study/` にGit管理外で保持。各24新VDIF/24sidecar、8保存相関、metadataを含む。初回と第二回は `outputs/stage162-attempt01-source-study/`・`outputs/stage162-attempt02-source-study/` とpreparation配下attempt01/02に保持。実原本131は再生成/再相関していない。

固定3局/4096sample1frame/FFT8×16block、4符号の同時3mode混合/scale1と.125。独立量子化にfloat32中間丸めを含み、復号全波形へ独立FIR/補間/RF/DFT係数を作用させる。geometryだけ固定合成値へ差替え、reader/codecは実行。局powerはSK無効の実accumulator内部を観察。MC0/seedMCSE対象外。

二scale・両環境は同じprobeを共有し独立観測ではない。有限平均差を実機補正率/Gaussian noise/連続PSD/画像品質へ読み替えない。八条件・実CasA・未知局量・実FFT独立性・lowSNR尤度・全夜GPU未検証。
