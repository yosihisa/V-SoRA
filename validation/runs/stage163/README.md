# 163：局候補と最後のχ²mask

[レポート](../../../docs/reports/163-station-chisq-gate.md)の小容量記録。

- [reference.json](reference.json)：旧147の512組、保存基線候補replay/局LS observer/独立2×2式、全候補/失敗/null/index/群統計と引用SHA。
- [verification.json](verification.json)：両86対象/各1720警告、source-native一致、module/byte/SHA/予算/公開監査。151full/wheel/GUIは引用。
- [arrays.npz](arrays.npz)：全22配列。局候補rate・χ²/各mask、train/eval powerと既知期待値残差。非連結の数値はNaNで、誤差0の観測ではない。自由度0のχ²も未定義のNaNでmaskと区別。

正式目的/凍結/runner/logは `outputs/stage163-preparation/`、科学出力は `outputs/stage163-source-study/`・`outputs/stage163-installed-study/` にGit管理外で保持。入力は元 `outputs/stage147-source-study/summary.json` と `arrays.npz`、その公開reference/verificationの4SHAで固定。原本131再生成/再相関なし。

sourceは `tools/run.py workflows.station_chisq_gate_validation --archive outputs/stage147-source-study --output <新出力>`。installedはcheckout外cwdから同workflowを直接起動しrunner/PYTHONPATHなし、BLAS1/OMP1。147 helperはcheckout依存。既存出力を拒否する。

元3局64cell/8ms/1channel・σ.5/1各256組を同じseed roleで再構成。新baseline非線形fit/新独立試行0。保存候補を戻す差替えで現solverの局LSと既定χ²3判定を通し、返り値を変えず観察。381局候補/354採用/27χ²棄却/131非連結nullを保持。棄却候補をprofileにしない。

各群の評価残差は旧モデル試行の固定6 MCSEだけを確認。学習側は記述で、純粋な推定bias/因果gate効果/補正率/coverage/画像confidenceではない。実八条件/実CasA/未知局量/実FFT独立性/lowSNR尤度/全夜GPU未校正。164/165は前提未成立で保留。
