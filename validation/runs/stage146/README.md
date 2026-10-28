# 段階146：供給clockと実SampleBufferの有限作用素

[レポート](../../../docs/reports/146-clock-samplebuffer-operator.md)、[科学概要](reference.json)、[53数値配列](arrays.npz)、[正式検証](verification.json)、[資源](measurements.json)。NPZは数値のみでobjectやローカルpathを含まない。

sourceは`python tools/run.py workflows.clock_operator_validation --output <new-output>`。nativeはcheckout外から`python <checkout>/workflows/clock_operator_validation.py --output <new-output>`、runner/PYTHONPATHなし、OMP/OpenBLAS各1。wrapperと既存142の検証helperはcheckoutを必要とする。

3局、raw512、FFT8×16block、offset0/.25/.5、Fs2048000、clock0と[-200,0,200]ppm、固定seed146/147。各環境3,072回の全実基底buffer入力と独立係数を全channelで照合する。実SampleBufferのreaderだけを64標本の合成decoded frameへ差し替え、FIR状態・guard・補間を実行する。binary VDIF codec/量子化/実機/未知clock推定/幾何・RF・rate位相経路は未検証。seed電圧は同じseedを両clockで共有し、2seedをMC校正と数えない。

clock0は既存049、既知局・時刻共分散は既存142のtraceと直接block対Wick和へ照合。全係数・電圧・FX・モーメント許容はrtol1e-11/atol1e-12。Monte Carlo0、MCSE対象外。分散比や係数差は既知モデルの計算値で、実効M/coverage/振幅保持率ではない。主比較の合成frameと、関連回帰の一時VDIFは別である。

Git外の目的/全ログ/凍結/開始前manifest作成の停止記録は`outputs/stage146-preparation/`、実行出力は`outputs/stage146-source-study/`と`outputs/stage146-installed-study/`に保存。138全回帰/wheel/GUIは引用のみで新実行なし。
